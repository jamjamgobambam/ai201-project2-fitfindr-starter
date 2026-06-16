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
<!-- Describe what this tool does in 1–2 sentences -->
`search_listings` searches the provided mock secondhand listings dataset for items that match the user's request. It filters by description keywords, optional size, and optional maximum price, then returns the best matching listings sorted by relevance.


**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): The main item or style the user is looking for, such as `"vintage graphic tee"`, `"track jacket"`, or `"black combat boots"`.
- `size` (str | None):  The requested size, such as `"M"`, `"S/M"`, `"US 8"`, or `None` if the user did not provide a size.
- `max_price` (float| None): The highest price the user wants to pay, such as `30.0`, or `None` if the user did not provide a price limit.


**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->
Returns a list of listing dictionaries sorted by relevance. Each result contains:

- `id` (str)
- `title` (str)
- `description` (str)
- `category` (str)
- `style_tags` (list[str])
- `size` (str)
- `condition` (str)
- `price` (float)
- `colors` (list[str])
- `brand` (str | None)
- `platform` (str)

If no listing matches, it returns an empty list `[]`. It should not raise an exception for normal no-result searches.


**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->
If no listings match, the agent stops the workflow early. It sets `session["error"]` to a helpful message such as:

> "I couldn't find anything matching that exact request. Try increasing your budget, removing the size filter, or using a broader description."

The agent must not call `suggest_outfit` or `create_fit_card` when search results are empty.

---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->

`suggest_outfit` takes the selected thrift listing and the user's wardrobe, then suggests one or two complete outfits. If the wardrobe has items, the suggestion should use named items from the wardrobe. If the wardrobe is empty, it should provide general styling advice instead.


**Input parameters:**
<!-- List each parameter, its type, and what it represents -->

- `new_item` (dict): The selected listing returned by `search_listings`. It contains fields such as `title`, `price`, `platform`, `colors`, `style_tags`, `category`, and `condition`.
- `wardrobe` (dict): The user's wardrobe in the provided schema. It contains an `"items"` key with a list of wardrobe item dictionaries. Each wardrobe item includes fields such as `id`, `name`, `category`, `colors`, `style_tags`, and `notes`.

**What it returns:**
<!-- Describe the return value -->
Returns a non-empty string containing outfit suggestions. The suggestion should mention the selected thrift item and, when available, specific pieces from the user's wardrobe.

Example return value:

> "Pair the Vintage Band Tee with your baggy straight-leg jeans, chunky white sneakers, and black crossbody bag for a casual 90s streetwear look. Add the vintage black denim jacket if you want a more layered grunge feel."


**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->

If the wardrobe is empty, the tool should not crash. It should return a general styling suggestion based on the new item, such as what types of bottoms, shoes, and accessories would match it.

If the LLM call fails, the tool should return a clear fallback string explaining that outfit generation failed and give a simple rule-based styling suggestion.


---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
`create_fit_card` turns the outfit suggestion and selected item into a short, shareable caption. The caption should sound casual and natural, like something someone might post on TikTok or Instagram.


**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (str): The outfit suggestion returned by `suggest_outfit`.
- `new_item` (dict): The selected listing returned by `search_listings`.

**What it returns:**
<!-- Describe the return value -->
Returns a 2–4 sentence string. The fit card should mention the item name, price, and platform naturally. It should describe the outfit vibe and sound different for different inputs.
Example return value:

> "Found this faded band tee on Depop for $19 and it instantly gives 90s streetwear energy. Styling it with baggy jeans, chunky sneakers, and a black crossbody for an easy thrifted everyday fit."


**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->

If `outfit` is empty or missing, the tool returns a clear error message string instead of raising an exception:

> "I couldn't create a fit card because the outfit suggestion was missing."

If required item fields are missing, the tool should still try to produce a basic caption using whatever fields are available.


---

### Additional Tools (if any)
<!-- Copy the block above for any tools beyond the required three -->

No additional tools will be implemented for the required version. Stretch tools, such as price comparison or retry search, will only be added after the required three-tool workflow is complete and tested.


---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->

The agent uses the session dictionary as its source of truth. It starts with the original user query and wardrobe, then moves step by step based on what data is available.

1. Initialize a new session using `_new_session(query, wardrobe)`.
2. Parse the user query to extract:
   - `description`
   - `size`
   - `max_price`
3. Store the parsed values in `session["parsed"]`.
4. Call `search_listings(description, size, max_price)`.
5. Store the returned list in `session["search_results"]`.
6. If `search_results` is empty:
   - Set `session["error"]` to a helpful no-results message.
   - Return the session immediately.
   - Do not call `suggest_outfit`.
   - Do not call `create_fit_card`.
7. If results exist:
   - Select the first result as the best match.
   - Store it in `session["selected_item"]`.
8. Call `suggest_outfit(session["selected_item"], session["wardrobe"])`.
9. Store the returned string in `session["outfit_suggestion"]`.
10. If the outfit suggestion is empty:
   - Set `session["error"]` to a helpful message.
   - Return early.
11. Call `create_fit_card(session["outfit_suggestion"], session["selected_item"])`.
12. Store the returned string in `session["fit_card"]`.
13. Return the completed session.

The loop is complete when either:

- `session["error"]` is set, or
- `session["fit_card"]` is successfully created.

The agent does not call all tools unconditionally. Its behavior changes depending on whether `search_listings` finds results and whether the outfit suggestion is valid.


---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

The agent stores all information for one user interaction in a session dictionary. This keeps the workflow organized and prevents tools from needing to ask the user for the same information again.

The session tracks:

- `query`: The original user query.
- `parsed`: The extracted search parameters.
- `search_results`: The list returned by `search_listings`.
- `selected_item`: The top listing selected from the search results.
- `wardrobe`: The user's wardrobe.
- `outfit_suggestion`: The string returned by `suggest_outfit`.
- `fit_card`: The string returned by `create_fit_card`.
- `error`: A message explaining why the workflow stopped early, or `None` if successful.

Data flow:

- The parsed query becomes input to `search_listings`.
- The top search result becomes `selected_item`.
- `selected_item` and `wardrobe` become input to `suggest_outfit`.
- `outfit_suggestion` and `selected_item` become input to `create_fit_card`.
- The final session is returned to the app.

To avoid redundant initialization, expensive resources such as loaded listings and the Groq client should be initialized once using caching or module-level helpers, instead of being recreated inside every request.


---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | |
| suggest_outfit | Wardrobe is empty | |
| create_fit_card | Outfit input is missing or incomplete | || Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | The agent sets `session["error"]` to a helpful message explaining that no listings were found. It suggests broadening the search, increasing budget, or removing the size filter. The workflow stops early and does not call the other tools. |
| suggest_outfit | Wardrobe is empty | The tool returns general styling advice for the selected item instead of crashing. The agent continues to `create_fit_card` using that general outfit suggestion. |
| create_fit_card | Outfit input is missing or incomplete | The tool returns a clear error message string such as `"I couldn't create a fit card because the outfit suggestion was missing."` The agent stores this message and does not crash. |


---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

```mermaid
flowchart TD
    A[User query] --> B[Planning Loop / run_agent]

    B --> C[Parse query into description, size, max_price]
    C --> S[(Session State)]
    S --> D[search_listings description, size, max_price]

    D --> E{Any results?}

    E -- No --> F[Set session error: no listings found]
    F --> Z[Return session early]

    E -- Yes --> G[Store search_results in session]
    G --> H[Select top result as selected_item]
    H --> S

    S --> I[suggest_outfit selected_item, wardrobe]
    I --> J{Outfit suggestion returned?}

    J -- No --> K[Set session error: outfit suggestion missing]
    K --> Z

    J -- Yes --> L[Store outfit_suggestion in session]
    L --> S

    S --> M[create_fit_card outfit_suggestion, selected_item]
    M --> N[Store fit_card in session]
    N --> O[Return completed session]

    S <--> B

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     I plan to use both Claude and ChaptGPT
     - What you'll give it as input (which sections of this planning.md, your agent diagram)

      i will give my tool one for it to implement and the ctest to see if the implementation matches what i am looking for as outpiut 
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

      this will be done by making sure that  after testing the completed segment if it matched with my expected output  iwill move on and if otherwise i will prompt for further help.

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**
I will use ChatGPT to help implement one tool at a time. For each tool, I will provide the matching tool section from this planning.md, the existing function stub from tools.py, and the fields available in listings.json or wardrobe_schema.json.

For search_listings, I will give ChatGPT the Tool 1 spec and ask it to implement keyword search using load_listings() from utils.data_loader. I will verify that the generated code filters by max_price, filters by size, scores keyword overlap, sorts by relevance, and returns an empty list when nothing matches.

For suggest_outfit, I will give ChatGPT the Tool 2 spec and ask it to write a Groq prompt that handles both normal wardrobes and empty wardrobes. I will verify that it does not crash when wardrobe["items"] is empty.

For create_fit_card, I will give ChatGPT the Tool 3 spec and ask it to write a caption-generation prompt. I will verify that it guards against empty outfit strings and uses a higher LLM temperature so different inputs can produce different captions.

I will test each tool using pytest before connecting them in the agent.

**Milestone 4 — Planning loop and state management:**
Milestone 4 — Planning loop and state management:

I will use ChatGPT to help implement run_agent() in agent.py. I will provide the Planning Loop section, State Management section, and Architecture diagram from this planning.md.

I expect it to produce code that:

Initializes the session.
Parses the query.
Calls search_listings.
Stops early if search results are empty.
Stores the selected item in session state.
Calls suggest_outfit.
Stores the outfit suggestion.
Calls create_fit_card.
Stores the final fit card.
Returns the session.

I will verify the output by running:

A happy-path query: "vintage graphic tee under $30"
A no-results query: "designer ballgown size XXS under $5"
An empty wardrobe query using get_empty_wardrobe()

I will confirm that the no-results path sets session["error"] and does not create a fit card.
---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
<!-- What does the agent do first? Which tool is called? With what input? -->
Example user query:
"I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

Step 1:
The agent receives the query and creates a new session.

It parses the query into:

description: "vintage graphic tee"
size: None
max_price: 30.0

The parsed values are stored in:

session["parsed"] = {
    "description": "vintage graphic tee",
    "size": None,
    "max_price": 30.0
}

**Step 2:**
<!-- What happens next? What was returned from step 1? What tool is called now? -->
the agent calls:
search_listings(
    description="vintage graphic tee",
    size=None,
    max_price=30.0
)
The tool searches the mock listings dataset. Matching listings may include items like a Y2K baby tee, a graphic tee, or a vintage band tee, because the dataset contains tops with graphic tee, vintage, band tee, and similar style tags.

The results are stored in:
session["search_results"] = results




**Step 3:**
<!-- Continue until the full interaction is complete -->
If the results list is empty, the agent stops and returns an error.

If results exist, the agent chooses the first result:
session["selected_item"] = session["search_results"][0]
{
    "title": "Vintage Band Tee — Faded Grey",
    "price": 19.00,
    "platform": "depop",
    "style_tags": ["vintage", "grunge", "band tee", "graphic tee", "streetwear"]
}

 the agent calls:
suggest_outfit(
    new_item=session["selected_item"],
    wardrobe=session["wardrobe"]
)

**Final output to user:**
<!-- What does the user actually see at the end? -->
Top listing Found:

Vintage Band Tee — Faded Grey
Price: $19.00
Platform: depop
Condition: fair
Size: L
Colors: grey, charcoal
Style tags: vintage, grunge, band tee, graphic tee, streetwear

Outfit idea:
Pair the Vintage Band Tee with your baggy straight-leg jeans, chunky white sneakers, and black crossbody bag for a casual 90s streetwear look. Add the vintage black denim jacket if you want a more layered grunge feel.

Fit Card:
Found this faded band tee on Depop for $19 and it instantly gives 90s streetwear energy. Styling it with baggy jeans, chunky sneakers, and a black crossbody for an easy thrifted everyday fit.



The tool looks at the selected thrift item and the user's wardrobe. Since the example wardrobe includes baggy jeans and chunky white sneakers, the outfit suggestion may recommend pairing the tee with those items.

session["outfit_suggestion"] = outfit_suggestion

Step 3: Implement tools.py

Order:

search_listings
suggest_outfit
create_fit_card

test one before moving on.

Step 4: 

Create:  
tests/test_tools.py

Test:

search returns results
search returns empty list for impossible query
price filter works
empty wardrobe does not crash
empty outfit does not crash

---
Step 3: Implement tools.py

Order:

search_listings
suggest_outfit
create_fit_card

Test each one before moving on.

Step 4: Add tests

Create:

tests/test_tools.py

Test:

search returns results
search returns empty list for impossible query
price filter works
empty wardrobe does not crash
empty outfit does not crash

Step 5: Implement agent.py

The agent should:

query → parse → search → if no result, stop → suggest outfit → create fit card → return session

Step 6: Implement app.py

handle_query() should:

Reject empty query.
Choose example or empty wardrobe.
Call run_agent().
If error, show error in first panel.
If success, show listing, outfit, and fit card.

Step 7: Run the app
python app.py

Then open the local Gradio link.

Step 8: Test these queries

Happy path:

vintage graphic tee under $30

No-results path:

designer ballgown size XXS under $5

Empty wardrobe path:

black combat boots size 8

---