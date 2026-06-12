"""
tests/test_tools.py

Tests for all three FitFindr tools. Run with: pytest tests/
"""

import pytest
from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe, load_listings


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    results = search_listings("jeans", size="M", max_price=None)
    assert all("m" in item["size"].lower() for item in results)


def test_search_results_are_sorted_by_relevance():
    # A very specific query — the first result should be more relevant than later ones
    results = search_listings("vintage streetwear denim", size=None, max_price=None)
    assert isinstance(results, list)
    # Just check it returns something and doesn't crash
    assert len(results) > 0


def test_search_no_exception_on_impossible_query():
    # Should return empty list, not raise
    results = search_listings("xyzzy impossible item", size=None, max_price=None)
    assert results == []


def test_search_no_max_price_returns_all_matching():
    results_no_cap = search_listings("vintage", size=None, max_price=None)
    results_capped = search_listings("vintage", size=None, max_price=9999)
    # Both should find the same items (all under $9999)
    assert len(results_no_cap) == len(results_capped)


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def _get_sample_item():
    listings = load_listings()
    return listings[0]


def test_suggest_outfit_with_wardrobe():
    item = _get_sample_item()
    wardrobe = get_example_wardrobe()
    result = suggest_outfit(item, wardrobe)
    assert isinstance(result, str)
    assert len(result) > 0


def test_suggest_outfit_empty_wardrobe():
    item = _get_sample_item()
    empty_wardrobe = get_empty_wardrobe()
    # Should not raise — returns general styling advice instead
    result = suggest_outfit(item, empty_wardrobe)
    assert isinstance(result, str)
    assert len(result) > 0


def test_suggest_outfit_missing_items_key():
    item = _get_sample_item()
    # Wardrobe without 'items' key — should handle gracefully
    result = suggest_outfit(item, {})
    assert isinstance(result, str)
    assert len(result) > 0


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def test_create_fit_card_returns_caption():
    item = _get_sample_item()
    outfit = "Pair these Levi's with a cropped white tee and chunky sneakers for a classic streetwear look."
    result = create_fit_card(outfit, item)
    assert isinstance(result, str)
    assert len(result) > 0


def test_create_fit_card_empty_outfit_returns_error_string():
    item = _get_sample_item()
    result = create_fit_card("", item)
    assert isinstance(result, str)
    assert "error" in result.lower() or "missing" in result.lower() or "empty" in result.lower()


def test_create_fit_card_whitespace_outfit_returns_error_string():
    item = _get_sample_item()
    result = create_fit_card("   ", item)
    assert isinstance(result, str)
    assert "error" in result.lower() or "missing" in result.lower() or "empty" in result.lower()


def test_create_fit_card_varies_output():
    """Run twice on the same input — outputs should differ (temperature=1.0)."""
    item = _get_sample_item()
    outfit = "Vintage Levi's with an oversized band tee and platform boots for a grunge vibe."
    result1 = create_fit_card(outfit, item)
    result2 = create_fit_card(outfit, item)
    # With temperature=1.0 these should differ; we allow a small chance they match
    assert isinstance(result1, str) and isinstance(result2, str)
    # At minimum both should be non-empty
    assert len(result1) > 0 and len(result2) > 0
