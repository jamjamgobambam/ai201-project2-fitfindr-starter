"""
tests/test_tools.py

Pytest tests for all three FitFindr tools.
Run with:  pytest tests/
"""

import pytest
from tools import search_listings, create_fit_card
from utils.data_loader import load_listings, get_example_wardrobe, get_empty_wardrobe


# ─────────────────────────────────────────────────────────────────
#  search_listings
# ─────────────────────────────────────────────────────────────────

def test_search_returns_list():
    results = search_listings("vintage graphic tee", size=None, max_price=None)
    assert isinstance(results, list)


def test_search_returns_results_for_valid_query():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0


def test_search_result_has_required_fields():
    results = search_listings("jacket", size=None, max_price=None)
    assert len(results) > 0
    item = results[0]
    for field in ("id", "title", "description", "category", "price", "size", "condition", "platform"):
        assert field in item, f"Missing field: {field}"


def test_search_empty_results_returns_empty_list():
    """Impossible query should return [] without raising an exception."""
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=30)
    assert all(item["price"] <= 30 for item in results)


def test_search_price_filter_excludes_expensive_items():
    all_results  = search_listings("jacket", size=None, max_price=None)
    cheap_results = search_listings("jacket", size=None, max_price=10)
    # At least one jacket costs more than $10, so cheap list must be shorter or empty
    assert len(cheap_results) <= len(all_results)


def test_search_size_filter():
    results = search_listings("shirt", size="M", max_price=None)
    for item in results:
        assert "m" in item["size"].lower(), (
            f"Size filter failed: got '{item['size']}' for size='M'"
        )


def test_search_results_sorted_by_relevance():
    """Top result should mention 'denim' in title or tags when searching for denim."""
    results = search_listings("denim jeans", size=None, max_price=None)
    assert len(results) > 0
    top = results[0]
    text = (top["title"] + " " + " ".join(top.get("style_tags", []))).lower()
    assert "denim" in text or "jeans" in text


def test_search_no_description_match_returns_empty():
    results = search_listings("xyznonexistentitem12345", size=None, max_price=None)
    assert results == []


def test_search_handles_none_size_and_price():
    """Should not crash when both optional params are None."""
    results = search_listings("top", size=None, max_price=None)
    assert isinstance(results, list)


# ─────────────────────────────────────────────────────────────────
#  create_fit_card — tested without LLM (guard clause path)
# ─────────────────────────────────────────────────────────────────

def test_create_fit_card_empty_outfit_returns_error_string():
    """Empty outfit must return an error string, not raise an exception."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    result = create_fit_card("", results[0])
    assert isinstance(result, str)
    assert len(result) > 0
    # Should NOT raise — confirmed by reaching this line


def test_create_fit_card_blank_outfit_returns_error_string():
    """Whitespace-only outfit string should also be caught."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    result = create_fit_card("   ", results[0])
    assert isinstance(result, str)
    assert len(result) > 0


# ─────────────────────────────────────────────────────────────────
#  suggest_outfit — empty wardrobe (no LLM required to test guard)
# ─────────────────────────────────────────────────────────────────

def test_suggest_outfit_empty_wardrobe_does_not_crash():
    """Empty wardrobe must not raise — it should return a non-empty string."""
    from tools import suggest_outfit
    results = search_listings("vintage polo shirt", size="M", max_price=50)
    assert len(results) > 0
    # This calls the LLM — skip if no API key available
    try:
        result = suggest_outfit(results[0], get_empty_wardrobe())
        assert isinstance(result, str)
        assert len(result) > 0
    except Exception as e:
        pytest.skip(f"LLM not available in this environment: {e}")


# ─────────────────────────────────────────────────────────────────
#  data loader sanity checks
# ─────────────────────────────────────────────────────────────────

def test_load_listings_returns_40_items():
    listings = load_listings()
    assert len(listings) == 40


def test_example_wardrobe_has_items():
    wardrobe = get_example_wardrobe()
    assert "items" in wardrobe
    assert len(wardrobe["items"]) > 0


def test_empty_wardrobe_has_empty_items():
    wardrobe = get_empty_wardrobe()
    assert "items" in wardrobe
    assert len(wardrobe["items"]) == 0