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
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

MODEL_NAME = "llama-3.3-70b-versatile"
STOP_WORDS = {
    "a",
    "an",
    "and",
    "for",
    "in",
    "of",
    "the",
    "to",
    "under",
    "with",
}


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


def _tokens(text: object) -> list[str]:
    """Return simple lowercase word tokens for search scoring."""
    return re.findall(r"[a-z0-9]+", str(text or "").lower())


def _query_terms(description: str) -> list[str]:
    return [token for token in _tokens(description) if token not in STOP_WORDS]


def _matches_size(listing_size: str, requested_size: str | None) -> bool:
    if not requested_size or not str(requested_size).strip():
        return True

    requested = str(requested_size).strip().lower()
    listing = str(listing_size or "").lower()
    requested_tokens = _tokens(requested)
    listing_tokens = _tokens(listing)

    if len(requested) > 1 and requested in listing:
        return True
    return bool(requested_tokens) and all(token in listing_tokens for token in requested_tokens)


def _listing_text(listing: dict) -> str:
    parts = [
        listing.get("title"),
        listing.get("description"),
        listing.get("category"),
        listing.get("brand"),
        " ".join(listing.get("style_tags") or []),
        " ".join(listing.get("colors") or []),
    ]
    return " ".join(str(part) for part in parts if part)


def _score_listing(listing: dict, terms: list[str], phrase: str) -> int:
    title_terms = set(_tokens(listing.get("title")))
    tag_terms = set(_tokens(" ".join(listing.get("style_tags") or [])))
    color_terms = set(_tokens(" ".join(listing.get("colors") or [])))
    category_terms = set(_tokens(listing.get("category")))
    all_terms = set(_tokens(_listing_text(listing)))

    score = 0
    for term in terms:
        if term in title_terms:
            score += 4
        if term in tag_terms:
            score += 3
        if term in color_terms or term in category_terms:
            score += 2
        if term in all_terms:
            score += 1

    haystack = _listing_text(listing).lower()
    if phrase and phrase.lower() in haystack:
        score += 5
    return score


def _format_listing_for_prompt(item: dict) -> str:
    tags = ", ".join(item.get("style_tags") or [])
    colors = ", ".join(item.get("colors") or [])
    brand = item.get("brand") or "unbranded"
    return (
        f"{item.get('title', 'Unknown item')} | "
        f"category: {item.get('category', 'unknown')} | "
        f"size: {item.get('size', 'unknown')} | "
        f"condition: {item.get('condition', 'unknown')} | "
        f"price: ${item.get('price', 'unknown')} | "
        f"platform: {item.get('platform', 'unknown')} | "
        f"brand: {brand} | "
        f"colors: {colors or 'unknown'} | "
        f"style tags: {tags or 'none'}"
    )


def _format_wardrobe_for_prompt(wardrobe_items: list[dict]) -> str:
    lines = []
    for item in wardrobe_items:
        colors = ", ".join(item.get("colors") or [])
        tags = ", ".join(item.get("style_tags") or [])
        notes = item.get("notes") or "no notes"
        lines.append(
            f"- {item.get('name', 'Unnamed item')} "
            f"({item.get('category', 'unknown')}; colors: {colors or 'unknown'}; "
            f"style: {tags or 'none'}; notes: {notes})"
        )
    return "\n".join(lines)


def _call_groq(system_prompt: str, user_prompt: str, temperature: float, max_tokens: int) -> str:
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    terms = _query_terms(description)
    if not terms:
        return []

    try:
        price_ceiling = float(max_price) if max_price is not None else None
    except (TypeError, ValueError):
        price_ceiling = None

    scored_listings = []
    for listing in load_listings():
        if price_ceiling is not None and float(listing.get("price", 0)) > price_ceiling:
            continue
        if not _matches_size(listing.get("size", ""), size):
            continue

        score = _score_listing(listing, terms, description.strip())
        if score > 0:
            scored_listings.append((score, float(listing.get("price", 0)), listing))

    scored_listings.sort(key=lambda item: (-item[0], item[1], item[2].get("title", "")))
    return [listing for _, _, listing in scored_listings]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

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

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    if not new_item:
        return "I need a selected listing before I can suggest an outfit."

    wardrobe_items = []
    if isinstance(wardrobe, dict):
        wardrobe_items = wardrobe.get("items") or []

    item_summary = _format_listing_for_prompt(new_item)
    system_prompt = (
        "You are FitFindr, a concise secondhand styling assistant. "
        "Give practical outfit ideas in a friendly voice. Do not invent closet items."
    )

    if not wardrobe_items:
        user_prompt = (
            "The user's wardrobe is empty, so give general styling advice instead "
            "of personalized closet pairings.\n\n"
            f"New item:\n{item_summary}\n\n"
            "Suggest 1-2 ways to style it. Keep it short and useful."
        )
        try:
            return _call_groq(system_prompt, user_prompt, temperature=0.7, max_tokens=280)
        except Exception:
            return (
                f"I found {new_item.get('title', 'this item')}, but your wardrobe is empty, "
                "so I cannot personalize it yet. In general, style it with a balanced bottom, "
                "simple shoes, and one layer or accessory that matches the item's vibe."
            )

    wardrobe_summary = _format_wardrobe_for_prompt(wardrobe_items)
    user_prompt = (
        f"New item:\n{item_summary}\n\n"
        f"User wardrobe:\n{wardrobe_summary}\n\n"
        "Suggest 1-2 complete outfits using the new item and named wardrobe pieces. "
        "Mention why the pieces work together. Keep it under 120 words."
    )
    try:
        return _call_groq(system_prompt, user_prompt, temperature=0.7, max_tokens=320)
    except Exception:
        item_names = [item.get("name") for item in wardrobe_items[:3] if item.get("name")]
        pieces = ", ".join(item_names) if item_names else "your existing basics"
        return (
            f"Try {new_item.get('title', 'the new item')} with {pieces}. "
            "Keep the colors simple and balance the fit with one structured piece."
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
    if not outfit or not str(outfit).strip():
        return "I need a complete outfit before I can make a fit card."
    if not new_item:
        return "I need the selected listing before I can make a fit card."

    item_summary = _format_listing_for_prompt(new_item)
    system_prompt = (
        "You write casual outfit captions for secondhand finds. "
        "Sound like a real outfit post, not an ad."
    )
    user_prompt = (
        f"New thrifted item:\n{item_summary}\n\n"
        f"Outfit suggestion:\n{outfit}\n\n"
        "Write a 2-4 sentence caption. Mention the item name, price, and platform once. "
        "Make it casual, specific, and a little different each time."
    )

    try:
        return _call_groq(system_prompt, user_prompt, temperature=1.05, max_tokens=220)
    except Exception:
        title = new_item.get("title", "this thrifted find")
        price = new_item.get("price", "unknown")
        platform = new_item.get("platform", "a secondhand shop")
        return (
            f"Found {title} on {platform} for ${price}. "
            f"Styled it like this: {str(outfit).strip()}"
        )
