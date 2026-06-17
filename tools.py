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
import re
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
    # Replace this with your implementation
   

    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.
    """
    listings = load_listings()
    results = []

    # Tokenize the description into unique lowercase keywords
    # This regex pulls out alphanumeric words, ignoring punctuation
    keywords = set(re.findall(r'\w+', description.lower()))

    for item in listings:
        # 1. Filter by max_price (inclusive)
        if max_price is not None and item.get("price", float('inf')) > max_price:
            continue

        # 2. Filter by size (case-insensitive substring match)
        if size is not None:
            item_size = item.get("size", "").lower()
            if size.lower() not in item_size:
                continue

        # 3. Score by keyword overlap
        # Create a giant string of the item's details to check for keywords
        searchable_text = (
            f"{item.get('title', '')} "
            f"{item.get('description', '')} "
            f"{' '.join(item.get('style_tags', []))} "
            f"{' '.join(item.get('colors', []))} "
            f"{item.get('category', '')}"
        ).lower()

        score = sum(1 for word in keywords if word in searchable_text)

        # 4. Keep only items with a score > 0
        if score > 0:
            results.append((score, item))

    # 5. Sort by score descending (highest first)
    results.sort(key=lambda x: x[0], reverse=True)

    # Return just the item dictionaries (drop the score)
    return [item for score, item in results]


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
    # Replace this with your implementation
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.
    """
    client = _get_groq_client()
    
    # Extract details about the new item
    item_title = new_item.get("title", "this piece")
    item_desc = new_item.get("description", "")
    
    # Safely get the list of items from the wardrobe dictionary
    wardrobe_items = wardrobe.get("items", [])
    
    system_prompt = (
        "You are a stylish, casual, and helpful fashion assistant. "
        "Provide 1-2 concise, practical outfit ideas. Keep your response under 4 sentences."
    )
    
    # 1. Check if the wardrobe is empty
    if not wardrobe_items:
        # 2. General styling advice prompt
        user_prompt = (
            f"I just found this item: '{item_title}' ({item_desc}). "
            "I haven't added anything to my digital wardrobe yet. "
            "Could you give me general advice on what kinds of pieces and colors would pair well with this?"
        )
    else:
        # 3. Specific styling advice prompt
        # Format the wardrobe items into a readable list for the LLM
        formatted_wardrobe = "\n".join([
            f"- {w.get('name')} (Category: {w.get('category')}, Vibes: {', '.join(w.get('style_tags', []))})"
            for w in wardrobe_items
        ])
        
        user_prompt = (
            f"I just found this item: '{item_title}' ({item_desc}). "
            f"Here is what I currently have in my wardrobe:\n{formatted_wardrobe}\n\n"
            "Based strictly on the items in my wardrobe, suggest 1-2 outfit combinations "
            "incorporating the new item. Name the specific pieces from my wardrobe."
        )
        
# 4. Call the LLM
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="llama-3.3-70b-versatile",  # Updated, supported model 
            temperature=0.7, 
        )
        return chat_completion.choices[0].message.content.strip()
    except Exception as e:
        # TEMPORARY: Print the exact error to the terminal
        print(f"\n[DEBUG] Groq API Error: {e}\n")
        
        # Fallback to prevent crashing
        return "I think this piece is great, but I'm having trouble coming up with an outfit right now!"

# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.
    """
    # 1. Guard against an empty or whitespace-only outfit string
    if not outfit or not outfit.strip():
        return "Could not generate fit card: outfit details missing."

    client = _get_groq_client()
    
    # Extract item details
    item_title = new_item.get("title", "this piece")
    price = new_item.get("price", "a great price")
    platform = new_item.get("platform", "the thrift store")

    # 2. Build the LLM prompts
    system_prompt = (
        "You are a stylish fashion creator on TikTok and Instagram. "
        "Write a short, engaging, and authentic caption (2-4 sentences) for an OOTD post."
    )
    
    user_prompt = (
        f"I just thrifted '{item_title}' for ${price} on {platform}. "
        f"Here is how I'm styling it: {outfit}\n\n"
        "Write a caption for this outfit. Mention the item name, the price, and the platform naturally. "
        "Capture the specific vibe of the outfit. Do not sound too robotic or corporate."
    )

    # 3. Call the LLM
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.8,
        )
        return chat_completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"\n[DEBUG] Groq API Error: {e}\n")
        return "Just scored a new piece and put together a great fit!"


# ── Local Testing ─────────────────────────────────────────────────────────────

# def test_search_listings():
#     print("=== Testing search_listings ===")
    
#     # Example 1: Search with all parameters
#     print("\nTest 1: 'vintage graphic tee', under $30, Size M")
#     results_1 = search_listings(description="vintage graphic tee", size="M", max_price=30.0)
#     for res in results_1:
#         print(f" - [${res['price']}] {res['title']} (Size: {res['size']})")
        
#     # Example 2: Broad search, no size or price limits
#     print("\nTest 2: 'leather bomber'")
#     results_2 = search_listings(description="leather bomber")
#     for res in results_2:
#         print(f" - [${res['price']}] {res['title']} (Size: {res['size']})")

#     # Example 3: A search designed to fail (empty result)
#     print("\nTest 3: 'neon green space suit', under $5")
#     results_3 = search_listings(description="neon green space suit", max_price=5.0)
#     print(f"Found {len(results_3)} results. (Expected 0)")

# if __name__ == "__main__":
#     test_search_listings()

# ── Local Testing ─────────────────────────────────────────────────────────────

# ── Local Testing ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe, load_listings
    
    print("=== Testing Tools ===")
    
    # Setup: Grab a sample item from listings to use as our "new item"
    listings = load_listings()
    sample_item = listings[0] # "Vintage Levi's 501 Jeans — Medium Wash"
    
    print(f"\nTarget Item: {sample_item['title']}")
    
    # Test A: suggest_outfit with an EMPTY wardrobe
    print("\n--- Test A: Empty Wardrobe ---")
    empty_wardrobe = get_empty_wardrobe()
    outfit_general = suggest_outfit(sample_item, empty_wardrobe)
    print(outfit_general)
    
    # Test B: suggest_outfit with a FULL wardrobe
    print("\n--- Test B: Populated Wardrobe ---")
    full_wardrobe = get_example_wardrobe()
    outfit_specific = suggest_outfit(sample_item, full_wardrobe)
    print(outfit_specific)

    # Test C: create_fit_card (Happy Path)
    print("\n--- Test C: Fit Card Generation ---")
    # We pass in the specific outfit string we generated in Test B
    fit_card = create_fit_card(outfit_specific, sample_item)
    print(fit_card)

    # Test D: create_fit_card with an empty string (Error Handling)
    print("\n--- Test D: Fit Card with missing outfit ---")
    error_card = create_fit_card("", sample_item)
    print(error_card)
    