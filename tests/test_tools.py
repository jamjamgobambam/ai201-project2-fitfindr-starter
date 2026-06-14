import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import create_fit_card, search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe


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


def test_search_empty_description_returns_empty_list():
    results = search_listings("", size=None, max_price=50)

    assert results == []


def test_search_size_filter_matches_case_insensitive():
    results = search_listings("y2k baby tee", size="m", max_price=30)

    assert len(results) > 0
    assert all("m" in item["size"].lower() for item in results)


@pytest.mark.parametrize(
    ("query", "size", "max_price"),
    [
        ("vintage graphic tee", None, 30),
        ("90s track jacket", "M", None),
        ("flowy midi skirt", None, 40),
        ("denim jacket", None, 45),
    ],
)
def test_search_success_queries(query, size, max_price):
    results = search_listings(query, size=size, max_price=max_price)

    assert isinstance(results, list)
    assert len(results) > 0


@pytest.mark.parametrize(
    ("query", "size", "max_price"),
    [
        ("designer ballgown", "XXS", 5),
        ("neon ski suit", "toddler", 3),
    ],
)
def test_search_failure_queries(query, size, max_price):
    results = search_listings(query, size=size, max_price=max_price)

    assert results == []


def test_suggest_outfit_with_example_wardrobe(monkeypatch):
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]

    def fake_call_groq(*args, **kwargs):
        return "Pair it with your baggy straight-leg jeans and chunky white sneakers."

    monkeypatch.setattr("tools._call_groq", fake_call_groq)

    suggestion = suggest_outfit(item, get_example_wardrobe())

    assert isinstance(suggestion, str)
    assert "baggy straight-leg jeans" in suggestion


def test_suggest_outfit_missing_item():
    suggestion = suggest_outfit({}, get_example_wardrobe())

    assert "selected listing" in suggestion.lower()


def test_suggest_outfit_empty_wardrobe(monkeypatch):
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]

    def fake_call_groq(*args, **kwargs):
        return "Style it with relaxed denim, simple sneakers, and one light layer."

    monkeypatch.setattr("tools._call_groq", fake_call_groq)

    suggestion = suggest_outfit(item, get_empty_wardrobe())

    assert isinstance(suggestion, str)
    assert suggestion != ""


def test_suggest_outfit_empty_wardrobe_llm_failure(monkeypatch):
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]

    def fake_call_groq(*args, **kwargs):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr("tools._call_groq", fake_call_groq)

    suggestion = suggest_outfit(item, get_empty_wardrobe())

    assert "wardrobe is empty" in suggestion.lower()
    assert "cannot personalize" in suggestion.lower()


def test_suggest_outfit_example_wardrobe_llm_failure(monkeypatch):
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]

    def fake_call_groq(*args, **kwargs):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr("tools._call_groq", fake_call_groq)

    suggestion = suggest_outfit(item, get_example_wardrobe())

    assert isinstance(suggestion, str)
    assert suggestion.startswith("Try")


def test_create_fit_card_empty_outfit():
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]

    result = create_fit_card("", item)

    assert "complete outfit" in result.lower()


def test_create_fit_card_whitespace_outfit():
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]

    result = create_fit_card("   ", item)

    assert "complete outfit" in result.lower()


def test_create_fit_card_missing_item():
    result = create_fit_card("Style it with jeans.", {})

    assert "selected listing" in result.lower()


def test_create_fit_card_returns_caption(monkeypatch):
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]

    def fake_call_groq(*args, **kwargs):
        return "Found this tee on Depop and styled it with baggy denim. Easy everyday fit."

    monkeypatch.setattr("tools._call_groq", fake_call_groq)

    caption = create_fit_card("Style it with baggy denim and sneakers.", item)

    assert isinstance(caption, str)
    assert "Depop" in caption


def test_create_fit_card_llm_failure_returns_fallback(monkeypatch):
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]

    def fake_call_groq(*args, **kwargs):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr("tools._call_groq", fake_call_groq)

    caption = create_fit_card("Style it with baggy denim and sneakers.", item)

    assert item["title"] in caption
    assert item["platform"] in caption
