import pytest
from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe, load_listings

# ── Tests for search_listings ────────────────────────────────────────────────

def test_search_returns_results():
    """Happy path: search returns a list of matching items."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_empty_results():
    """Failure mode: returns an empty list without crashing."""
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []

def test_search_price_filter():
    """Logic check: ensures max_price filter works."""
    results = search_listings("jacket", size=None, max_price=40)
    assert all(item.get("price", float('inf')) <= 40 for item in results)

# ── Tests for suggest_outfit ─────────────────────────────────────────────────

def test_suggest_outfit_populated_wardrobe():
    """Happy path: generates outfit string with a full wardrobe."""
    sample_item = load_listings()[0]
    wardrobe = get_example_wardrobe()
    
    result = suggest_outfit(sample_item, wardrobe)
    assert isinstance(result, str)
    assert len(result) > 0

def test_suggest_outfit_empty_wardrobe():
    """Failure mode: falls back to general advice without crashing."""
    sample_item = load_listings()[0]
    empty_wardrobe = get_empty_wardrobe()
    
    result = suggest_outfit(sample_item, empty_wardrobe)
    assert isinstance(result, str)
    assert len(result) > 0

# ── Tests for create_fit_card ────────────────────────────────────────────────

def test_create_fit_card_happy_path():
    """Happy path: generates a caption from an outfit string."""
    sample_item = load_listings()[0]
    outfit_text = "Pair these jeans with a white tee and combat boots."
    
    result = create_fit_card(outfit_text, sample_item)
    assert isinstance(result, str)
    assert len(result) > 0

def test_create_fit_card_empty_outfit():
    """Failure mode: returns hardcoded error if outfit string is empty."""
    sample_item = load_listings()[0]
    
    result = create_fit_card("", sample_item)
    assert result == "Could not generate fit card: outfit details missing."