"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Usage:
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
from utils.data_loader import load_listings


# ── Per-listing Unsplash photo IDs (same order as listings.json lst_001–040) ──
_PHOTO_IDS = [
    "1542767852-d4fd4c6c0a48",  # lst_001 vintage denim jeans
    "1523381210434-271e8be1f52b",  # lst_002 y2k crop top
    "1574634271046-6a87b3e9cadf",  # lst_003 flannel shirt
    "1556906783-b630bdd4d5a2",  # lst_004 track jacket
    "1596902852634-37a42b2d9bda",  # lst_005 corduroy rust pants
    "1503342217505-b0a15ec3261c",  # lst_006 graphic tee black
    "1591047139829-d91aecb6caea",  # lst_007 light wash denim jacket
    "1578587018452-892bacefd3fc",  # lst_008 chunky brown cardigan
    "1543163521-1bf539c55dd2",  # lst_009 platform mary janes
    "1614430590000-7f96d6b6c4e8",  # lst_010 purple teal windbreaker
    "1594380890612-1b02a23f9ce6",  # lst_011 khaki cargo pants
    "1556821840-3a63f8550bf3",  # lst_012 navy crewneck sweatshirt
    "1515886657613-9f3515b0c78f",  # lst_013 floral slip dress
    "1553062407-98eeb64c6a6a",  # lst_014 brown leather belt
    "1556905055-8f358a7a47b2",  # lst_015 black hoodie
    "1611312449408-fcece27cdbb7",  # lst_016 denim cutoff shorts
    "1558618666-fcd25c85cd64",  # lst_017 black mesh top
    "1507003211169-0a1dd7228f2d",  # lst_018 cream linen blazer
    "1542291026-7eec264c27ff",  # lst_019 white chunky platform sneakers
    "1589984662646-eb93e6f1a5a4",  # lst_020 burgundy henley
    "1631217868264-e5b90bb7e133",  # lst_021 olive trousers
    "1551028719-00167b16eac5",  # lst_022 black leather bomber
    "1517686469429-8bdb88b9f907",  # lst_023 cream crochet halter
    "1581803118522-7b72a50f7e9f",  # lst_024 green polo shirt
    "1622290291468-a28f7a7dc6a8",  # lst_025 natural linen wide leg
    "1538805060514-7be4e63eb9b4",  # lst_026 black biker shorts
    "1495105787522-5adfd8b8ef0c",  # lst_027 red college crewneck
    "1548036161-f5d7f91b29e5",  # lst_028 tan chelsea boots
    "1549298916-b41d501d3772",  # lst_029 sage green button down
    "1606293926249-ed32b9e6fc87",  # lst_030 argyle knit vest
    "1544966503-7d3ff04bb7c6",  # lst_031 dark wash baggy jeans
    "1564584217132-2271feaeb3c5",  # lst_032 olive shacket
    "1529720317453-c8da503f2051",  # lst_033 grey faded band tee
    "1521369909449-0cf41ebd5a53",  # lst_034 brown plaid bucket hat
    "1460353581641-37baddab0fa2",  # lst_035 off-white canvas sneakers
    "1540221652346-4f0d1b9d0b2f",  # lst_036 emerald velvet blazer
    "1441984904996-e0b6ba687e04",  # lst_037 faded black jeans
    "1576566588028-4147f3842f27",  # lst_038 medium wash denim vest
    "1584917865442-de89df76afd3",  # lst_039 tan leather shoulder bag
    "1554568218-a5e3e0e0a735",  # lst_040 pastel tie-dye long sleeve
]


def get_listings_with_images() -> list[dict]:
    """
    Load all mock listings and attach a per-listing Unsplash image URL.

    Each listing gets a unique photo matched to its specific title/style,
    not just a generic category image.

    Returns:
        List of listing dicts, each with an added 'image_url' key.
    """
    listings = load_listings()
    for i, item in enumerate(listings):
        if i < len(_PHOTO_IDS):
            photo_id = _PHOTO_IDS[i]
            item["image_url"] = (
                f"https://images.unsplash.com/photo-{photo_id}"
                "?w=600&h=420&fit=crop&crop=center&auto=format&q=80"
            )
        else:
            # Fallback by category if we somehow exceed the list
            fallback = {
                "tops":        "1521572267360-ee0c2909d518",
                "bottoms":     "1541099649105-f69ad21f3246",
                "outerwear":   "1551028719-00167b16eac5",
                "shoes":       "1542291026-7eec264c27ff",
                "accessories": "1553062407-98eeb64c6a6a",
            }
            cat = item.get("category", "tops")
            pid = fallback.get(cat, "1521572267360-ee0c2909d518")
            item["image_url"] = (
                f"https://images.unsplash.com/photo-{pid}"
                "?w=600&h=420&fit=crop&auto=format&q=80"
            )
    return listings


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """Initialize a fresh session dict for one user interaction."""
    return {
        "query":             query,
        "parsed":            {},       # extracted description / size / max_price
        "search_results":    [],       # list of matching listing dicts
        "selected_item":     None,     # top result → input to suggest_outfit
        "wardrobe":          wardrobe,
        "outfit_suggestion": None,     # string from suggest_outfit
        "fit_card":          None,     # string from create_fit_card
        "error":             None,     # set if interaction ended early
    }


# ── query parser ──────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a natural language query
    using regex patterns.

    Examples handled:
        "vintage graphic tee under $30, size M"
        "black combat boots size 8, max $50"
        "flannel XL below 25 dollars"
    """
    parsed: dict = {"description": query, "size": None, "max_price": None}

    # ── price ─────────────────────────────────────────────────────────────────
    price_pattern = re.compile(
        r'(?:under|below|max(?:imum)?|less\s+than|no\s+more\s+than|at\s+most)'
        r'\s*\$?\s*(\d+(?:\.\d+)?)',
        re.IGNORECASE,
    )
    m = price_pattern.search(query)
    if not m:
        # "$X or less" / "$X max"
        m = re.search(
            r'\$\s*(\d+(?:\.\d+)?)\s*(?:or\s+less|max(?:imum)?)', query, re.IGNORECASE
        )
    if m:
        parsed["max_price"] = float(m.group(1))

    # ── size ──────────────────────────────────────────────────────────────────
    size_m = re.search(r'\bsize\s+([A-Za-z0-9/]+)', query, re.IGNORECASE)
    if size_m:
        parsed["size"] = size_m.group(1)
    else:
        # Standalone standard sizes: XS, S, M, L, XL, XXL, S/M, M/L, W28, W30 L32 …
        size_m2 = re.search(
            r'\b(XXS|XS|S/M|M/L|L/XL|XL/XXL|XXL|XL|[SML]|W\d{2}(?:\s+L\d{2})?)\b',
            query,
        )
        if size_m2:
            parsed["size"] = size_m2.group(1)

    # ── clean description ─────────────────────────────────────────────────────
    desc = query
    desc = re.sub(
        r'(?:under|below|max(?:imum)?|less\s+than|no\s+more\s+than|at\s+most)'
        r'\s*\$?\s*\d+(?:\.\d+)?',
        '', desc, flags=re.IGNORECASE,
    )
    desc = re.sub(r'\$\s*\d+(?:\.\d+)?\s*(?:or\s+less|max(?:imum)?)?', '', desc, flags=re.IGNORECASE)
    desc = re.sub(r'\bsize\s+[A-Za-z0-9/]+\b', '', desc, flags=re.IGNORECASE)
    desc = re.sub(
        r'\b(XXS|XS|S/M|M/L|L/XL|XL/XXL|XXL|XL|[SML]|W\d{2}(?:\s+L\d{2})?)\b',
        '', desc,
    )
    desc = re.sub(r'\s+', ' ', desc).strip(" ,.;-—")
    parsed["description"] = desc if desc else query

    return parsed


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Planning loop (conditional — not a fixed sequence):

        1. Parse query → extract description, size, max_price
        2. search_listings(description, size, max_price)
              → empty?  set error, STOP (do not call suggest_outfit with nothing)
              → results? pick top result, continue
        3. suggest_outfit(selected_item, wardrobe)
        4. create_fit_card(outfit_suggestion, selected_item)
        5. Return completed session

    Args:
        query:    Natural language user request.
        wardrobe: User's wardrobe dict from get_example_wardrobe() or
                  get_empty_wardrobe().

    Returns:
        Session dict. Check session["error"] first — if not None the
        interaction ended early and outfit_suggestion / fit_card will be None.
    """
    session = _new_session(query, wardrobe)

    # ── Step 1: parse ──────────────────────────────────────────────────────────
    session["parsed"] = _parse_query(query)
    p = session["parsed"]

    # ── Step 2: search ─────────────────────────────────────────────────────────
    results = search_listings(
        description=p["description"],
        size=p.get("size"),
        max_price=p.get("max_price"),
    )
    session["search_results"] = results

    if not results:
        parts = ["No listings matched your search."]
        if p.get("max_price"):
            parts.append(f"Try raising the price limit above ${p['max_price']:.0f}.")
        if p.get("size"):
            parts.append(f"Or remove the size filter ('{p['size']}') to see more options.")
        parts.append("You can also try different keywords — e.g. a colour, style tag, or brand.")
        session["error"] = " ".join(parts)
        return session

    # ── Step 3: pick top result ────────────────────────────────────────────────
    session["selected_item"] = results[0]

    # ── Step 4: outfit suggestion ──────────────────────────────────────────────
    outfit = suggest_outfit(session["selected_item"], wardrobe)
    session["outfit_suggestion"] = outfit

    # Treat LLM error strings as soft errors but continue so the UI still shows
    # the found listing — only the fit card will be affected.
    if outfit.startswith("[suggest_outfit error]"):
        session["outfit_suggestion"] = outfit  # keep error text visible in UI

    # ── Step 5: fit card ───────────────────────────────────────────────────────
    fit_card = create_fit_card(session["outfit_suggestion"], session["selected_item"])
    session["fit_card"] = fit_card

    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    s = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if s["error"]:
        print(f"Error: {s['error']}")
    else:
        print(f"Found:    {s['selected_item']['title']}  (${s['selected_item']['price']})")
        print(f"\nOutfit:   {s['outfit_suggestion']}")
        print(f"\nFit card: {s['fit_card']}")

    print("\n\n=== No-results path ===\n")
    s2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {s2['error']}")

    print("\n\n=== Empty wardrobe path ===\n")
    s3 = run_agent(
        query="vintage polo shirt size M",
        wardrobe=get_empty_wardrobe(),
    )
    if s3["error"]:
        print(f"Error: {s3['error']}")
    else:
        print(f"Found:    {s3['selected_item']['title']}")
        print(f"\nOutfit:   {s3['outfit_suggestion']}")
        print(f"\nFit card: {s3['fit_card']}")
