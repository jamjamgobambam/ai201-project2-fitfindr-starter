# FitFindr — planning.md

> Written before implementation, updated to reflect final design.

---

## Tools

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset for secondhand items that match the user's description. Applies hard filters for size and price ceiling first, then scores each remaining listing by keyword relevance across title, style tags, category, description body, colors, and brand. Returns results sorted best-match first.

**Input parameters:**
- `description` (str): Keywords describing what the user wants, e.g. `"vintage graphic tee"`. Extracted from the natural language query after removing price/size mentions.
- `size` (str | None): Size string to filter by. Matching is case-insensitive substring — `"M"` matches `"S/M"` and `"M/L"`. Pass `None` to skip size filtering.
- `max_price` (float | None): Maximum price inclusive. Pass `None` to skip price filtering.

**What it returns:**
`list[dict]` — matching listing dicts sorted by relevance score (highest first). Each dict contains: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns an empty list `[]` when nothing matches — never raises an exception.

**What happens if it fails or returns nothing:**
If the list is empty, the planning loop sets `session["error"]` with a specific message that tells the user which filter to relax (price ceiling too low, size too restrictive, or keywords too narrow), then returns immediately. `suggest_outfit` and `create_fit_card` are never called.

---

### Tool 2: suggest_outfit

**What it does:**
Given a specific thrifted item and the user's wardrobe, calls the Groq LLM (llama-3.3-70b-versatile) to suggest 1–2 complete outfit combinations. If the wardrobe is empty, it gives general styling advice instead of wardrobe-specific combinations.

**Input parameters:**
- `new_item` (dict): A listing dict returned by `search_listings` — the item the user is considering buying.
- `wardrobe` (dict): User wardrobe dict with an `"items"` key. Each item has `name`, `category`, `colors`, and optional `notes`. May be empty — handled gracefully.

**What it returns:**
`str` — 4–6 sentences of outfit advice. Names specific wardrobe pieces by name when the wardrobe is populated. Returns an error string prefixed with `[suggest_outfit error]` if the LLM call fails — never raises an exception.

**What happens if it fails or returns nothing:**
Empty wardrobe: detected before the LLM call; a different prompt is sent asking for general styling advice. LLM failure: returns an error string. The planning loop keeps the error string in `session["outfit_suggestion"]` and continues to `create_fit_card` so the user still sees the listing result.

---

### Tool 3: create_fit_card

**What it does:**
Calls the Groq LLM to generate a short, casual Instagram-style caption for the outfit — something a real person would post with a thrift-find photo. Uses temperature 0.92 so each call produces a different caption even for the same input.

**Input parameters:**
- `outfit` (str): The outfit suggestion string from `suggest_outfit`.
- `new_item` (dict): The listing dict for the thrifted item — used to include item name, price, and platform in the caption.

**What it returns:**
`str` — a 2–4 sentence caption that mentions the item name, price, and platform exactly once each, with 1–3 emojis, no hashtags. Returns a descriptive error message string if `outfit` is empty or the LLM fails — never raises an exception.

**What happens if it fails or returns nothing:**
Empty `outfit` string: caught by a guard clause before the LLM call; returns a message explaining the issue. LLM failure: returns an error string prefixed with `[create_fit_card error]`.

---

## Planning Loop

The loop is conditional — it branches based on what `search_listings` returns rather than calling all three tools in a fixed sequence:

```
1. _parse_query(query)
       │
       └─► session["parsed"] = {description, size, max_price}
       │
2. search_listings(description, size, max_price)
       │
       ├── results == [] ?
       │       └─► session["error"] = specific message
       │           RETURN EARLY (suggest_outfit never called)
       │
       └── results non-empty?
               └─► session["selected_item"] = results[0]
               │
3. suggest_outfit(selected_item, wardrobe)
               └─► session["outfit_suggestion"] = "..."
               │
4. create_fit_card(outfit_suggestion, selected_item)
               └─► session["fit_card"] = "..."
               │
5. return session
```

**Key decisions:**
- After `search_listings`: if empty → set error and return immediately. This is the only hard branch.
- `suggest_outfit` LLM failure: the error string is kept in the session but the loop continues to `create_fit_card`. The listing result is still useful even without a fit card.
- The loop never retries automatically — it tells the user what to change and lets them re-query.

---

## State Management

All state for one interaction lives in a session dict created at the start of `run_agent()`:

```python
session = {
    "query":             query,       # original user input
    "parsed":            {},          # description / size / max_price after parsing
    "search_results":    [],          # full ranked list from search_listings
    "selected_item":     None,        # results[0] → passed into suggest_outfit
    "wardrobe":          wardrobe,    # stored for reference
    "outfit_suggestion": None,        # output of suggest_outfit → passed into create_fit_card
    "fit_card":          None,        # output of create_fit_card
    "error":             None,        # set on early exit; checked first by handle_query
}
```

Each tool writes its output into the session dict. The next tool reads from the dict — no re-prompting the user, no hardcoded values. `handle_query()` in `app.py` maps the final session dict to the three Gradio output panels.

---

## Error Handling

| Tool | Failure mode | Agent response |
|---|---|---|
| `search_listings` | No listings match (empty list) | Sets `session["error"]`: "No listings matched your search. Try raising the price limit above $X." or "Or remove the size filter ('M') to see more options." Returns immediately — LLM tools never called with empty input. |
| `suggest_outfit` | Empty wardrobe (`items == []`) | Sends a different LLM prompt requesting general styling advice for the item. Returns a useful string, not an error. |
| `suggest_outfit` | LLM call fails | Returns `"[suggest_outfit error] ..."` string. Loop continues so the found listing is still shown. |
| `create_fit_card` | `outfit` is empty or blank | Guard clause returns a descriptive message string before the LLM is called. |
| `create_fit_card` | LLM call fails | Returns `"[create_fit_card error] ..."` string. Listing and outfit suggestion still shown. |

---

## Architecture

```
User query (natural language)
    │
    ▼
_parse_query(query)
    Regex extracts: description, size, max_price
    │
    ▼
search_listings(description, size, max_price)
    Hard filter: price ≤ max_price, size substring match
    Score: title(3×), tags(2×), category(2×), desc(1×), colors(1×), brand(2×)
    │
    ├── results == [] ──────────────────────────────────────────────────┐
    │                                                                   │
    │   session["error"] = specific advice message                      │
    │   RETURN session                                                  │
    │                                                                   │
    └── results non-empty                                               │
            │                                                           │
            ▼                                                           │
    session["selected_item"] = results[0]                               │
            │                                                           │
            ▼                                                           │
    suggest_outfit(selected_item, wardrobe)                             │
        wardrobe empty? → general styling prompt                        │
        wardrobe populated? → wardrobe-specific outfit prompt           │
            │                                                           │
            ▼                                                           │
    session["outfit_suggestion"] = "..."                                │
            │                                                           │
            ▼                                                           │
    create_fit_card(outfit_suggestion, selected_item)                   │
        outfit empty? → return error string (no LLM call)              │
        otherwise → LLM generates caption (temp 0.92)                  │
            │                                                           │
            ▼                                                           │
    session["fit_card"] = "..."                                         │
            │                                                           │
            ▼                                                           ▼
    return session ◄────────────────────────────────────────────────────┘
            │
            ▼
    handle_query() maps session → 3 Gradio output panels
        panel 1: formatted listing text  (or error message)
        panel 2: outfit suggestion       (or "")
        panel 3: fit card caption        (or "")
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

- **`search_listings`:** Gave Claude the Tool 1 spec block (inputs, return value, failure mode) and the listing dict structure from `listings.json`. Asked it to implement using `load_listings()` from the data loader. Reviewed generated code for: does it filter by all three parameters? Does it handle empty results without raising? Tested with 3 queries before accepting. Revised the scoring weights — generated code used equal weights; changed title to 3× and added separate brand scoring at 2×.

- **`suggest_outfit`:** Gave Claude the Tool 2 spec and the wardrobe schema from `wardrobe_schema.json`. Asked it to implement with empty-wardrobe branching. Verified the two distinct prompts (empty vs. populated wardrobe) before using. Rewrote the empty-wardrobe prompt — generated version returned a hardcoded string; replaced with an actual LLM call for general styling advice.

- **`create_fit_card`:** Gave Claude the Tool 3 spec. Reviewed generated prompt for caption rules. Added explicit rules: mention price and platform exactly once each, no hashtags, 1–3 emojis max. Set temperature to 0.92 (generated code used 0.7 — too uniform across calls).

**Milestone 4 — Planning loop and state management:**

Gave Claude the agent diagram above and both the Planning Loop and State Management sections. Reviewed generated `run_agent()` for: does it branch on empty results? Does it store values in the session dict? Does it avoid calling all tools unconditionally? Revised the early-exit error message from a generic `"No results"` to a conditional that checks which filters were active and gives specific advice.

---

## A Complete Interaction (Step by Step)

**Example user query:** `"I'm looking for a vintage graphic tee under $30, size M"`

**Step 1 — Parse query:**
`_parse_query` extracts: `description="vintage graphic tee"`, `size="M"`, `max_price=30.0`. Stores in `session["parsed"]`.

**Step 2 — Search listings:**
`search_listings("vintage graphic tee", size="M", max_price=30.0)` is called.
- Hard filter: removes listings with `price > 30` and listings where `"m"` is not in the `size` field (case-insensitive).
- Scoring: "vintage" matches title + style tags on multiple listings; "graphic" and "tee" match title on `lst_006` (Graphic Tee — 2003 Tour Bootleg, $24, size L) but `L` doesn't contain `"m"`, so it's filtered out. `lst_024` (Vintage Polo Shirt — Forest Green, $18, size M) passes the size filter and scores well on "vintage".
- Top result: a matching item with `size` containing `"M"` and `price ≤ 30`.
- `session["selected_item"]` = that listing dict.

**Step 3 — Suggest outfit:**
`suggest_outfit(selected_item, example_wardrobe)` is called with the found item and the user's 10-item wardrobe. The LLM receives the item details and specific wardrobe pieces. Returns something like: "Pair this with your wide-leg jeans and white canvas sneakers for a relaxed 90s look. Tuck the front of the tee in slightly and add your brown leather belt for shape."
`session["outfit_suggestion"]` = that string.

**Step 4 — Fit card:**
`create_fit_card(outfit_suggestion, selected_item)` is called. The LLM generates a caption like: "thrifted this vintage polo off thredUp for $18 and honestly it just works 🌿 wide legs + white canvas and we're done. full fit in my stories."
`session["fit_card"]` = that string.

**Final output to user:**
- Panel 1 (listing): formatted item details — title, price, platform, size, condition, description
- Panel 2 (outfit): the 4–6 sentence styling suggestion naming specific wardrobe pieces
- Panel 3 (fit card): the 2–3 sentence shareable caption

**Error path (same query, impossible constraints):**
Query: `"designer ballgown size XXS under $5"` → `search_listings` returns `[]` → `session["error"]` = `"No listings matched your search. Try raising the price limit above $5. Or remove the size filter ('XXS') to see more options."` → returned in panel 1, panels 2 and 3 are empty. `suggest_outfit` and `create_fit_card` are never called.