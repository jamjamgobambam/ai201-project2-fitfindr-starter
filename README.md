# FitFindr — Multi-Tool AI Agent

FitFindr is a multi-tool AI agent that helps users find secondhand clothing items and decide how to style them with their existing wardrobe. The agent takes a natural language request, searches a mock secondhand listings dataset, suggests outfit ideas, and creates a short shareable fit card caption.

This project focuses on agent planning: deciding which tool to call, when to call it, how to pass state between tools, and how to stop safely when something goes wrong.

---

## Project Overview

FitFindr helps users answer questions like:

> "I'm looking for a vintage graphic tee under $30. How would I style it?"

The agent handles the request in multiple steps:

1. Parse the user query into search parameters.
2. Search secondhand listings using `search_listings`.
3. Select the best matching item.
4. Suggest outfits using `suggest_outfit`.
5. Generate a social-style caption using `create_fit_card`.
6. Return the final result through a Gradio interface.

If no matching listings are found, the agent stops early and returns a helpful message instead of continuing to the styling tools.

---

## What's Included

```text
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json              # 40 mock secondhand listings
│   └── wardrobe_schema.json       # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py             # Helper functions for loading data
├── tests/
│   ├── test_tools.py              # Tests for individual tools
│   ├── test_agent.py              # Tests for planning loop and state flow
│   └── test_app.py                # Tests for Gradio handler logic
├── agent.py                       # Planning loop and session state management
├── app.py                         # Gradio interface
├── tools.py                       # Tool implementations
├── planning.md                    # Agent design specification
├── pytest.ini                     # Pytest configuration
├── requirements.txt               # Python dependencies
└── README.md                      # Project documentation
```

---

## Setup

Create and activate a virtual environment.

### Windows PowerShell

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Git Bash

```bash
python -m venv .venv
source .venv/Scripts/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_key_here
```

The `.env` file should not be committed to GitHub.

---

## How to Run the App

Run the Gradio app:

```bash
python app.py
```

Open the local URL shown in the terminal, usually:

```text
http://localhost:7860
```

Try a successful query:

```text
vintage graphic tee under $30
```

Try a failure query:

```text
designer ballgown size XXS under $5
```

---

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories such as:

* tops
* bottoms
* outerwear
* shoes
* accessories

Each listing has these fields:

* `id`
* `title`
* `description`
* `category`
* `style_tags`
* `size`
* `condition`
* `price`
* `colors`
* `brand`
* `platform`

The app loads listings through:

```python
from utils.data_loader import load_listings
```

To avoid redundant loading, the project uses a cached helper in `tools.py` so listings are loaded once and reused across searches.

---

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the structure of a user's wardrobe.

Each wardrobe item can include:

* `id`
* `name`
* `category`
* `colors`
* `style_tags`
* `notes`

The project uses two helper functions:

```python
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe
```

`get_example_wardrobe()` is used for normal testing with a sample closet.

`get_empty_wardrobe()` is used to test the case where a new user has not added wardrobe items yet.

---

## Tool Inventory

### Tool 1: `search_listings(description, size=None, max_price=None)`

**Purpose:**
Searches the mock secondhand listings dataset for items matching the user's request.

**Inputs:**

* `description` (`str`): Keywords describing the item, such as `"vintage graphic tee"`.
* `size` (`str | None`): Optional size filter, such as `"M"`, `"S/M"`, `"US 8"`, or `None`.
* `max_price` (`float | None`): Optional maximum price filter, such as `30.0`, or `None`.

**Output:**
Returns a list of matching listing dictionaries sorted by relevance. Each listing contains fields such as `title`, `description`, `price`, `size`, `style_tags`, `colors`, and `platform`.

**Failure handling:**
If no listing matches, the function returns an empty list `[]`. It does not raise an exception.

---

### Tool 2: `suggest_outfit(new_item, wardrobe)`

**Purpose:**
Suggests 1–2 outfits using the selected thrift item and the user's wardrobe.

**Inputs:**

* `new_item` (`dict`): The selected listing returned by `search_listings`.
* `wardrobe` (`dict`): The user's wardrobe dictionary with an `"items"` list.

**Output:**
Returns a non-empty string containing outfit suggestions.

**Failure handling:**
If the wardrobe is empty, the tool does not crash. It asks the LLM for general styling advice instead of wardrobe-specific outfit ideas.

If the LLM call fails, the tool returns a rule-based fallback styling suggestion.

---

### Tool 3: `create_fit_card(outfit, new_item)`

**Purpose:**
Creates a short, shareable outfit caption based on the thrifted item and outfit suggestion.

**Inputs:**

* `outfit` (`str`): The outfit suggestion returned by `suggest_outfit`.
* `new_item` (`dict`): The selected listing returned by `search_listings`.

**Output:**
Returns a 2–4 sentence caption suitable for Instagram or TikTok.

**Failure handling:**
If `outfit` is empty or missing, the tool returns a descriptive error message instead of raising an exception.

Example:

```text
I couldn't create a fit card because the outfit suggestion was missing.
```

---

## Planning Loop Explanation

The main planning loop is implemented in `agent.py` inside `run_agent()`.

The agent does not blindly call every tool. It checks the current session state and decides what to do next.

The workflow is:

1. Create a new session dictionary.
2. Parse the user query into:

   * `description`
   * `size`
   * `max_price`
3. Store the parsed values in `session["parsed"]`.
4. Call `search_listings(description, size, max_price)`.
5. Store the results in `session["search_results"]`.
6. If no results are found:

   * Set `session["error"]`.
   * Return the session early.
   * Do not call `suggest_outfit`.
   * Do not call `create_fit_card`.
7. If results exist:

   * Select the first result as `session["selected_item"]`.
8. Call `suggest_outfit(selected_item, wardrobe)`.
9. Store the result in `session["outfit_suggestion"]`.
10. Call `create_fit_card(outfit_suggestion, selected_item)`.
11. Store the result in `session["fit_card"]`.
12. Return the completed session.

This makes the agent conditional because its behavior changes based on whether `search_listings` returns results.

---

## State Management

The agent uses a session dictionary as the single source of truth for one interaction.

The session includes:

```python
{
    "query": query,
    "parsed": {},
    "search_results": [],
    "selected_item": None,
    "wardrobe": wardrobe,
    "outfit_suggestion": None,
    "fit_card": None,
    "error": None,
}
```

State flows through the agent like this:

```text
User query
→ session["parsed"]
→ search_listings()
→ session["search_results"]
→ session["selected_item"]
→ suggest_outfit()
→ session["outfit_suggestion"]
→ create_fit_card()
→ session["fit_card"]
```

This avoids asking the user to re-enter information. The selected listing from the search step is passed directly into the outfit suggestion step, and the outfit suggestion is passed directly into the fit card step.

---

## Avoiding Redundant Initialization

One improvement I focused on was avoiding redundant expensive setup.

In `tools.py`, the listings dataset is cached:

```python
@lru_cache(maxsize=1)
def _get_listings():
    return tuple(load_listings())
```

This prevents the app from repeatedly reading `listings.json` every time a user searches.

The Groq client is also cached:

```python
@lru_cache(maxsize=1)
def _get_groq_client():
    return Groq(api_key=api_key)
```

This prevents the app from recreating the Groq client every time `suggest_outfit()` or `create_fit_card()` runs.

The LLM call is centralized in `_call_llm()`, so the same Groq API logic is reused by both LLM-based tools.

The agent also uses regex-based parsing instead of calling the LLM just to extract simple fields like price and size.

---

## Error Handling Strategy

| Tool / Component   | Failure Mode                | Agent Response                                                                          |
| ------------------ | --------------------------- | --------------------------------------------------------------------------------------- |
| `search_listings`  | No listings match the query | Returns `[]`. The agent sets `session["error"]` and stops early with a helpful message. |
| `suggest_outfit`   | Wardrobe is empty           | Returns general styling advice instead of crashing.                                     |
| `suggest_outfit`   | LLM call fails              | Returns a rule-based fallback outfit suggestion.                                        |
| `create_fit_card`  | Outfit input is empty       | Returns a clear message explaining that the outfit suggestion is missing.               |
| `run_agent`        | Empty user query            | Sets `session["error"]` asking the user to enter an item.                               |
| `app.handle_query` | Agent returns an error      | Displays the error in the first output panel and leaves the other panels empty.         |

Example no-results message:

```text
I couldn't find any listings for 'designer ballgown' with size XXS and under $5.00. Try using a broader description, increasing your budget, or removing the size filter.
```

---

## Testing Summary

The project includes tests for the tools, agent loop, and app handler.

Run all tests with:

```bash
pytest
```

Current test result:

```text
14 passed
```

Test coverage includes:

### `tests/test_tools.py`

* Search returns results.
* Search returns an empty list for impossible queries.
* Search respects max price.
* Outfit suggestion works with example wardrobe.
* Outfit suggestion works with empty wardrobe.
* Fit card generation works.
* Fit card handles missing outfit input.

### `tests/test_agent.py`

* Happy-path planning loop.
* No-results path stops early.
* Empty query returns an error.

### `tests/test_app.py`

* Empty query handling.
* Error path mapping.
* Successful output mapping.
* Empty wardrobe choice handling.

The agent tests use `monkeypatch` to avoid unnecessary live LLM calls when testing planning logic. This keeps tests faster and focused on state flow and decision-making.

---

## Example Interaction

User query:

```text
vintage graphic tee under $30
```

The agent:

1. Parses the query into:

   * description: `vintage graphic tee`
   * size: `None`
   * max_price: `30.0`
2. Searches listings.
3. Selects a matching graphic tee.
4. Suggests outfit ideas using the example wardrobe.
5. Creates a shareable fit card.

Example output:

```text
Top listing:
Graphic Tee — 2003 Tour Bootleg Style
Price: $24.00
Platform: depop
Size: L
Condition: good

Outfit idea:
Pair the Graphic Tee with baggy straight-leg jeans, black combat boots, and a vintage black denim jacket for a grunge-inspired look.

Fit card:
Just scored this Graphic Tee on depop for $24.00 and styled it with baggy jeans, combat boots, and a denim jacket for an easy grunge streetwear fit.
```

---

## Spec Reflection

The planning spec helped me separate the project into three clear tools before writing implementation code. This made it easier to build and test each tool individually before connecting them through the agent loop.

One implementation detail that became more important during coding was avoiding redundant initialization. Based on feedback from the previous retrieval project, I made sure not to reload data or recreate expensive clients inside every request. I used `lru_cache` for loading listings and initializing the Groq client once.

Another small implementation detail was improving query parsing. The planning document described extracting description, size, and price from the query. During implementation, I added regex parsing so the agent could handle phrases like `"under $30"`, `"size M"`, and `"US 8"` without using an extra LLM call.

The implementation still matches the original plan: search first, stop early if no results, suggest an outfit only when an item exists, and create a fit card only after an outfit suggestion exists.

---

## AI Usage

I used AI assistance in specific, reviewable ways during this project.

### AI Usage Instance 1: Planning Document

I used ChatGPT to help draft the `planning.md` sections for the three required tools, the planning loop, state management, error handling, and architecture diagram. I provided the starter code, assignment requirements, and dataset structure as input. I reviewed the generated plan and adjusted it so it matched the actual required function signatures and project behavior.

### AI Usage Instance 2: Tool Implementation Support

I used ChatGPT to help implement `search_listings`, `suggest_outfit`, and `create_fit_card` based on the completed `planning.md`. I specifically asked for implementations that avoided redundant initialization. I reviewed the output and kept the design where listings and the Groq client are cached instead of being recreated on every request.

### AI Usage Instance 3: Testing Support

I used ChatGPT to help design pytest tests for the individual tools, the planning loop in `agent.py`, and the Gradio handler in `app.py`. I revised the tests when one parser expectation did not match the actual implementation. After the revision, all 14 tests passed.

---

## Demo Video Notes

The demo video should show:

1. The Gradio app running.
2. A successful full interaction using:

```text
vintage graphic tee under $30
```

This should show all three output panels:

* Top listing found
* Outfit idea
* Fit card

3. A failure interaction using:

```text
designer ballgown size XXS under $5
```

This should show the agent returning a helpful error message and leaving the outfit and fit card panels empty.

4. A narration explaining the state flow:

```text
The agent parses the query, calls search_listings, stores the top result as selected_item, passes selected_item and wardrobe into suggest_outfit, then passes outfit_suggestion and selected_item into create_fit_card.
```

5. A narration explaining the error path:

```text
When search_listings returns no results, the agent sets session["error"] and stops early instead of calling suggest_outfit or create_fit_card.
```

Demo video link:

```text
Add demo video link here before submission.
```

---

## Final Status

Completed features:

* Three required tools implemented.
* Planning loop implemented.
* State passed across tool calls using a session dictionary.
* Error handling implemented for each required failure mode.
* Gradio app connected to the agent.
* Tests added for tools, agent loop, and app handler.
* 14 tests passing.
* Redundant initialization reduced using caching.
