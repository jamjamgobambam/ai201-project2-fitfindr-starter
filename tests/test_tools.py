from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)

    assert isinstance(results, list)
    assert len(results) > 0
    assert all(isinstance(item, dict) for item in results)


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)

    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=50)

    assert all(item["price"] <= 50 for item in results)


def test_suggest_outfit_with_example_wardrobe():
    item = search_listings("vintage graphic tee", size=None, max_price=30)[0]
    outfit = suggest_outfit(item, get_example_wardrobe())

    assert isinstance(outfit, str)
    assert len(outfit.strip()) > 0


def test_suggest_outfit_with_empty_wardrobe():
    item = search_listings("vintage graphic tee", size=None, max_price=30)[0]
    outfit = suggest_outfit(item, get_empty_wardrobe())

    assert isinstance(outfit, str)
    assert len(outfit.strip()) > 0


def test_create_fit_card_success():
    item = search_listings("vintage graphic tee", size=None, max_price=30)[0]
    outfit = "Pair it with baggy jeans, black combat boots, and a denim jacket."
    fit_card = create_fit_card(outfit, item)

    assert isinstance(fit_card, str)
    assert len(fit_card.strip()) > 0


def test_create_fit_card_empty_outfit():
    item = search_listings("vintage graphic tee", size=None, max_price=30)[0]
    fit_card = create_fit_card("", item)

    assert "outfit suggestion was missing" in fit_card.lower()