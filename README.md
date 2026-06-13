# FitFindr

A multi-tool AI agent that helps users find secondhand clothing and figure out how to wear it. Given a natural language query, FitFindr searches a dataset of thrift listings, suggests outfit combinations based on the user's wardrobe, and generates a shareable fit card caption — handling failures gracefully at every step.

---

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root (never commit this):
```
GROQ_API_KEY=your_key_here
```

Run the Gradio interface:
```bash
python app.py
```

Then open the URL shown in your terminal (usually `http://localhost:7860`).

---

## Tool Inventory

### `search_listings(description, size, max_price)`

**Purpose:** Searches the mock listings dataset for items matching the user's description, with optional hard filters for size and price ceiling.

**Inputs:**
- `description` (str) — keywords describing what the user wants (e.g. `"vintage graphic tee"`)
- `size` (str | None) — size string to filter by; matching is case-insensitive substring so `"M"` matches `"S/M"` and `"M/L"`; pass `None` to skip size filtering
- `max_price` (float | None) — maximum price inclusive; pass `None` to skip price filtering

**Output:** `list[dict]` — matching listing dicts sorted by relevance score (best match first). Returns an empty list `[]` when nothing matches. Never raises an exception.

Each dict in the list contains: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`.

**Relevance scoring:** tokens from `description` are matched against listing fields with weighted points — title (3×), style tags (2×), category (2×), description body (1×), colors (1×), brand (2×). Items with a score of zero are excluded from results.

---

### `suggest_outfit(new_item, wardrobe)`

**Purpose:** Given a thrifted item and the user's wardrobe, suggests one or two complete outfit combinations using specific wardrobe pieces, including a styling detail per outfit.

**Inputs:**
- `new_item` (dict) — a listing dict returned by `search_listings` (the item the user is considering)
- `wardrobe` (dict) — user wardrobe with an `"items"` key containing a list of wardrobe item dicts; each item has `name`, `category`, `colors`, and optional `notes`

**Output:** `str` — 4–6 sentence outfit suggestion. If the wardrobe is empty (`items` is `[]`), returns general styling advice for the item instead of wardrobe-specific combinations. Returns an error string prefixed with `[suggest_outfit error]` if the LLM call fails — does not raise an exception.

---

### `create_fit_card(outfit, new_item)`

**Purpose:** Generates a short, casual Instagram-style caption for the outfit — the kind of thing someone would post with a OOTD photo. Produces different output each call for the same inputs (temperature 0.92).

**Inputs:**
- `outfit` (str) — the outfit suggestion string returned by `suggest_outfit`
- `new_item` (dict) — the listing dict for the thrifted item

**Output:** `str` — a 2–4 sentence caption that naturally mentions the item name, price, and platform exactly once each, with 1–3 emojis, no hashtags. Returns a descriptive error message string if `outfit` is empty or blank — does not raise an exception.

---

## How the Planning Loop Works

The planning loop in `run_agent()` is **conditional, not sequential** — it branches based on what each tool returns rather than calling all three tools in a fixed order.

```
run_agent(query, wardrobe)
    │
    ▼
Step 1: _parse_query(query)
    Extract description, size, max_price via regex.
    Store in session["parsed"].
    │
    ▼
Step 2: search_listings(description, size, max_price)
    │
    ├── results == [] ?
    │       │
    │       └── SET session["error"] with specific advice
    │           (raise price ceiling / remove size filter / try different keywords)
    │           RETURN EARLY — suggest_outfit and create_fit_card are NOT called
    │
    └── results non-empty?
            │
            ▼
        session["selected_item"] = results[0]
            │
            ▼
Step 3: suggest_outfit(selected_item, wardrobe)
    Store result in session["outfit_suggestion"].
    If result starts with "[suggest_outfit error]", keep the error text
    visible in the UI but continue — the listing was found successfully.
            │
            ▼
Step 4: create_fit_card(outfit_suggestion, selected_item)
    Store result in session["fit_card"].
            │
            ▼
Step 5: Return completed session dict
```

The key conditional is after `search_listings`: if results are empty the agent returns immediately with an error message and never calls `suggest_outfit` with empty input. This prevents the LLM from generating an outfit for a nonexistent item.

The query parser (`_parse_query`) runs before the search and handles many natural language price formats (`under $30`, `below 30`, `max $30`, `$30 or less`) and size formats (`size M`, standalone `M`, `W30 L32`) so users don't need structured input.

---

## State Management

All state for a single interaction lives in a **session dict** created at the start of `run_agent()`:

```python
session = {
    "query":             query,          # original user input
    "parsed":            {},             # extracted description / size / max_price
    "search_results":    [],             # full list from search_listings
    "selected_item":     None,           # results[0] — flows into suggest_outfit
    "wardrobe":          wardrobe,       # passed in, stored for reference
    "outfit_suggestion": None,           # return value of suggest_outfit → flows into create_fit_card
    "fit_card":          None,           # return value of create_fit_card
    "error":             None,           # set on early termination; check this first
}
```

**How data flows between tools:**
1. `_parse_query` writes to `session["parsed"]`; the planning loop reads `parsed["description"]`, `parsed["size"]`, `parsed["max_price"]` to call `search_listings`
2. `search_listings` result is stored as `session["selected_item"] = results[0]`; this exact dict is passed directly into `suggest_outfit` — no re-entry, no re-prompting
3. `suggest_outfit` result is stored as `session["outfit_suggestion"]`; this string is passed directly into `create_fit_card`
4. The final session dict is returned to `handle_query()` in `app.py`, which maps the fields to the three Gradio output panels

The session dict is the single source of truth. No global variables, no side effects between calls.

---

## Error Handling

| Tool | Failure mode | What the agent does |
|---|---|---|
| `search_listings` | No listings match (empty list `[]`) | Sets `session["error"]` with a specific message: tells the user what filter to relax (price ceiling too low, size too restrictive, or keywords too narrow). Returns immediately — does **not** call `suggest_outfit`. |
| `suggest_outfit` | LLM call fails (network error, rate limit, etc.) | Returns an error string starting with `[suggest_outfit error]`. The planning loop keeps this string in `session["outfit_suggestion"]` and continues to `create_fit_card` — the listing result is still shown to the user. |
| `suggest_outfit` | Empty wardrobe | Detected before the LLM call. Sends a different prompt asking for general styling advice rather than wardrobe-specific combinations. Never crashes. |
| `create_fit_card` | `outfit` is empty or blank | Detected with a guard clause before the LLM call. Returns a descriptive error message string explaining the issue. Does not raise an exception. |
| `create_fit_card` | LLM call fails | Returns an error string starting with `[create_fit_card error]`. The listing and outfit suggestion are still available to the user. |

**Concrete test examples:**

```bash
# Empty results — confirmed returns [] with no exception
python -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"
# Output: []

# Full agent on the same query — confirmed error message, no crash
python agent.py
# Output: "No listings matched your search. Try raising the price limit above $5.
#          Or remove the size filter ('XXS') to see more options."

# Empty wardrobe — confirmed returns styling advice string, not an exception
python -c "
from tools import search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe
r = search_listings('vintage polo shirt', size='M', max_price=50)
print(suggest_outfit(r[0], get_empty_wardrobe()))
"

# Empty outfit string — confirmed returns error message string
python -c "
from tools import search_listings, create_fit_card
r = search_listings('vintage graphic tee', size=None, max_price=50)
print(create_fit_card('', r[0]))
"
# Output: "Couldn't create a fit card — no outfit suggestion was provided..."
```

---

## Spec Reflection

**One way the spec helped:** The spec's requirement to handle `search_listings` returning an empty list forced a clean early-exit design in the planning loop. Because the spec explicitly said "the agent must not call `suggest_outfit` with empty input," the conditional branch after `search_listings` became a first-class design decision rather than an afterthought. This made the error messages significantly more useful — instead of a generic failure, the agent tells the user specifically which filter to relax.

**One way implementation diverged from the spec:** The spec describes `create_fit_card` as taking only `outfit` and `new_item`. During implementation it became clear that generating a good caption required knowing the item's price and platform specifically (so the caption could mention "found this for $22 on Depop" naturally). The function signature already included `new_item` for this reason, but the prompt engineering needed to be much more explicit than the spec anticipated — specifically instructing the LLM to mention price and platform exactly once each, or it would either omit them entirely or repeat them awkwardly. The final prompt includes that as an explicit rule, which wasn't in the original spec.

---

## AI Usage

**Instance 1 — `search_listings` relevance scoring**

I gave Claude the tool spec from `planning.md` (inputs, return value, failure mode) and the structure of a listing dict from `listings.json`, and asked it to implement a scoring function that weighted matches across different fields. The generated code used a flat token-match approach with equal weights across all fields. I overrode this: title matches should score 3× because a user searching "vintage graphic tee" cares most about the title saying "graphic tee," not just the description body containing those words. I also added brand matching (2×) separately because the original scoring folded brand into the description match, which underweighted it. The final weighted scoring (`title 3×, style_tags 2×, category 2×, description 1×, brand 2×`) came from manually testing a dozen queries and noticing which results were ranking incorrectly.

**Instance 2 — planning loop early termination**

I gave Claude the agent diagram from `planning.md` and asked it to implement `run_agent()`. The generated code called all three tools unconditionally and only checked for errors at the end. I revised the structure so `search_listings` returning an empty list triggers an immediate `return session` before `suggest_outfit` is ever called. I also added the specific error message logic — the generated code returned a generic `"No results found"` string; I replaced it with a conditional that checks whether `max_price` or `size` filters were active and tailors the message to tell the user exactly which constraint to relax. This required reading the `parsed` dict in the error branch, which the generated code didn't do.

**Instance 3 — `suggest_outfit` prompt branching**

The spec says `suggest_outfit` must handle an empty wardrobe. I asked Claude to add this case to the function. The generated code returned a hardcoded string like `"No wardrobe provided — try adding some items."` I overrode this entirely: an empty wardrobe is a real use case (a new user), not an error. I replaced it with a separate LLM prompt that asks for general styling advice for the item — what types of pieces pair with it, what aesthetic it suits, one specific styling tip. This produces a genuinely useful response rather than an error message for a perfectly valid input.

---

## Running Tests

```bash
pytest tests/
```

Tests cover: search returning results, search returning empty list, price filter correctness, empty wardrobe handling, empty outfit string guard in `create_fit_card`.