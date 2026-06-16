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
import re
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

def _parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a natural language query.

    This uses lightweight regex/string rules instead of an LLM so the agent
    does not make an unnecessary API call just to parse simple search filters.
    """
    cleaned_query = query.strip()

    max_price = _extract_max_price(cleaned_query)
    size = _extract_size(cleaned_query)
    description = _extract_description(cleaned_query)

    return {
        "description": description,
        "size": size,
        "max_price": max_price,
    }


def _extract_max_price(query: str) -> float | None:
    """
    Extract a price ceiling from phrases like:
    - under $30
    - below 30
    - less than $40
    - max $25
    """
    price_patterns = [
        r"(?:under|below|less than|max|maximum|up to)\s*\$?(\d+(?:\.\d{1,2})?)",
        r"\$?(\d+(?:\.\d{1,2})?)\s*(?:or less|and under)",
    ]

    for pattern in price_patterns:
        match = re.search(pattern, query, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))

    return None


def _extract_size(query: str) -> str | None:
    """
    Extract a size from phrases like:
    - size M
    - in size M
    - US 8
    - W30
    """
    size_patterns = [
        r"\bsize\s+([a-zA-Z0-9./-]+)\b",
        r"\bUS\s*([0-9]+(?:\.[0-9])?)\b",
        r"\b(W[0-9]{2}(?:\s*L[0-9]{2})?)\b",
    ]

    for pattern in size_patterns:
        match = re.search(pattern, query, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip()

            if pattern.startswith(r"\bUS"):
                return f"US {value}"

            return value.upper()

    return None


def _extract_description(query: str) -> str:
    """
    Remove price and size phrases so the remaining text can be used as the
    search description.
    """
    description = query.strip().lower()

    # Remove common starter phrases.
    starter_phrases = [
        "i'm looking for",
        "im looking for",
        "looking for",
        "find me",
        "show me",
        "i want",
        "can you find",
        "what's out there for",
        "what is out there for",
    ]

    for phrase in starter_phrases:
        description = description.replace(phrase, " ")

    # Remove price phrases.
    description = re.sub(
        r"(?:under|below|less than|max|maximum|up to)\s*\$?\d+(?:\.\d{1,2})?",
        " ",
        description,
        flags=re.IGNORECASE,
    )
    description = re.sub(
        r"\$?\d+(?:\.\d{1,2})?\s*(?:or less|and under)",
        " ",
        description,
        flags=re.IGNORECASE,
    )

    # Remove size phrases.
    description = re.sub(
        r"\b(?:in\s+)?size\s+[a-zA-Z0-9./-]+\b",
        " ",
        description,
        flags=re.IGNORECASE,
    )
    description = re.sub(
        r"\bUS\s*[0-9]+(?:\.[0-9])?\b",
        " ",
        description,
        flags=re.IGNORECASE,
    )

    # Remove styling-only context after common separators.
    description = re.split(
        r"\b(?:i mostly wear|how would i style|what would i wear|style it with|and how)\b",
        description,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]

    # Clean punctuation and extra spaces.
    description = re.sub(r"[^a-zA-Z0-9\s/-]", " ", description)
    description = re.sub(r"\s+", " ", description).strip()

    return description

# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.
    """
    session = _new_session(query, wardrobe)

    if not query or not query.strip():
        session["error"] = "Please enter what kind of secondhand item you are looking for."
        return session

    # Step 1: Parse the user query.
    parsed = _parse_query(query)
    session["parsed"] = parsed

    description = parsed["description"]
    size = parsed["size"]
    max_price = parsed["max_price"]

    if not description:
        session["error"] = (
            "I couldn't tell what item you are looking for. "
            "Try something like 'vintage graphic tee under $30' or 'black combat boots size US 8'."
        )
        return session

    # Step 2: Search listings.
    search_results = search_listings(
        description=description,
        size=size,
        max_price=max_price,
    )
    session["search_results"] = search_results

    # Step 3: Branch if no results.
    if not search_results:
        filters_used = []

        if size:
            filters_used.append(f"size {size}")

        if max_price is not None:
            filters_used.append(f"under ${max_price:.2f}")

        filter_text = f" with {' and '.join(filters_used)}" if filters_used else ""

        session["error"] = (
            f"I couldn't find any listings for '{description}'{filter_text}. "
            "Try using a broader description, increasing your budget, or removing the size filter."
        )
        return session

    # Step 4: Select top listing.
    selected_item = search_results[0]
    session["selected_item"] = selected_item

    # Step 5: Suggest outfit.
    outfit_suggestion = suggest_outfit(
        new_item=selected_item,
        wardrobe=wardrobe,
    )
    session["outfit_suggestion"] = outfit_suggestion

    if not outfit_suggestion or not outfit_suggestion.strip():
        session["error"] = (
            "I found a listing, but I couldn't generate an outfit suggestion for it. "
            "Please try again with another item."
        )
        return session

    # Step 6: Create fit card.
    fit_card = create_fit_card(
        outfit=outfit_suggestion,
        new_item=selected_item,
    )
    session["fit_card"] = fit_card

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
