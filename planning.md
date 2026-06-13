# FitFindr planning.md

> doing this before any code. this is the spec im handing to claude to generate each piece, so the more exact it is the better the generated code is. ill update it before i start any stretch feature.

---

## Tools

3 tools, the required ones. each one works and gets tested on its own before I wire them into the loop.

### Tool 1: search_listings

**What it does:**
pure python keyword search over the 40 mock listings, no LLM. loads the dataset, filters by price and size if i gave them, scores whats left by how many of my query words show up in each listing, drops the zeros, sorts best first, hands back the full listing dicts. returns [] if nothing matches and never throws.

**Input parameters:**
- `description` (str): the keywords for what i want, eg "vintage graphic tee". required. gets tokenized and matched against each listing's searchable text. if its empty/whitespace everything scores 0 so u get [].
- `size` (str | None): optional size filter. case insensitive substring match against the listing's `size` field, so "m" matches "M", "S/M", "M/L" but NOT "XL (oversized)" (no letter m in that string). None skips size filtering.
- `max_price` (float | None): optional inclusive price ceiling in dollars. keep a listing only if `price <= max_price`. None skips price filtering.

**What it returns:**
a list[dict] sorted best match first. each element is the full unchanged listing dict w these fields: `id` (str), `title` (str), `description` (str), `category` (str, one of tops/bottoms/outerwear/shoes/accessories), `style_tags` (list[str]), `size` (str), `condition` (str: excellent/good/fair), `price` (float), `colors` (list[str]), `brand` (str or None), `platform` (str: depop/thredUp/poshmark). only listings scoring > 0 are in there. no score field gets attached, the score is j used internally for ranking.

**What happens if it fails or returns nothing:**
returns []. the whole body is wrapped in try/except so a missing/corrupt listings.json or a weird input gives [] instead of crashing (use `listing.get(...)` for the fields to be safe). upstream the agent treats [] as "no results" and tells me what to loosen (raise the price, drop/broaden the size, reword), it does NOT call suggest_outfit or create_fit_card on nothing.

scoring detail for claude: lowercase the query, replace every non a-z0-9 char w a space (kills "/", "-", commas), split on whitespace into a set of tokens. for each surviving listing build token sets from `title`, from `style_tags` joined, and from `description`. per query token: +1 if it appears anywhere in title|tags|desc, +1 extra if its in the title, +1 extra if its in a tag. so title-only or tag-only = 2, desc-only = 1, title+tag = 3. drop any listing scoring 0. sort by score desc, then condition (excellent > good > fair), then price asc.

---

### Tool 2: suggest_outfit

**What it does:**
takes the thrifted item i found + my wardrobe, calls the LLM (groq `llama-3.3-70b-versatile`) and returns 1 to 2 actual outfit combos. if my wardrobe has stuff it builds outfits naming real pieces i own. if my wardrobe is empty it switches to general styling advice so it never crashes and always gives me something useful.

**Input parameters:**
- `new_item` (dict): a listing dict from search_listings (the item to style). note its a LISTING so the name field is `title`, NOT `name`. inject `title`, `description`, `category`, `style_tags`, `colors`, `condition`, `price`, `brand` into the prompt.
- `wardrobe` (dict): a wardrobe dict matching wardrobe_schema.json, has an `items` key w a list. each wardrobe item has `id`, `name`, `category`, `colors`, `style_tags`, optional `notes`. the list can be empty for a new user. read it as `wardrobe.get("items", [])` so a missing key doesnt KeyError.

**What it returns:**
a non empty string. populated wardrobe = 1 to 2 specific combos that name the new item + real pieces from my closet (by their `name`) w a quick why each one works. empty wardrobe = general advice (what categories/colors/vibes pair w it, a couple example directions) w no references to pieces i dont own.

**What happens if it fails or returns nothing:**
empty wardrobe isnt an error, its the fallback branch (general advice). it never returns "" and never raises. a missing GROQ_API_KEY is a separate config thing that `_get_groq_client()` raises, not this case.

---

### Tool 3: create_fit_card

**What it does:**
takes an outfit description + the item and calls the LLM (same model, higher temp) to write a short casual OOTD caption, 2 to 4 sentences, the kind of thing id actually post. it names the item, price, and platform once each, captures the vibe, and sounds different every run.

**Input parameters:**
- `outfit` (str): the outfit text, usually straight from suggest_outfit. if its empty/whitespace the function bails early w an error string.
- `new_item` (dict): the listing dict. inject `title` (the item name), `price`, `platform`, plus `colors`/`style_tags`/`brand` for vibe. name/price/platform are the 3 facts that each show up once. note platform values are lowercase in the data (depop/poshmark/thredUp) so title-case it for the caption if i want "Depop".

**What it returns:**
on success, a 2 to 4 sentence casual caption string usable as an instagram/tiktok post. on the empty outfit guard, a descriptive error message string (not an exception), eg "cant make a fit card, no outfit was provided, run suggest_outfit first".

**What happens if it fails or returns nothing:**
empty/whitespace `outfit` returns the error string, doesnt call the LLM, doesnt raise. higher temp (~1.0) so the same input gives a different caption each time, if theyre identical i bump the temp.

---

### Additional Tools (if any)

none for the core 3. if i do stretch ill add them here and update this section first:
- `retry_search(...)` (+1): on an empty search, auto retry w loosened constraints (drop the size filter first, then raise the price) and tell me what got adjusted.
- `compare_price(item)` (+2): given an item, estimate if the price is fair vs comparable listings in the dataset (same category + overlapping style_tags), return an assessment w reasoning.

---

## Planning Loop

**How does your agent decide which tool to call next?**

single pass deterministic loop inside `run_agent`, not a multi turn LLM thing. the "planning" is the control flow deciding which tool runs next by looking at what i wrote into the session so far, and theres exactly one real decision point: the empty search branch.

how it goes:
1. parse the query into description/size/max_price w simple regex/string rules, no LLM. price = the number after "under $" / "below" / "less than" / "$" cast to float, else None. size = the token after the word "size" (eg M, XS, 8), else None. description = the query w the price phrase + size phrase + filler ("looking for", "i want", "show me") stripped out, and it falls back to the raw query if stripping leaves it empty. store all 3 in `session["parsed"]`.
2. call `search_listings(description, size, max_price)`, store the list in `session["search_results"]`.
3. THE BRANCH (the graded decision point): if `search_results` is empty, set `session["error"]` to a specific message naming the constraints i tried and RETURN the session right there. dont select an item, dont call suggest_outfit, dont call create_fit_card, those stay None. if its non empty, error stays None and it keeps going.
4. `selected_item = search_results[0]` (already the best match cuz the tool sorts by relevance). store it.
5. call `suggest_outfit(selected_item, wardrobe)`, store the string in `outfit_suggestion`. an empty wardrobe doesnt branch here, the tool handles it internally w general advice so the run stays on the happy path.
6. call `create_fit_card(outfit_suggestion, selected_item)`, store in `fit_card`. if the outfit were empty the tool returns an error string itself so no extra branch is needed.
7. return the session.

how it knows its done: no counter, no LLM deciding to stop. its structural, each tool runs at most once in a fixed order and the only fork is the empty search early return. done = it reached a return, either early (error set, all 3 outputs None) or after step 6 (error None, all 3 outputs populated).

whats actually adaptive: the tool sequence changes based on what search gives back. an impossible query runs 1 tool then stops w a helpful msg, a good query runs all 3. it does NOT fire all 3 unconditionally in the same order regardless of context.

---

## State Management

**How does information from one tool get passed to the next?**

the session dict from `_new_session()` is the single source of truth for one interaction. `run_agent` never re prompts me and never hardcodes a middle value. each step WRITES its output into the session, the next step READS its input back out, thats how data moves between tools w no re entry.

write then read:
- `_new_session` writes `query` (raw input) and `wardrobe` (passed in by gradio). set once, never mutated.
- step 2 reads `query`, writes `parsed = {description, size, max_price}`.
- step 3 reads `parsed`, writes `search_results`. reads it right back for the branch, and on empty writes `error` and returns.
- step 4 reads `search_results[0]`, writes `selected_item`. this is the key handoff, the exact same dict goes to both downstream tools.
- step 5 reads `selected_item` + `wardrobe`, writes `outfit_suggestion`.
- step 6 reads `outfit_suggestion` + `selected_item` (same dict reused, not re fetched), writes `fit_card`.
- step 7 returns the whole session. `app.py`'s `handle_query` reads `error` first (set, panel 1 shows it and the others go blank), else reads `selected_item` / `outfit_suggestion` / `fit_card` into the 3 panels.

proof its real state and not just re running the same thing: `selected_item` is read by BOTH suggest_outfit and create_fit_card, so the item i saw in the listing panel is provably the one that got styled and captioned. `outfit_suggestion` from step 5 is the literal input to step 6. `error` is the gate, when its set early the 3 output fields are guaranteed to stay None. nothing in the loop reads from a global or asks me a second time.

---

## Error Handling

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | no listing matches the parsed description/size/price, returns [] (never raises). fires the empty result branch. | stop before any LLM tool runs and show a specific msg naming what i tried + what to change, eg "no listings matched 'designer ballgown' in size XXS under $5. try dropping the size filter, raising your price ceiling, or describing it more broadly." the outfit + fit card panels stay empty. |
| suggest_outfit | wardrobe is empty (`items == []`), a new user w nothing logged so no owned pieces to pair w. | detect the empty list and call the LLM for GENERAL advice instead of returning "" or raising, eg "your wardrobe's empty so here's some general ideas: this tee leans 90s grunge, pair it w baggy or wide leg jeans + chunky boots or platform sneakers, tuck the front hem for shape." stays on the happy path, still makes a fit card, and tells me the advice is general. |
| create_fit_card | the outfit string is missing/empty/whitespace, nothing to caption. | hit the whitespace guard and return a descriptive error string instead of raising, eg "couldnt make a fit card, no outfit was available. try re running the search or picking a different item." the other panels keep what they had and the app doesnt crash. |

---

## Architecture

```
user query + wardrobe choice   (gradio: handle_query)
        |
        v
+--------------------------------------------------------------+
|                   PLANNING LOOP (run_agent)                  |
|                                                              |
|  step 1  session = _new_session(query, wardrobe)             |
|            error=None, selected_item=None,                   |
|            outfit_suggestion=None, fit_card=None             |
|                       |                                      |
|  step 2  parse query -> session["parsed"]                    |
|            {description, size, max_price}                    |
|                       |                                      |
|                       v                                      |
|  step 3  search_listings(desc, size, max_price) -------------+--> TOOL 1
|            session["search_results"] = results               |    returns list[dict]
|                       |                                      |    best match first
|              +--------+--------+                             |
|        results == []      results = [item, ...]              |
|            |                    |                            |
|            v                    v                            |
|     ERROR BRANCH        step 4  selected_item = results[0]   |
|     session["error"] =          |                            |
|       "no listings...           v                            |
|        try dropping     step 5  suggest_outfit(              |
|        size/price"                selected_item, wardrobe) --+--> TOOL 2
|            |                    |                            |    outfit str
|            |             session["outfit_suggestion"]        |    (empty wardrobe ->
|            |                    |                            |     general advice)
|            |                    v                            |
|            |          step 6  create_fit_card(               |
|            |                    outfit, selected_item) ------+--> TOOL 3
|            |                    |                            |    caption str
|            |             session["fit_card"]                 |
|            |                    |                            |
|            | early return       | step 7 return session     |
|            +--------------------+                            |
+----------------------|----------|---------------------------+
                       v          v
                  return session (single source of truth)
                            |
                            v
        handle_query maps session -> 3 gradio panels:
          error?  -> panel1 = error,         panel2 = "",  panel3 = ""
          else    -> panel1 = selected_item,  panel2 = outfit_suggestion,
                     panel3 = fit_card
```

---

## AI Tool Plan

**Milestone 3 (individual tool implementations):** tool im using is claude, one tool at a time.

- search_listings: ill give claude my Tool 1 block above (the 3 params w types, the "returns list[dict] best match first, [] on no match, never raises" contract, and the scoring detail) plus the listing field list from the `load_listings()` docstring in utils/data_loader.py. i expect a pure python fn that calls `load_listings()` (not `open()`), applies all 3 filters w None meaning skip that filter, scores by keyword overlap, drops score 0, sorts, and returns the dicts. before trusting it ill read the code and check (a) it uses load_listings not open, (b) all 3 params actually apply and None skips, (c) the no match path returns [] and never raises. then ill write `tests/test_tools.py` (theres no tests/ folder yet, the 3 tests are examples in instructions.md, i create the file) and run `pytest tests/`: results > 0 for "vintage graphic tee" / max_price=50, == [] for "designer ballgown" / size XXS / $5, and `all(price <= 10)` for "jacket" / max_price=10.

- suggest_outfit: give claude my Tool 2 block + the wardrobe item schema + "use groq llama-3.3-70b-versatile via `_get_groq_client()`". note `_get_groq_client()` only builds the client from GROQ_API_KEY, the model id gets passed at the `client.chat.completions.create(model="llama-3.3-70b-versatile")` call inside the tool, not in the helper. i expect a branch on `wardrobe.get("items")` empty vs populated. verify the empty branch returns advice not "", and that wardrobe items get formatted by name into the populated prompt. test w `get_example_wardrobe()` (expect named pieces referenced) and `get_empty_wardrobe()` (expect non empty general advice, no crash).

- create_fit_card: give claude my Tool 3 block. i expect a whitespace guard that returns an error string first, then a higher temp groq call. verify `create_fit_card("", item)` returns a string not an exception, verify the temp is raised, then run it 3x on the same item and confirm the outputs differ and each one names the item/price/platform.

**Milestone 4 (planning loop and state management):** tool im using is claude.

ill hand claude the Planning Loop section, the State Management section, and the ASCII architecture diagram together (not just a prose ask) plus the agent.py scaffold (the `_new_session` fields and the 7 numbered TODO steps in run_agent). i expect a `run_agent()` body that does the 7 steps w the empty search early return, plus a `handle_query()` in app.py that guards empty input, picks the wardrobe by radio choice, calls run_agent, and maps error to panel 1 (others empty) vs the 3 fields to the 3 panels. before trusting it ill read the code and confirm 3 things: (a) it actually branches on `search_results` being empty w an early return, (b) it does NOT call suggest_outfit/create_fit_card on the empty path (those calls are after the branch, not unconditional), (c) every cross tool value is read back out of the session, not recomputed or hardcoded. then run the 2 cases in agent.py's `__main__`: the happy "vintage graphic tee under $30" (assert error is None, all 3 fields populated, print selected_item before suggest_outfit to show its the same dict) and "designer ballgown size XXS under $5" (assert error is set, fit_card stays None). last, `python app.py` and confirm a happy query fills all 3 panels and the ballgown query shows the error only in panel 1.

---

## A Complete Interaction (Step by Step)

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

(wardrobe = the example wardrobe, which already has baggy dark wash jeans w_001 and chunky white sneakers w_007.)

**Step 1:** agent inits the session w `_new_session(query, example_wardrobe)`, then parses the query: `max_price = 30.0` (from "under $30"), `size = None` (theres no "size" word), `description = "vintage graphic tee"` (after stripping the price phrase and the "i'm looking for" / "what's out there" filler). stored in `session["parsed"]`.

**Step 2:** calls `search_listings("vintage graphic tee", None, 30.0)`. returns a ranked non empty list, top result is lst_006 "Graphic Tee, 2003 Tour Bootleg Style" ($24, depop, good condition), then lst_033 "Vintage Band Tee" ($19) and lst_002 "Y2K Baby Tee" ($18). stored in `session["search_results"]`. its non empty so `error` stays None and we dont take the error branch.

**Step 3:** `selected_item = search_results[0]` = lst_006. stored in `session["selected_item"]`. this exact dict is what both of the next tools get.

**Step 4:** calls `suggest_outfit(lst_006, example_wardrobe)`. the wardrobe has items so it builds real combos, eg pair the graphic tee w the baggy dark wash jeans (w_001) + chunky white sneakers (w_007), and throw the vintage black denim jacket (w_006) over it, roll the sleeves once. stored in `session["outfit_suggestion"]`.

**Step 5:** calls `create_fit_card(outfit_suggestion, lst_006)`. higher temp caption that names "Graphic Tee 2003 Tour Bootleg", $24, and depop, casual OOTD voice. stored in `session["fit_card"]`. returns the session, error None, all 3 fields populated.

**Final output to user:** the 3 gradio panels fill in. panel 1 (top listing) shows the formatted lst_006 (title, price, platform, condition, size, brand). panel 2 (outfit idea) shows the combos from suggest_outfit. panel 3 (fit card) shows the caption. if id typed the "designer ballgown size XXS under $5" query instead, search returns [], `error` gets set ("no listings matched..."), suggest_outfit and create_fit_card never run, and only panel 1 shows that message while panels 2 and 3 stay empty.
