# FitFindr — Starter Kit

This starter kit contains everything you need to begin Project 2.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── planning.md                # Your planning template — fill this out first
└── requirements.txt           # Python dependencies
```

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Tool Inventory

The agent orchestrates three tools, all defined in `tools.py`. The inputs and
return types below match the actual function signatures in the code.

### 1. `search_listings`

- **Purpose:** Search the mock listings dataset for items matching a free-text
  description, scoring by keyword overlap and applying optional size/price
  filters. Returns matches sorted by relevance (best first).
- **Signature:** `search_listings(description: str, size: str | None = None, max_price: float | None = None) -> list[dict]`
- **Inputs:**
  - `description` (`str`): keywords describing the desired item (e.g. `"vintage graphic tee"`).
  - `size` (`str | None`, default `None`): size to filter by; case-insensitive substring match (e.g. `"M"` matches `"S/M"`). `None` skips size filtering.
  - `max_price` (`float | None`, default `None`): inclusive price ceiling. `None` skips price filtering.
- **Output:** `list[dict]` — matching listing dicts, highest relevance first. Returns an empty list when nothing matches (never raises). Each dict has: `id`, `title`, `description`, `category`, `style_tags` (list), `size`, `condition`, `price` (float), `colors` (list), `brand`, `platform`.

### 2. `suggest_outfit`

- **Purpose:** Given a thrifted item and the user's wardrobe, ask the LLM to suggest 1–2 complete outfits. Falls back to general styling advice when the wardrobe is empty.
- **Signature:** `suggest_outfit(new_item: dict, wardrobe: dict) -> str`
- **Inputs:**
  - `new_item` (`dict`): a listing dict (the item being considered).
  - `wardrobe` (`dict`): wardrobe dict with an `items` key (a list of wardrobe item dicts). May be empty — handled gracefully.
- **Output:** `str` — a non-empty outfit-suggestion string. If the wardrobe is empty, returns general styling advice instead of raising or returning an empty string.

### 3. `create_fit_card`

- **Purpose:** Turn an outfit suggestion plus item details into a short, shareable OOTD caption (Instagram/TikTok style).
- **Signature:** `create_fit_card(outfit: str, new_item: dict) -> str`
- **Inputs:**
  - `outfit` (`str`): the outfit suggestion string from `suggest_outfit()`.
  - `new_item` (`dict`): the listing dict for the thrifted item.
- **Output:** `str` — a 2–4 sentence caption. If `outfit` is empty or whitespace-only, returns a descriptive error message string instead of raising an exception.

## How the Planning Loop Works

`run_agent(query, wardrobe)` in `agent.py` runs a single user interaction. All
state lives in one `session` dict (query, parsed params, search results,
selected item, outfit, fit card, and an `error` field), and each step reads from
and writes to it. The control flow is a linear pipeline with one early-exit
branch:

1. **Initialize** — `_new_session()` creates the session dict with every field
   set to its empty default and `error = None`.

2. **Parse the query** — `_parse_query()` uses regex (not an LLM, so it's
   deterministic) to extract:
   - `max_price`: matched from phrases like `under $30`, `below 25`,
     `less than $30.50`, `< 30`, or a bare `$30`.
   - `size`: matched from `size M`, `size XXS`, etc.; `None` if absent.
   - `description`: the original query with the price/size clauses (and any
     orphaned punctuation) stripped out.
   The result is stored in `session["parsed"]`.

3. **Search** — calls `search_listings(description, size, max_price)` and stores
   the list in `session["search_results"]`.

4. **Branch on results (the key conditional):**
   - **If `search_results` is empty** → the loop sets `session["error"]` to a
     helpful message and **returns immediately**, skipping `suggest_outfit` and
     `create_fit_card` so they never run on empty input. The error message is
     built dynamically: it suggests *raising your price limit* only if a
     `max_price` was set, *removing the size filter* only if a `size` was given,
     and always *trying different keywords*.
   - **If `search_results` is non-empty** → continue.

5. **Select** — takes the top (highest-relevance) result,
   `search_results[0]`, and stores it in `session["selected_item"]`.

6. **Suggest outfit** — calls `suggest_outfit(selected_item, wardrobe)` and
   stores the string in `session["outfit_suggestion"]`. (This tool internally
   handles an empty wardrobe by returning general styling advice, so the loop
   needs no separate branch for it.)

7. **Create fit card** — calls `create_fit_card(outfit_suggestion,
   selected_item)` and stores the result in `session["fit_card"]`.

8. **Return** the completed `session`.

**How callers use the result:** always check `session["error"]` first. If it's
not `None`, the run ended early and `outfit_suggestion` / `fit_card` are `None`.
Otherwise all three output fields are populated. `app.py`'s `handle_query()`
follows exactly this contract — it returns the error in the first UI panel (with
the other two blank) on early exit, and the formatted listing, outfit, and fit
card on success.

## State Management

FitFindr keeps **all** interaction state in a single `session` dict, created per
call by `_new_session(query, wardrobe)` in `agent.py`. There are no globals and
no hidden state — the session is the single source of truth, passed forward as
each step fills in its slice. The tools themselves are stateless: the planning
loop is the only thing that reads from and writes to the session.

### What is stored, and when

| Field | Type | Written by | When |
|-------|------|-----------|------|
| `query` | `str` | `_new_session` | At init — the original user query, kept verbatim. |
| `wardrobe` | `dict` | `_new_session` | At init — passed in by the caller (`get_example_wardrobe()` / `get_empty_wardrobe()`). |
| `parsed` | `dict` | Step 2 | After `_parse_query()` — `{description, size, max_price}`. |
| `search_results` | `list[dict]` | Step 3 | After `search_listings()` — all matching listings, ranked. |
| `selected_item` | `dict \| None` | Step 5 | After selection — the top result (`search_results[0]`). |
| `outfit_suggestion` | `str \| None` | Step 6 | After `suggest_outfit()`. |
| `fit_card` | `str \| None` | Step 7 | After `create_fit_card()`. |
| `error` | `str \| None` | Any early exit | Set when the run ends early (e.g. no search results); `None` on success. |

Fields not yet reached keep their empty defaults (`None` / `[]` / `{}`), so the
shape of the session is always predictable regardless of where the run stopped.

### How state is passed between tools

Each tool receives **only the slice of state it needs**, taken from the session,
and its return value is written straight back into the session — never passed
tool-to-tool directly:

- `session["parsed"]` → unpacked into `search_listings(description, size, max_price)` → result stored in `session["search_results"]`.
- `session["search_results"][0]` → stored as `session["selected_item"]`, then passed (with `session["wardrobe"]`) into `suggest_outfit(new_item, wardrobe)` → result stored in `session["outfit_suggestion"]`.
- `session["outfit_suggestion"]` and `session["selected_item"]` → passed into `create_fit_card(outfit, new_item)` → result stored in `session["fit_card"]`.

This means the output of one tool becomes the input of the next *via the
session*, so at any point you can inspect the full session to see exactly what
each tool produced.

### Lifetime and consumption

The session lives for one `run_agent()` call and is returned to the caller. It is
**not** persisted across queries — each query starts a fresh session, so there is
no cross-request memory. Callers consume it by checking `session["error"]` first
(non-`None` means early exit, with `outfit_suggestion`/`fit_card` still `None`),
then reading the populated output fields. `app.py`'s `handle_query()` does exactly
this when mapping the session to the three UI panels.

## Error Handling Strategy

Every tool degrades gracefully instead of raising — a failure mode returns a
safe value (empty list or descriptive string) so the planning loop never crashes
mid-run. The loop adds one more layer: it refuses to call a downstream tool with
unusable input.

### `search_listings` — no matches return an empty list

The tool never raises on a missed search; it returns `[]`. The planning loop
checks for this and **exits early** rather than calling `suggest_outfit` with no
item, building a help message that only mentions the filters actually in play.

> **Concrete example (from testing):** the query
> `"designer ballgown size XXS under $5"` parses to
> `{description: "designer ballgown", size: "XXS", max_price: 5.0}` and matches
> **0 listings**. `run_agent` returns early with:
> *"No listings matched your search. Try raising your price limit, or removing
> the size filter, or trying different keywords."*
> `outfit_suggestion` and `fit_card` stay `None`.

### `suggest_outfit` — empty wardrobe falls back to general advice

A new user may have an empty wardrobe (`{"items": []}`) or a wardrobe dict with
no `items` key at all. Rather than raising or returning `""`, the tool detects
the empty case and switches its prompt to ask the LLM for **general styling
advice** for the item. It always returns a non-empty string.

> **Concrete example (from testing):** calling `handle_query(..., "Empty
> wardrobe (new user)")` still returns a populated outfit panel — the suggestion
> describes what kinds of pieces and vibes pair with the item, instead of naming
> specific wardrobe items it doesn't have.

### `create_fit_card` — empty outfit is guarded before the LLM call

If `outfit` is empty or whitespace-only, the tool returns a descriptive message
(*"Outfit details unavailable. Please check your wardrobe or try again."*)
**without** calling the LLM — saving a wasted API request and never raising.

> **Concrete example (from testing):** `create_fit_card("", item)` and
> `create_fit_card("   \n\t  ", item)` both return the guard message, and our
> unit tests assert the Groq client was **never invoked** in those cases
> (`patch_groq.last_call is None`).

These behaviors are locked in by `tests/test_tools.py`, which includes at least
one test per failure mode (no-match search, empty/missing-key wardrobe,
empty/whitespace outfit guard).

## Spec Reflection

The spec (`planning.md`) was written before the code. Comparing it to the final
implementation:

**One way the spec helped:** the *Error Handling* table and the *Complete
Interaction (Step by Step)* walkthrough made the planning loop almost mechanical
to write. They specified up front that `search_listings` returning nothing should
stop the run and offer broadened filters — *before* `suggest_outfit` is ever
called — and that the tool order is always search → suggest → fit card. That
turned directly into the early-exit branch and the linear pipeline in
`run_agent`, so there was no guesswork about control flow or where errors get
handled.

**One way the implementation diverged, and why:** the spec designed richer tool
contracts than what shipped. For example, it described `suggest_outfit` as taking
extra `occasion` / `max_items` params and returning a structured `outfit` object
(`{items, rationale, confidence, swap_suggestions}`), and `create_fit_card` as
returning a `fit_card` dict (`{title, hero_image, price, bullets, link, meta}`).
The implemented signatures are simpler: `suggest_outfit(new_item, wardrobe) ->
str` and `create_fit_card(outfit, new_item) -> str`. Two reasons drove this: (1)
the starter `tools.py` fixed these signatures, so matching them kept the tools,
agent, and Gradio app consistent; and (2) the UI just renders text panels, so a
plain LLM-generated string is what's actually needed — building and then
re-flattening structured dicts would have been overhead with no payoff for this
interface. The spec's structured-object design remains a sensible direction if
the app later needs to render real cards (images, clickable links, confidence
badges) rather than text.

## AI Usage

I used an AI coding assistant (Claude) to help build parts of this project.
Specific instances of what I directed it to do, and what I revised or overrode:

**1. Implementing the planning loop in `agent.py`.**
I directed the AI to implement `run_agent` to follow the loop I designed in
`planning.md`. It chose a regex-based query parser (over an LLM parser) for
determinism, which I kept. I then reviewed the parsed output and **overrode the
first version**: parsing `"vintage graphic tee under $30, size M"` left a stray
trailing comma in the description (`"vintage graphic tee ,"`). I had it revise
`_parse_query` to strip orphaned punctuation so the description came out clean.

**2. Writing the tool tests.**
I directed the AI to write pytest tests with at least one test per failure mode.
It proposed mocking the Groq client so the tests run offline with no API key — I
accepted that approach because it makes the suite deterministic and CI-friendly.
What I did **not** accept was expanding scope: when it offered to also add
integration tests for `run_agent`, I declined ("not yet") to keep the test file
focused on the individual tools first.

**3. Writing this README's documentation.**
I directed the AI to document the tool inventory, but with the constraint that
the inputs and return values **must match the actual function signatures**, not
the richer designs in `planning.md`. This overrode the spec's structured-object
contracts (e.g. `suggest_outfit` returning an `outfit` dict) in favor of
documenting what the code really does (`-> str`). See *Spec Reflection* above for
the reasoning.

## Where to Start

1. **Read `planning.md` and fill it out before writing any code.**
2. Verify the data loads correctly by running `python utils/data_loader.py`.
3. Build and test each tool individually before connecting them through your planning loop.

Your implementation files go in this same directory. There's no required file structure for your agent code — organize it however makes sense for your design.
