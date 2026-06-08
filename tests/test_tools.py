import pytest
from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe, load_listings

# --- search_listings tests ---

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0
    assert any("Graphic Tee" in item["title"] for item in results)

def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []

def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=30)
    for item in results:
        assert item["price"] <= 30

def test_search_size_filter():
    results = search_listings("jacket", size="M", max_price=None)
    for item in results:
        assert "M" in item["size"].upper()

# --- suggest_outfit tests ---

def test_suggest_outfit_happy_path():
    listings = load_listings()
    new_item = next(item for item in listings if item["id"] == "lst_006")
    wardrobe = get_example_wardrobe()
    suggestion = suggest_outfit(new_item, wardrobe)
    assert isinstance(suggestion, str)
    assert len(suggestion) > 0

def test_suggest_outfit_empty_wardrobe():
    listings = load_listings()
    new_item = next(item for item in listings if item["id"] == "lst_006")
    wardrobe = get_empty_wardrobe()
    advice = suggest_outfit(new_item, wardrobe)
    assert isinstance(advice, str)
    assert len(advice) > 0
    # LLM advice should be descriptive even without wardrobe
    assert len(advice.split()) > 20

# --- create_fit_card tests ---

def test_create_fit_card_happy_path():
    listings = load_listings()
    new_item = next(item for item in listings if item["id"] == "lst_006")
    outfit = "Pair with baggy jeans and sneakers."
    caption = create_fit_card(outfit, new_item)
    assert isinstance(caption, str)
    assert len(caption) > 0
    assert str(new_item["price"]) in caption
    assert new_item["platform"] in caption.lower()

def test_create_fit_card_missing_outfit():
    listings = load_listings()
    new_item = next(item for item in listings if item["id"] == "lst_006")
    result = create_fit_card("", new_item)
    assert "missing outfit details" in result.lower()
