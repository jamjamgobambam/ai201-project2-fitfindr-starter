# FitFindr

FitFindr helps a user search mock secondhand listings, pick the best match, style it with their wardrobe, and create a short fit-card caption.

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file with:

```text
GROQ_API_KEY=your_key_here
```

Run the app:

```bash
python app.py
```

Run tests:

```bash
pytest tests/
```

## Tool Inventory

### `search_listings`

Purpose: searches `data/listings.json` for matching secondhand items.

Inputs:
- `description` (str): item words, like `"vintage graphic tee"`
- `size` (str): optional size filter, like `"M"` or `"US 8"`
- `max_price` (float): optional price limit, like `30.0`

Output: a list of listing dictionaries, best match first. Each listing has `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

### `suggest_outfit`

Purpose: suggests how to style one selected listing with the user's wardrobe.

Inputs:
- `new_item` (dict): the listing selected from search results
- `wardrobe` (dict): a wardrobe with an `items` list

Output: a string with outfit advice. If the wardrobe has items, it tries to name those pieces. If the wardrobe is empty, it gives general styling advice.

### `create_fit_card`

Purpose: creates a short shareable caption from an outfit idea and selected listing.

Inputs:
- `outfit` (str): the outfit suggestion
- `new_item` (dict): the selected listing

Output: a 2-4 sentence fit-card caption, or a clear message if the outfit is missing.

## Planning Loop

`run_agent()` starts a session, parses the query into `description`, `size`, and `max_price`, then calls `search_listings()`.

If search returns no results, the agent sets `session["error"]` and returns early. It does not call `suggest_outfit()` with empty input.

If search returns results, the agent saves them in `session["search_results"]`, sets `session["selected_item"] = results[0]`, and passes that exact item to `suggest_outfit()`.

If an outfit suggestion comes back, the agent saves it in `session["outfit_suggestion"]` and passes it to `create_fit_card()` with the same selected item. The completed session is returned to `app.py`.

## State Management

The agent uses one session dict for the whole interaction.

Tracked fields:
- `query`: original user query
- `parsed`: extracted search filters
- `search_results`: list returned by `search_listings`
- `selected_item`: first search result
- `wardrobe`: selected wardrobe
- `outfit_suggestion`: string returned by `suggest_outfit`
- `fit_card`: string returned by `create_fit_card`
- `error`: message for early failure

Each tool result is stored before the next tool runs, so the next step uses real state instead of hardcoded values.

## Error Handling

`search_listings`: if nothing matches, it returns `[]`. Example tested query: `designer ballgown size XXS under $5`. The full agent returns: "I couldn't find listings for that. Try a higher budget, no size filter, or broader search words."

`suggest_outfit`: if the wardrobe is empty, it still returns a useful string. Example tested behavior: it says the wardrobe is empty and gives general styling advice instead of crashing.

`create_fit_card`: if the outfit string is empty, it returns: "I need a complete outfit before I can make a fit card."

## Testing Notes

I tested the tools with:

```bash
pytest tests/
```

I also tested the app handler with the happy-path query `vintage graphic tee under $30`. It returned non-empty text for all three panels: listing, outfit idea, and fit card.

I smoke-tested the Gradio server with `python app.py`. The server started at `http://127.0.0.1:7861` during testing and returned HTTP 200.

## Spec Reflection

The main design choice was to keep the tools small and let the agent decide the order. Search is deterministic, while outfit ideas and fit cards use the LLM.

The most important branch is the no-results path. If search fails, the agent stops early so later tools do not receive bad input.

I also kept empty wardrobe handling inside `suggest_outfit`, because an empty closet is not a full failure. The app can still give general styling advice.

## AI Usage

### Tool Implementation Help

Input given to AI: the Tool Inventory section from `planning.md`, the `tools.py` docstrings, and the data fields from `utils/data_loader.py`.

What it produced: draft implementations for `search_listings`, `suggest_outfit`, and `create_fit_card`.

What I changed: I kept the starter function signatures, used `load_listings()` instead of reading files directly, added guards for empty input, and mocked LLM calls in tests so pytest does not need network access.

### Agent Loop Help

Input given to AI: the Planning Loop section, State Management section, Error Handling table, and the ASCII Architecture diagram from `planning.md`.

What it produced: a draft `run_agent()` flow with search, selected item, outfit suggestion, fit card, and early return on no results.

What I changed: I added a simple regex parser for `description`, `size`, and `max_price`, verified that no-results stops before `suggest_outfit()`, and checked that the same selected item flows into later tools.

### README Help

Input given to AI: the project rubric, current implementation files, and the tested failure outputs.

What it produced: a README outline with required sections.

What I changed: I shortened the wording, removed vague claims, and added the exact tested error messages.
