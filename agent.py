"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

import re

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.
    """
    # Step 1: Initialize the session with _new_session().
    session = _new_session(query, wardrobe)

    # Step 2: Parse the user's query using regex
    # Extract price (e.g., looks for "$30" or "$30.50")
    price_match = re.search(r'\$(\d+(?:\.\d{2})?)', query)
    max_price = float(price_match.group(1)) if price_match else None

    # Extract size (e.g., looks for "size M", "size 8", "size XS")
    size_match = re.search(r'size\s+([A-Za-z0-9/]+)', query, re.IGNORECASE)
    size = size_match.group(1).upper() if size_match else None

    # Remove the price and size from the query to leave just the description keywords
    description = re.sub(r'(under\s*\$\d+(?:\.\d{2})?|size\s+[A-Za-z0-9/]+)', '', query, flags=re.IGNORECASE).strip()
    
    session["parsed"] = {
        "description": description, 
        "size": size, 
        "max_price": max_price
    }

    # Step 3: Call search_listings() with the parsed parameters.
    session["search_results"] = search_listings(
        description=session["parsed"]["description"], 
        size=session["parsed"]["size"], 
        max_price=session["parsed"]["max_price"]
    )

    # Step 4: Conditional Branching / Error Handling
    # If no results: set error and return early! Do not proceed to suggest_outfit.
    if not session["search_results"]:
        session["error"] = "I couldn't find any items matching your search criteria. Try adjusting your description, price, or size!"
        return session

    # Step 5: Select the item to use (the top result)
    session["selected_item"] = session["search_results"][0]

    # Step 6: Call suggest_outfit() 
    session["outfit_suggestion"] = suggest_outfit(session["selected_item"], session["wardrobe"])

    # Step 7: Call create_fit_card()
    session["fit_card"] = create_fit_card(session["outfit_suggestion"], session["selected_item"])

    # Step 8: Return the session
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
