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

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


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
    # Load all listings
    all_listings = load_listings()
    
    # Filter by max_price if provided
    if max_price is not None:
        all_listings = [l for l in all_listings if l.get("price", float("inf")) <= max_price]
    
    # Filter by size if provided (case-insensitive substring match)
    if size:
        size_lower = size.lower()
        all_listings = [l for l in all_listings if size_lower in l.get("size", "").lower()]
    
    # Score by keyword overlap
    desc_words = set(description.lower().split())
    scored = []
    
    for listing in all_listings:
        # Build searchable text from title, description, style_tags, category, brand
        searchable = " ".join([
            listing.get("title", ""),
            listing.get("description", ""),
            " ".join(listing.get("style_tags", [])),
            listing.get("category", ""),
            listing.get("brand", "") or "",
        ]).lower()
        
        listing_words = set(searchable.split())
        # Score is the number of description words found in the listing
        score = len(desc_words & listing_words)
        
        if score > 0:
            scored.append((score, listing))
    
    # Sort by score descending and return just the listing dicts
    scored.sort(key=lambda x: x[0], reverse=True)
    return [listing for _, listing in scored]


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
    client = _get_groq_client()
    
    wardrobe_items = wardrobe.get("items", [])
    new_item_desc = f"{new_item.get('title', 'New item')} ({new_item.get('category', 'clothing')}) - {new_item.get('style_tags', [])}"
    
    if not wardrobe_items:
        # Empty wardrobe: suggest general styling ideas
        prompt = f"""
I'm considering buying this thrifted item: {new_item_desc}

Price: ${new_item.get('price', 'N/A')}
Colors: {', '.join(new_item.get('colors', []))}
Condition: {new_item.get('condition', 'unknown')}

I don't have details about my current wardrobe yet. Can you suggest what kinds of items and styles would pair well with this, and what vibe or occasion this item suits best? Be specific and practical.
"""
    else:
        # Wardrobe available: suggest specific outfit combos
        wardrobe_str = "\n".join([
            f"- {item.get('name', 'Item')}: {item.get('category', '')} (color: {item.get('color', 'unknown')})"
            for item in wardrobe_items
        ])
        prompt = f"""
I'm considering buying this thrifted item: {new_item_desc}

Price: ${new_item.get('price', 'N/A')}
Colors: {', '.join(new_item.get('colors', []))}
Condition: {new_item.get('condition', 'unknown')}

Here's my current wardrobe:
{wardrobe_str}

Please suggest 1–2 specific outfit combinations using this new item with pieces from my wardrobe. Be specific about which items pair well and why. Keep it casual and fun.
"""
    
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=300,
        temperature=0.7,
    )
    
    return response.choices[0].message.content.strip() if response.choices else ""


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
    # Guard against empty outfit
    if not outfit or not outfit.strip():
        return "Outfit details unavailable. Please check your wardrobe or try again."
    
    client = _get_groq_client()
    
    prompt = f"""
Create a short, casual Instagram/TikTok OOTD (outfit of the day) caption based on the following:

Item: {new_item.get('title', 'Thrifted find')}
Price: ${new_item.get('price', 'N/A')} (from {new_item.get('platform', 'thrifting platform')})
Style tags: {', '.join(new_item.get('style_tags', []))}

Outfit suggestion:
{outfit}

Write a 2-4 sentence caption that:
- Feels authentic and casual (like a real person posting)
- Naturally mentions the item name, price, and where it's from (once each)
- Captures the outfit vibe and styling
- Avoids sounding like a product description

Just the caption text, nothing else.
"""
    
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=200,
        temperature=0.9,
    )
    
    return response.choices[0].message.content.strip() if response.choices else "Check back soon for more fits!"
