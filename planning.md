# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches `listings.json` for items that match the user's description, size, and max price. It returns the best matches first.

**Input parameters:**
- `description` (str): Keywords or phrase describing what the user wants, such as `"vintage graphic tee"` or `"black combat boots"`.
- `size` (str): Size filter from the query, such as `"M"` or `"US 8"`.
- `max_price` (float): Maximum price from the query, such as `30.0`.

**What it returns:**
A list of listing dictionaries, best match first. Each listing has `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

**What happens if it fails or returns nothing:**
If nothing matches, return `[]`. The agent tells the user no listings were found, suggests broader search terms, no size filter, or a higher budget, and stops before `suggest_outfit`.

---

### Tool 2: suggest_outfit

**What it does:**
Suggests how to style the selected listing with the user's wardrobe. If possible, it names specific closet items.

**Input parameters:**
- `new_item` (dict): The selected listing from `search_listings`, using the listing fields described above.
- `wardrobe` (dict): A wardrobe object with an `items` list. Each wardrobe item has `id` (str), `name` (str), `category` (str), `colors` (list[str]), `style_tags` (list[str]), and optional `notes` (str or None).

**What it returns:**
An outfit suggestion string. With a filled wardrobe, it names matching closet pieces; with an empty wardrobe, it gives general styling advice.

**What happens if it fails or returns nothing:**
If the wardrobe is empty, the agent keeps the listing result and says it cannot personalize the outfit yet. It can give general advice or ask the user to add wardrobe items.

---

### Tool 3: create_fit_card

**What it does:**
Creates a short fit-card caption from a completed outfit. It runs only when the app needs a fit card or the user asks for a caption, post, or fit card.

**Input parameters:**
- `outfit` (...): The completed outfit information returned by `suggest_outfit`.

**What it returns:**
A short caption or fit-card text.

**What happens if it fails or returns nothing:**
If the outfit is empty or incomplete, return an error message. The agent still shows the listing and outfit suggestion, but skips the fit card.

---

### Additional Tools (if any)

None. FitFindr only needs `search_listings`, `suggest_outfit`, and `create_fit_card`.

---

## Planning Loop

**How does your agent decide which tool to call next?**
The agent starts a session and parses the query into `description`, `size`, and `max_price`.

First it calls `search_listings(description, size, max_price)`. If the results list is empty, it sets `session["error"]`, leaves the other result fields empty, and returns early. If results exist, it saves them in `session["search_results"]`, sets `session["selected_item"] = results[0]`, and moves on.

Next it calls `suggest_outfit(new_item=session["selected_item"], wardrobe=session["wardrobe"])`. If the suggestion is empty, it sets `session["error"]` and returns with the listing results still saved. If the suggestion works, it saves it in `session["outfit_suggestion"]`.

It calls `create_fit_card(outfit)` only if the app needs a fit card or the user asks for one. If the fit card fails, the agent keeps the listing and outfit suggestion and stores a short fit-card error. Then it returns the session.

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Say: "I couldn't find listings for that. Try a higher budget, no size filter, or broader words like 'vintage top'." Set `session["error"]` and stop. |
| suggest_outfit | Wardrobe is empty | Say: "I found a listing, but I need closet items to personalize the outfit." Give general styling advice or ask the user to add wardrobe items. |
| create_fit_card | Outfit input is missing or incomplete | Say: "I need a complete outfit before I can make a fit card." Show the listing and outfit notes instead. |

---

## Architecture

```text
User query + wardrobe choice
        |
        v
Planning Loop
  - create session
  - parse query into description, size, max_price
        |
        | parsed search filters
        v
search_listings(description, size, max_price)
        |
        | results = []
        +-----------------------> Session: error = "No listings found"
        |                         Return session early
        |
        | results = [item, ...]
        v
Session State
  - search_results = results
  - selected_item = results[0]
        |
        | selected_item + wardrobe
        v
suggest_outfit(new_item, wardrobe)
        |
        | outfit missing or empty
        +-----------------------> Session: error = "Could not create outfit"
        |                         Return session with listing results
        |
        | outfit suggestion text
        v
Session State
  - outfit_suggestion = outfit
        |
        | if fit card is needed: outfit
        v
create_fit_card(outfit)
        |
        | fit card missing or incomplete
        +-----------------------> Session: fit_card = error message
        |                         Return session with listing + outfit
        |
        | fit card text
        v
Session State
  - fit_card = caption text
        |
        v
Return session to app.py
  - selected listing panel
  - outfit idea panel
  - fit card panel, if created
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**
I will use ChatGPT or Claude for one tool at a time in `tools.py`.

For `search_listings`, I will give it the Tool 1 block, the listings fields from `utils/data_loader.py`, and the function stub. I expect code that uses `load_listings()`, filters by `description`, `size`, and `max_price`, sorts best matches first, and returns `[]` when nothing matches. I will test a normal query, a size query, and a no-results query.

For `suggest_outfit`, I will give it the Tool 2 block, `wardrobe_schema.json`, and the function stub. I expect code that handles both example and empty wardrobes and returns a useful outfit suggestion. I will test with `get_example_wardrobe()` and `get_empty_wardrobe()`.

For `create_fit_card`, I will give it the Tool 3 block and the function stub. I expect code that makes a short caption and returns a clear message when the outfit is missing. I will test it with a normal outfit and an empty outfit.

**Milestone 4 — Planning loop and state management:**
I will use ChatGPT or Claude to implement `run_agent()` in `agent.py`. I will give it the Planning Loop, State Management, Error Handling, Architecture diagram, Complete Interaction, and `_new_session()` from `agent.py`.

I expect it to parse the query, call `search_listings`, stop early if there are no results, choose `results[0]`, call `suggest_outfit`, and call `create_fit_card` only when needed. I will check that each result is saved in the right session key, then test `run_agent()` with an example wardrobe, an empty wardrobe, and a no-results query.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1: Search listings**
The query asks what is available, so FitFindr calls `search_listings(description="vintage graphic tee", size="", max_price=30.0)`. Example return:

1. `Graphic Tee — 2003 Tour Bootleg Style` — $24, Depop, good condition
2. `Vintage Band Tee — Faded Grey` — $19, Depop, fair condition
3. `Y2K Baby Tee — Butterfly Print` — $18, Depop, excellent condition

FitFindr stores these in `session["search_results"]` and sets `session["selected_item"]` to the first result.

**Step 2: Suggest outfit**
The query asks how to style it, so FitFindr calls `suggest_outfit(new_item=session["selected_item"], wardrobe=session["wardrobe"])`. Example return: "Pair the bootleg-style graphic tee with your baggy jeans and chunky sneakers. Add your black denim jacket for more structure."

FitFindr stores this in `session["outfit_suggestion"]`.

**Step 3: Respond to user**
FitFindr does not call `create_fit_card` because the user did not ask for a fit card. It combines the listings and outfit idea into the final response.

**Final output to user:**
The user sees the top 3 listings, the best pick, and a styling idea. Example: "I found 3 good options under $30. My top pick is `Graphic Tee — 2003 Tour Bootleg Style` on Depop for $24. Style it with baggy jeans, chunky sneakers, and a black denim jacket."

**Error path:**
If `search_listings` returns nothing, FitFindr says what to try differently and stops. If the wardrobe is empty, FitFindr still shows the listings and gives general styling advice or asks for wardrobe details.
