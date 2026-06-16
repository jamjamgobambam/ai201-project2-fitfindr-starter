"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings
from functools import lru_cache
import re

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)

def _tokenize(text: str) -> set[str]:
    """
    Convert text into lowercase searchable words.

    Example:
        "Vintage Graphic Tee!" -> {"vintage", "graphic", "tee"}
    """
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _build_searchable_text(listing: dict) -> str:
    """
    Combine the listing fields that should be searchable.

    We search more than just the title so users can match style tags,
    colors, category, brand, and description.
    """
    parts = [
        str(listing.get("title", "")),
        str(listing.get("description", "")),
        str(listing.get("category", "")),
        str(listing.get("size", "")),
        str(listing.get("condition", "")),
        str(listing.get("brand") or ""),
        " ".join(listing.get("style_tags", [])),
        " ".join(listing.get("colors", [])),
    ]

    return " ".join(parts)


@lru_cache(maxsize=1)
def _get_listings() -> tuple[dict, ...]:
    """
    Load listings once and reuse them across calls.

    This avoids repeatedly reading listings.json every time the user searches.
    Returning a tuple also discourages accidental modification of the cached data.
    """
    return tuple(load_listings())


def _tokenize(text: str) -> set[str]:
    """
    Convert text into lowercase searchable words.
    """
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _build_searchable_text(listing: dict) -> str:
    """
    Combine fields that should be searched.
    """
    parts = [
        str(listing.get("title", "")),
        str(listing.get("description", "")),
        str(listing.get("category", "")),
        str(listing.get("size", "")),
        str(listing.get("condition", "")),
        str(listing.get("brand") or ""),
        " ".join(listing.get("style_tags", [])),
        " ".join(listing.get("colors", [])),
    ]

    return " ".join(parts).lower()


def _score_listing(query_terms: set[str], listing: dict) -> int:
    """
    Score a listing based on keyword overlap.

    Stronger matches in title and style tags get extra weight.
    """
    searchable_text = _build_searchable_text(listing)
    listing_terms = _tokenize(searchable_text)

    title_terms = _tokenize(str(listing.get("title", "")))
    style_terms = _tokenize(" ".join(listing.get("style_tags", [])))
    description_terms = _tokenize(str(listing.get("description", "")))
    category_terms = _tokenize(str(listing.get("category", "")))
    color_terms = _tokenize(" ".join(listing.get("colors", [])))

    score = 0

    # General overlap
    score += len(query_terms.intersection(listing_terms))

    # Stronger fields
    score += 3 * len(query_terms.intersection(title_terms))
    score += 3 * len(query_terms.intersection(style_terms))
    score += 2 * len(query_terms.intersection(description_terms))
    score += len(query_terms.intersection(category_terms))
    score += len(query_terms.intersection(color_terms))

    return score

def _matches_required_item_type(description: str, listing: dict) -> bool:
    """
    Prevent items from matching only because the description casually mentions
    the requested item type.

    Example:
    If the user asks for a "graphic tee", a mesh top should not match just
    because its description says it can be layered under a graphic tee.
    """
    query = description.lower()

    title_and_tags = " ".join(
        [
            str(listing.get("title", "")),
            str(listing.get("category", "")),
            " ".join(listing.get("style_tags", [])),
        ]
    ).lower()

    required_terms = ["tee", "hoodie", "jacket", "boots", "sneakers", "jeans", "pants", "skirt", "dress", "belt", "hat"]

    for term in required_terms:
        if term in query and term not in title_and_tags:
            return False

    return True

def _is_relevant_match(description: str, query_terms: set[str], listing: dict, score: int) -> bool:
    """
    Decide whether a scored listing is relevant enough to return.

    This prevents weak matches like returning a belt just because it has the word
    'vintage' when the user asked for 'vintage graphic tee'.
    """
    searchable_text = _build_searchable_text(listing)
    matched_terms = query_terms.intersection(_tokenize(searchable_text))

    # If the full phrase appears, it is definitely relevant.
    if description.strip().lower() in searchable_text:
        return True

    # Important phrase support for common fashion terms.
    important_phrases = [
        "graphic tee",
        "band tee",
        "track jacket",
        "combat boots",
        "midi skirt",
        "baby tee",
        "denim jacket",
        "leather jacket",
        "cargo pants",
    ]

    for phrase in important_phrases:
        if phrase in description.lower() and phrase in searchable_text:
            return True

    # Require at least 2 matched query terms for multi-word searches.
    if len(query_terms) >= 2 and len(matched_terms) < 2:
        return False

    # Require a meaningful score.
    return score > 0


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Returns matching listing dictionaries sorted by relevance.
    Returns [] when nothing matches.
    """
    if not description or not description.strip():
        return []

    query_terms = _tokenize(description)

    if not query_terms:
        return []

    normalized_size = size.strip().lower() if size else None
    scored_results: list[tuple[int, float, dict]] = []

    for listing in _get_listings():
        price = float(listing.get("price", 0))

        if max_price is not None and price > max_price:
            continue

        listing_size = str(listing.get("size", "")).lower()

        if normalized_size and normalized_size not in listing_size:
            continue

        score = _score_listing(query_terms, listing)

        if (_is_relevant_match(description, query_terms, listing, score) and _matches_required_item_type(description, listing)):
            scored_results.append((score, price, dict(listing)))



    scored_results.sort(key=lambda item: (-item[0], item[1]))

    return [listing for _, _, listing in scored_results]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def _format_new_item(new_item: dict) -> str:
    """
    Format the selected thrift listing into a short text block for the LLM.
    """
    return (
        f"Title: {new_item.get('title', 'Unknown item')}\n"
        f"Category: {new_item.get('category', 'unknown')}\n"
        f"Style tags: {', '.join(new_item.get('style_tags', []))}\n"
        f"Colors: {', '.join(new_item.get('colors', []))}\n"
        f"Size: {new_item.get('size', 'unknown')}\n"
        f"Condition: {new_item.get('condition', 'unknown')}\n"
        f"Price: ${float(new_item.get('price', 0)):.2f}\n"
        f"Platform: {new_item.get('platform', 'unknown')}\n"
        f"Description: {new_item.get('description', '')}"
    )


def _format_wardrobe_items(wardrobe_items: list[dict]) -> str:
    """
    Format wardrobe items into readable text for the LLM.
    """
    formatted_items = []

    for item in wardrobe_items:
        notes = item.get("notes") or "No extra notes"

        formatted_items.append(
            "- "
            f"{item.get('name', 'Unnamed item')} "
            f"({item.get('category', 'unknown category')}; "
            f"colors: {', '.join(item.get('colors', []))}; "
            f"style tags: {', '.join(item.get('style_tags', []))}; "
            f"notes: {notes})"
        )

    return "\n".join(formatted_items)


def _call_llm(prompt: str, temperature: float = 0.7) -> str:
    """
    Call Groq LLM with a reusable client.

    Keeping this in one helper avoids repeating the same Groq API code
    in suggest_outfit() and create_fit_card().
    """
    client = _get_groq_client()

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are FitFindr, a helpful secondhand fashion styling assistant. "
                    "Give practical, specific, concise outfit advice. "
                    "Avoid sounding like a generic product ad."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=temperature,
        max_tokens=350,
    )

    return response.choices[0].message.content.strip()


def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.
    """
    if not new_item:
        return (
            "I couldn't suggest an outfit because the selected listing is missing. "
            "Please search for an item first."
        )

    wardrobe_items = wardrobe.get("items", []) if isinstance(wardrobe, dict) else []
    item_text = _format_new_item(new_item)

    if not wardrobe_items:
        prompt = f"""
A user is considering buying this thrifted item:

{item_text}

The user has not added any wardrobe items yet.

Suggest 1–2 complete outfit ideas using general pieces that would pair well with this item.
Include:
- bottoms
- shoes
- optional outerwear or accessories
- the overall style vibe

Keep the answer practical, friendly, and concise.
Do not mention that you are an AI.
"""
    else:
        wardrobe_text = _format_wardrobe_items(wardrobe_items)

        prompt = f"""
A user is considering buying this thrifted item:

{item_text}

Here is the user's current wardrobe:

{wardrobe_text}

Suggest 1–2 complete outfits using the thrifted item and specific named pieces from the user's wardrobe.
Use the exact wardrobe item names when possible.

For each outfit, include:
- the thrifted item
- bottom or base piece
- shoes
- optional outerwear or accessory
- the overall style vibe

Keep the answer practical, friendly, and concise.
Do not mention that you are an AI.
"""

    try:
        result = _call_llm(prompt, temperature=0.7)

        if result:
            return result

        return _fallback_outfit_suggestion(new_item, wardrobe_items)

    except Exception as exc:
        return (
            "I couldn't generate a full LLM outfit suggestion right now, "
            f"but here's a simple styling idea: {_fallback_outfit_suggestion(new_item, wardrobe_items)}"
        )

def _fallback_outfit_suggestion(new_item: dict, wardrobe_items: list[dict]) -> str:
    """
    Rule-based backup if the LLM call fails or returns nothing.
    """
    item_name = new_item.get("title", "this thrifted item")
    item_tags = new_item.get("style_tags", [])
    vibe = ", ".join(item_tags[:3]) if item_tags else "casual thrifted"

    if wardrobe_items:
        bottoms = [
            item for item in wardrobe_items
            if item.get("category") == "bottoms"
        ]
        shoes = [
            item for item in wardrobe_items
            if item.get("category") == "shoes"
        ]
        accessories = [
            item for item in wardrobe_items
            if item.get("category") == "accessories"
        ]
        outerwear = [
            item for item in wardrobe_items
            if item.get("category") == "outerwear"
        ]

        outfit_parts = [item_name]

        if bottoms:
            outfit_parts.append(bottoms[0].get("name", "a simple bottom"))
        else:
            outfit_parts.append("a simple pair of jeans or trousers")

        if shoes:
            outfit_parts.append(shoes[0].get("name", "comfortable shoes"))
        else:
            outfit_parts.append("clean sneakers or boots")

        if outerwear:
            outfit_parts.append(outerwear[0].get("name", "a light jacket"))

        if accessories:
            outfit_parts.append(accessories[0].get("name", "a simple accessory"))

        return (
            f"Style {', '.join(outfit_parts)} together for a {vibe} look. "
            "Keep the colors balanced and let the thrifted item be the main focus."
        )

    return (
        f"Style {item_name} with relaxed denim or neutral trousers, clean sneakers or boots, "
        f"and a simple accessory for a {vibe} look."
    )

# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # Replace this with your implementation
    return ""
