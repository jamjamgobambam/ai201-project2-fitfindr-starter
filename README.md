# FitFindr 🛍️

FitFindr is an AI-powered personal stylist agent that helps you discover secondhand clothing and styles them with your existing wardrobe.

## Tool Inventory

### 1. `search_listings`
- **Purpose**: Searches a dataset of mock secondhand listings for items matching a user's description, with optional filters.
- **Inputs**:
    - `description` (str): Keywords for the item search.
    - `size` (str | None): Optional size filter (case-insensitive substring match).
    - `max_price` (float | None): Optional maximum price ceiling.
- **Outputs**: `list[dict]` - A list of matching listing dictionaries, sorted by relevance score.
- **Implementation**: Uses a keyword overlap scoring system to rank items based on their title, description, and style tags.

### 2. `suggest_outfit`
- **Purpose**: Suggests 1-2 complete outfits combining a newly found thrifted item with the user's current wardrobe.
- **Inputs**:
    - `new_item` (dict): The listing dictionary for the found item.
    - `wardrobe` (dict): The user's wardrobe dictionary containing a list of items.
- **Outputs**: `str` - A natural language suggestion of outfit combinations or general styling advice.
- **Implementation**: Uses the Groq LLM (`llama-3.3-70b-versatile`) to generate creative and cohesive styling ideas.

### 3. `create_fit_card`
- **Purpose**: Generates a short, shareable social media caption for the thrifted find and suggested outfit.
- **Inputs**:
    - `outfit` (str): The outfit suggestion string.
    - `new_item` (dict): The listing dictionary for the found item.
- **Outputs**: `str` - A 2-4 sentence caption suitable for Instagram or TikTok.
- **Implementation**: Uses the Groq LLM with a high temperature to ensure varied and authentic-sounding social media captions.

## How the Planning Loop Works

The FitFindr agent follows a structured linear pipeline with conditional early termination:

1.  **Parsing**: The agent first uses an LLM to parse the raw user query into structured search parameters (`description`, `size`, `max_price`).
2.  **Search**: It calls `search_listings` with these parameters.
3.  **Conditional Branch**:
    -   **Failure Path**: If no results are found, the agent sets an error message in the session state and returns immediately. This prevents subsequent tools from receiving empty or invalid data.
    -   **Success Path**: If results are found, it selects the top match (the most relevant item) and proceeds to the next stage.
4.  **Styling**: It calls `suggest_outfit` using the selected item and the user's wardrobe.
5.  **Captions**: It calls `create_fit_card` using the outfit suggestion and item details.
6.  **Completion**: The agent returns the full session object containing all results.

## State Management

FitFindr uses a central `session` dictionary to manage state throughout a single interaction.

-   **Data Storage**: The session stores the original `query`, the `parsed` parameters, the `search_results`, the `selected_item`, the `wardrobe`, the `outfit_suggestion`, and the final `fit_card`.
-   **Data Flow**: Data is passed sequentially. For example, the `selected_item` from the search step is passed into both the `suggest_outfit` and `create_fit_card` tools.
-   **Error Handling**: The `error` key in the session acts as a flag. If set, the UI displays the error instead of the tool outputs.

## Error Handling Strategy

| Tool | Failure Mode | Agent Response | Example |
|------|--------------|----------------|---------|
| `search_listings` | No matching results | Terminates loop early and returns a helpful message. | "No results found for 'designer ballgown' with your filters. Try a broader search!" |
| `suggest_outfit` | Wardrobe is empty | LLM provides "general styling advice" and essential item recommendations. | "Your wardrobe is empty. This tee pairs well with distressed denim or skater shorts..." |
| `create_fit_card` | Missing outfit input | Returns a descriptive error message instead of failing. | "Could not generate fit card due to missing outfit details." |

## Spec Reflection

-   **Helping the process**: The spec forced me to think about the "Empty Wardrobe" case early on. Without the spec, I might have assumed the user always has a wardrobe, which would have led to poor LLM performance or errors when testing with new users.
-   **Implementation Divergence**: In the initial spec, I thought about using simple regex for query parsing. However, I realized that users express price filters in many ways ("under $30", "max 30 dollars", "<30"). I diverged from the spec by using an LLM-based parser for better robustness.

## AI Usage

1.  **Tool Implementation**: I provided Claude with the tool specifications from `planning.md` and the existing code in `tools.py`. I asked it to implement the logic for `search_listings`. I had to override the initial suggestion of a complex TF-IDF approach with a simpler keyword overlap score to keep the implementation maintainable and predictable.
2.  **Gradio Integration**: I gave ChatGPT the structure of my `session` dictionary and the `app.py` skeleton. It produced the `handle_query` logic. I revised the output to ensure the "Top Listing" panel was formatted as a readable string rather than a raw dictionary dump.
