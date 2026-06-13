"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

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
                     Matching is case-insensitive substring (e.g. "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.
    """
    try:
        listings = load_listings()
    except Exception as e:
        print(f"[search_listings] Failed to load listings: {e}")
        return []

    # ── Step 1: hard filters ──────────────────────────────────────────────────
    if max_price is not None:
        listings = [l for l in listings if l.get("price", 0) <= max_price]

    if size:
        size_lower = size.lower().strip()
        listings = [l for l in listings if size_lower in l.get("size", "").lower()]

    if not listings:
        return []

    # ── Step 2: relevance scoring ─────────────────────────────────────────────
    # Tokenise description into meaningful words (drop very short ones)
    tokens = {t.lower().strip(".,!?") for t in description.split() if len(t) > 2}

    def score(listing: dict) -> int:
        s = 0
        # Title: high weight (3 pts per matching token)
        title_words = {w.lower().strip(".,!?-—") for w in listing.get("title", "").split()}
        s += len(tokens & title_words) * 3

        # Style tags: 2 pts each — a tag like "vintage" fully matches token "vintage"
        for tag in listing.get("style_tags", []):
            tag_tokens = {w.lower() for w in tag.split()}
            if tokens & tag_tokens:
                s += 2

        # Category: 2 pts if any token mentions the category or vice-versa
        cat = listing.get("category", "").lower()
        if any(t in cat or cat in t for t in tokens):
            s += 2

        # Description body: 1 pt per matching token
        body_words = {w.lower().strip(".,!?") for w in listing.get("description", "").split()}
        s += len(tokens & body_words)

        # Colors: 1 pt each
        for color in listing.get("colors", []):
            color_tokens = {w.lower() for w in color.split()}
            if tokens & color_tokens:
                s += 1

        # Brand: 2 pts
        brand = (listing.get("brand") or "").lower()
        if brand and any(t in brand for t in tokens):
            s += 2

        return s

    scored = [(score(l), l) for l in listings]
    scored = [(s, l) for s, l in scored if s > 0]   # drop zero-match items
    scored.sort(key=lambda x: x[0], reverse=True)
    return [l for _, l in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key. May be empty — handled
                  gracefully with general styling advice.

    Returns:
        A non-empty string with outfit suggestions. Never raises an exception.
    """
    try:
        client = _get_groq_client()
    except ValueError as e:
        return f"[suggest_outfit error] {e}"

    item_lines = (
        f"Item: {new_item.get('title', 'unknown')}\n"
        f"Category: {new_item.get('category', 'unknown')}\n"
        f"Style tags: {', '.join(new_item.get('style_tags', []))}\n"
        f"Colors: {', '.join(new_item.get('colors', []))}\n"
        f"Condition: {new_item.get('condition', 'good')}\n"
        f"Price: ${new_item.get('price', '?')}"
    )

    wardrobe_items = wardrobe.get("items", [])

    if not wardrobe_items:
        prompt = (
            f"A shopper found this secondhand piece:\n\n{item_lines}\n\n"
            "They haven't shared their wardrobe yet. Give them 1–2 general outfit ideas for this piece — "
            "what types of items pair well with it, what aesthetic or vibe it suits, and one specific "
            "styling tip (tuck, layer, accessorise, etc.). Keep the tone casual and practical. "
            "3–5 sentences total."
        )
    else:
        wardrobe_str = "\n".join(
            f"  • {item['name']} "
            f"({item.get('category','?')}, {', '.join(item.get('colors', []))})"
            + (f" — {item['notes']}" if item.get("notes") else "")
            for item in wardrobe_items
        )
        prompt = (
            f"A shopper found this secondhand piece:\n\n{item_lines}\n\n"
            f"Their current wardrobe:\n{wardrobe_str}\n\n"
            "Suggest 1–2 specific outfit combinations using the new item alongside pieces from their "
            "wardrobe. Name the exact wardrobe pieces by name. Include one styling detail per outfit "
            "(how to layer, tuck, or accessorise). Tone: casual, like a friend giving advice. "
            "4–6 sentences total."
        )

    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=450,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"[suggest_outfit error] Couldn't reach the LLM: {e}"


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption (Instagram/TikTok style).

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence caption string. Returns a descriptive error message
        string if outfit is empty — does NOT raise an exception.
    """
    if not outfit or not outfit.strip():
        return (
            "Couldn't create a fit card — no outfit suggestion was provided. "
            "Make sure suggest_outfit ran successfully before calling create_fit_card."
        )

    try:
        client = _get_groq_client()
    except ValueError as e:
        return f"[create_fit_card error] {e}"

    prompt = (
        "Write an Instagram caption for a thrift-find OOTD post.\n\n"
        f"The thrifted piece: {new_item.get('title', 'a thrifted find')} "
        f"— ${new_item.get('price', '?')} on {new_item.get('platform', 'depop')}\n"
        f"The full outfit: {outfit}\n\n"
        "Caption rules:\n"
        "- 2–4 sentences, casual and authentic — sounds like a real person, not a brand\n"
        "- Mention the item name, price, and platform naturally, exactly once each\n"
        "- Capture the specific vibe of the outfit in concrete terms\n"
        "- You may use 1–3 relevant emojis\n"
        "- Do NOT use hashtags\n\n"
        "Write only the caption text, nothing else."
    )

    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.92,   # higher = more varied captions on repeated calls
            max_tokens=220,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"[create_fit_card error] Couldn't reach the LLM: {e}"
