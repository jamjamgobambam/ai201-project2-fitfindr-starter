from app import handle_query


def test_handle_query_empty_query():
    listing_text, outfit_suggestion, fit_card = handle_query("", "Example wardrobe")

    assert "please enter" in listing_text.lower()
    assert outfit_suggestion == ""
    assert fit_card == ""


def test_handle_query_error_path(monkeypatch):
    def fake_run_agent(query, wardrobe):
        return {
            "query": query,
            "parsed": {},
            "search_results": [],
            "selected_item": None,
            "wardrobe": wardrobe,
            "outfit_suggestion": None,
            "fit_card": None,
            "error": "I couldn't find any listings for that request.",
        }

    monkeypatch.setattr("app.run_agent", fake_run_agent)

    listing_text, outfit_suggestion, fit_card = handle_query(
        "designer ballgown size XXS under $5",
        "Example wardrobe",
    )

    assert "couldn't find any listings" in listing_text.lower()
    assert outfit_suggestion == ""
    assert fit_card == ""


def test_handle_query_success_path(monkeypatch):
    fake_item = {
        "id": "lst_test",
        "title": "Test Graphic Tee",
        "description": "A vintage graphic tee",
        "category": "tops",
        "style_tags": ["vintage", "graphic tee"],
        "size": "M",
        "condition": "good",
        "price": 24.00,
        "colors": ["black"],
        "brand": None,
        "platform": "depop",
    }

    def fake_run_agent(query, wardrobe):
        return {
            "query": query,
            "parsed": {
                "description": "vintage graphic tee",
                "size": None,
                "max_price": 30.0,
            },
            "search_results": [fake_item],
            "selected_item": fake_item,
            "wardrobe": wardrobe,
            "outfit_suggestion": "Pair it with baggy jeans and chunky sneakers.",
            "fit_card": "Found this Test Graphic Tee on Depop for $24.",
            "error": None,
        }

    monkeypatch.setattr("app.run_agent", fake_run_agent)

    listing_text, outfit_suggestion, fit_card = handle_query(
        "vintage graphic tee under $30",
        "Example wardrobe",
    )

    assert "Test Graphic Tee" in listing_text
    assert "Price: $24.00" in listing_text
    assert "Platform: depop" in listing_text
    assert outfit_suggestion == "Pair it with baggy jeans and chunky sneakers."
    assert fit_card == "Found this Test Graphic Tee on Depop for $24."


def test_handle_query_empty_wardrobe_choice(monkeypatch):
    def fake_run_agent(query, wardrobe):
        assert wardrobe["items"] == []

        return {
            "query": query,
            "parsed": {},
            "search_results": [],
            "selected_item": None,
            "wardrobe": wardrobe,
            "outfit_suggestion": None,
            "fit_card": None,
            "error": "No results for test.",
        }

    monkeypatch.setattr("app.run_agent", fake_run_agent)

    listing_text, outfit_suggestion, fit_card = handle_query(
        "black combat boots size 8",
        "Empty wardrobe (new user)",
    )

    assert "no results for test" in listing_text.lower()
    assert outfit_suggestion == ""
    assert fit_card == ""
    