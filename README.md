# FitFindr

A secondhand clothing discovery agent that searches listings, suggests outfits using your wardrobe, and generates a shareable fit card — all from a single natural language query.

---

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root with your Groq API key (free at [console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=your_key_here
```

Run the app:

```bash
python app.py
```

Open the URL shown in your terminal (usually `http://localhost:7860`).

---

## Tool Inventory

### Tool 1: `search_listings`

| Field | Detail |
|-------|--------|
| **File** | `tools.py` |
| **Inputs** | `description: str` — keywords from the user query (e.g. `"vintage graphic tee"`); `size: str \| None` — size string to filter on (e.g. `"M"`), case-insensitive; `max_price: float \| None` — inclusive price ceiling |
| **Output** | `list[dict]` — matching listing dicts sorted by keyword relevance (best match first). Each dict has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Empty list if nothing matches. |
| **Purpose** | Filters the 40-item mock dataset by hard constraints (price, size) then ranks survivors by keyword overlap with the description. Pure Python — no LLM call. |

### Tool 2: `suggest_outfit`

| Field | Detail |
|-------|--------|
| **File** | `tools.py` |
| **Inputs** | `new_item: dict` — a listing dict from `search_listings`; `wardrobe: dict` — user's wardrobe with an `items` key (may be empty) |
| **Output** | `str` — 1–2 outfit suggestions as natural language. Never empty. |
| **Purpose** | Calls Groq (llama-3.3-70b-versatile, temp 0.7) with the new item's attributes and the user's existing wardrobe items. If the wardrobe is empty, asks for general styling advice instead of referencing specific pieces. |

### Tool 3: `create_fit_card`

| Field | Detail |
|-------|--------|
| **File** | `tools.py` |
| **Inputs** | `outfit: str` — the suggestion string from `suggest_outfit`; `new_item: dict` — the listing dict |
| **Output** | `str` — a 2–4 sentence Instagram/TikTok-style caption that mentions item name, price, and platform once each. |
| **Purpose** | Calls Groq (temp 1.0 for variety) to generate a casual, shareable caption summarizing the outfit vibe. If `outfit` is empty, returns an error string without raising an exception. |

---

## How the Planning Loop Works

The planning loop in `agent.py` is **linear and deterministic** — it always calls tools in the same order and makes decisions about whether to continue or abort based on intermediate results.

```
User query
    │
    ▼
Step 1 — Parse query (regex)
    Extract description, size, max_price from free text
    │
    ▼
Step 2 — search_listings(description, size, max_price)
    │
    ├── Empty results? → set session["error"], return early (no LLM calls wasted)
    │
    ▼
Step 3 — Select top result (index 0 of sorted list)
    │
    ▼
Step 4 — suggest_outfit(selected_item, wardrobe)
    │
    ▼
Step 5 — create_fit_card(outfit_suggestion, selected_item)
    │
    ▼
Return completed session
```

**Key decisions the agent makes:**

1. **Parse or fail early.** Before touching any tool, the agent extracts structured parameters from the user's raw text using regex (`size\s+([A-Z0-9/]+)`, `under\s+\$?([\d.]+)`). Anything not captured stays in `description`. This keeps parsing logic out of the tools themselves.

2. **Gate on search results.** If `search_listings` returns an empty list, the agent sets `session["error"]` with a human-readable message and returns immediately. It does not call the LLM tools — there is no point generating outfit suggestions for an item that doesn't exist.

3. **Pick the best match automatically.** The agent always selects `results[0]`, which is the listing with the highest keyword-overlap score. The user doesn't need to choose; the ranking is done in `search_listings`.

4. **Let the LLM tools adapt to wardrobe state.** `suggest_outfit` receives the wardrobe as-is. If it's empty, the prompt to the LLM is different ("give general styling advice") rather than failing. The planning loop itself doesn't branch on this — it delegates the graceful degradation to the tool.

5. **Terminate normally after `create_fit_card`.** There is no retry loop. One query → one result → one outfit → one fit card. The session dict is the return value so the caller (`app.py`) can inspect any field.

---

## State Management

All state for a single interaction lives in a **session dict** initialized by `_new_session()`:

```python
{
    "query":             str,   # original user input, never modified
    "parsed":            dict,  # {description, size, max_price} extracted by regex
    "search_results":    list,  # all matching listings from search_listings
    "selected_item":     dict,  # results[0] — the top match
    "wardrobe":          dict,  # user's wardrobe, passed through unchanged
    "outfit_suggestion": str,   # output of suggest_outfit
    "fit_card":          str,   # output of create_fit_card
    "error":             str,   # set on early termination, None otherwise
}
```

State flows **forward only** — each step reads from the session and writes its output back. No tool reads a field it wrote itself. The session is created fresh for every `run_agent()` call, so there is no cross-session leakage.

`app.py` reads from the session at the end: if `session["error"]` is set it shows the error in panel 1 and leaves panels 2 and 3 blank; otherwise it formats `session["selected_item"]` into a listing summary and passes `session["outfit_suggestion"]` and `session["fit_card"]` directly to the remaining panels.

---

## Error Handling

| Tool | Failure mode | What the agent does | Concrete example from testing |
|------|-------------|---------------------|-------------------------------|
| `search_listings` | No listings match filters | Sets `session["error"]` to a user-friendly message; returns session immediately without calling LLM tools | Query `"designer ballgown size XXS under $5"` — price filter removes all 40 listings, score step yields empty list, agent returns: *"Unfortunately, no listings matched your search. Try a different description, size, or price range."* Panels 2 and 3 stay blank. |
| `suggest_outfit` | Wardrobe is empty | Sends a different prompt to the LLM asking for general styling advice rather than wardrobe-specific pairings | With `get_empty_wardrobe()`, the tool receives `wardrobe["items"] == []` and falls into the empty-wardrobe branch, returning suggestions like "pair with high-waisted mom jeans and platform sneakers for a Y2K-inspired look." No exception raised. |
| `create_fit_card` | `outfit` argument is empty or whitespace | Returns a descriptive error string immediately, no LLM call | If `suggest_outfit` somehow returned `""` (e.g. during unit testing with a mock), `create_fit_card` returns: *"Error: outfit description is missing or empty. Please generate an outfit suggestion first before creating a fit card."* — no crash, no API charge. |
| Query parsing | Size or price not present in query | Regex returns `None`; tools receive `None` and skip those filters | Query `"flowy midi skirt"` — no size or price mentioned, both parse to `None`, `search_listings` applies only keyword scoring, returns broader results. |

---

## Spec Reflection

**What matched the spec:** The three-tool linear pipeline, the session dict as shared state, and the early-termination pattern on empty search results all matched what I planned in `planning.md` before writing code.

**What changed from the original plan:** The planning doc described a retry loop where `create_fit_card` would ask the user for another outfit if the caption couldn't be generated. In practice, the LLM never returns an empty string for a non-empty input — so the loop would never trigger and just added complexity. I replaced it with a guard clause that returns an error string if `outfit` is empty, which covers the only realistic failure path (a caller passing bad input directly).

The planning doc also described tracking "visited listings" across calls to avoid suggesting the same item twice. Since `run_agent()` creates a fresh session per call there is no cross-session history to deduplicate — this was over-engineering for the single-query use case the interface actually supports.

**Tradeoff I'd revisit:** The regex parser is brittle — it only catches `"size M"` and `"under $30"` patterns. A query like `"medium-sized vintage tee, budget around 25 dollars"` would not extract size or price. A one-shot LLM parse step would handle more natural phrasing, at the cost of one extra API call and latency on every query. Given the demo scope, regex was the right call.

---

## AI Usage

### Instance 1 — Implementing the three tools

**Input given:** I opened `planning.md` (specifically the Tools section with all four fields per tool and the Architecture diagram) and `tools.py` in Claude Code and asked it to implement `search_listings`, `suggest_outfit`, and `create_fit_card` according to the spec.

**What it produced:** Implementations that matched the function signatures. For `search_listings`, Claude generated keyword scoring by concatenating all text fields and counting overlap — which matched my intent. For `suggest_outfit`, it generated the wardrobe-empty branch but used `item['colors'][0]` directly without a guard for items missing the `colors` field, which would crash on malformed wardrobe data.

**What I changed:** I added `item.get('colors', ['unknown'])[0] if item.get('colors') else 'unknown'` in the wardrobe summary formatting to handle wardrobe items without a `colors` field gracefully. I also bumped `create_fit_card`'s temperature from 0.7 (Claude's default) to 1.0 because the spec called for captions that "sound different each time."

### Instance 2 — Implementing the planning loop

**Input given:** I provided Claude with the Planning Loop, State Management, and Error Handling sections of `planning.md`, plus the `_new_session()` stub and the tool signatures, and asked it to implement `run_agent()`.

**What it produced:** A correct sequential loop with the early-return on empty results. However, it placed the `import re` statement inside `run_agent()` rather than at the module top level, and it implemented the "visited listings" deduplication from my planning doc (maintaining a `seen_ids` set across steps).

**What I changed:** Moved `import re` to the top of the function (acceptable for a single-file module, avoids module-level import order issues). Removed the `seen_ids` logic entirely — within a single `run_agent()` call there's only one search and one selected item, so deduplication is meaningless. This was the over-engineering I noted in the spec reflection above.
