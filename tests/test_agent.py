from agent import run_agent
from utils.data_loader import get_example_wardrobe


def test_run_agent_happy_path(monkeypatch):
    fake_item = {
        "id": "lst_test",
        "title": "Test Graphic Tee",
        "description": "A vintage graphic tee",
        "category": "tops",
        "style_tags": ["vintage", "graphic tee", "streetwear"],
        "size": "M",
        "condition": "good",
        "price": 24.00,
        "colors": ["black"],
        "brand": None,
        "platform": "depop",
    }

    def fake_search_listings(description, size=None, max_price=None):
        assert description in {"vintage graphic tee", "a vintage graphic tee"}
        assert max_price == 30.0
        return [fake_item]

    def fake_suggest_outfit(new_item, wardrobe):
        assert new_item == fake_item
        assert "items" in wardrobe
        return "Pair the Test Graphic Tee with baggy jeans and chunky sneakers."

    def fake_create_fit_card(outfit, new_item):
        assert outfit == "Pair the Test Graphic Tee with baggy jeans and chunky sneakers."
        assert new_item == fake_item
        return "Found this Test Graphic Tee on Depop for $24. Easy streetwear fit."

    monkeypatch.setattr("agent.search_listings", fake_search_listings)
    monkeypatch.setattr("agent.suggest_outfit", fake_suggest_outfit)
    monkeypatch.setattr("agent.create_fit_card", fake_create_fit_card)

    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )

    assert session["error"] is None
    assert session["parsed"]["description"] in {"vintage graphic tee", "a vintage graphic tee"}
    assert session["parsed"]["max_price"] == 30.0
    assert session["search_results"] == [fake_item]
    assert session["selected_item"] == fake_item
    assert session["outfit_suggestion"]
    assert session["fit_card"]


def test_run_agent_no_results_stops_early(monkeypatch):
    calls = {
        "suggest_outfit_called": False,
        "create_fit_card_called": False,
    }

    def fake_search_listings(description, size=None, max_price=None):
        return []

    def fake_suggest_outfit(new_item, wardrobe):
        calls["suggest_outfit_called"] = True
        return "This should not be called."

    def fake_create_fit_card(outfit, new_item):
        calls["create_fit_card_called"] = True
        return "This should not be called."

    monkeypatch.setattr("agent.search_listings", fake_search_listings)
    monkeypatch.setattr("agent.suggest_outfit", fake_suggest_outfit)
    monkeypatch.setattr("agent.create_fit_card", fake_create_fit_card)

    session = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )

    assert session["error"] is not None
    assert "couldn't find any listings" in session["error"].lower()
    assert session["search_results"] == []
    assert session["selected_item"] is None
    assert session["outfit_suggestion"] is None
    assert session["fit_card"] is None
    assert calls["suggest_outfit_called"] is False
    assert calls["create_fit_card_called"] is False


def test_run_agent_empty_query():
    session = run_agent(
        query="",
        wardrobe=get_example_wardrobe(),
    )

    assert session["error"] is not None
    assert "please enter" in session["error"].lower()
    assert session["fit_card"] is None