"""
tests/test_tools.py

Unit tests for the three FitFindr tools in tools.py.

- search_listings is pure logic (no network) and is tested directly.
- suggest_outfit and create_fit_card call the Groq LLM, so the Groq client is
  replaced with a fake (see `patch_groq` fixture) — these tests run offline and
  need no GROQ_API_KEY. The fake also records the prompt sent so we can assert
  which code path was taken.

Run from the project root:  pytest
"""

import sys
from pathlib import Path

import pytest

# Make sure the project root is importable when pytest is run from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tools  # noqa: E402
from tools import search_listings, suggest_outfit, create_fit_card  # noqa: E402


# ── Fake Groq client ────────────────────────────────────────────────────────

class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeCompletions:
    def __init__(self, client):
        self._client = client

    def create(self, *, model, messages, max_tokens=None, temperature=None):
        # Record what the tool sent so tests can inspect the chosen code path.
        self._client.last_call = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        self._client.last_prompt = messages[-1]["content"]
        return _FakeResponse(self._client.reply)


class _FakeChat:
    def __init__(self, client):
        self.completions = _FakeCompletions(client)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)] if content is not None else []


class FakeGroqClient:
    """Stand-in for groq.Groq — returns a canned reply and records the prompt."""

    def __init__(self, reply="canned LLM reply"):
        self.reply = reply
        self.last_call = None
        self.last_prompt = None
        self.chat = _FakeChat(self)


@pytest.fixture
def fake_client():
    return FakeGroqClient()


@pytest.fixture
def patch_groq(monkeypatch, fake_client):
    """Replace tools._get_groq_client so LLM tools use the fake, offline client."""
    monkeypatch.setattr(tools, "_get_groq_client", lambda: fake_client)
    return fake_client


# Minimal listing used by the LLM-backed tools.
SAMPLE_ITEM = {
    "id": "lst_999",
    "title": "Vintage Band Tee",
    "category": "tops",
    "style_tags": ["vintage", "graphic tee"],
    "price": 25.0,
    "colors": ["black"],
    "condition": "good",
    "platform": "depop",
}


# ── Tool 1: search_listings ───────────────────────────────────────────────────

class TestSearchListings:
    def test_returns_matches_for_relevant_description(self):
        results = search_listings("vintage denim jeans")
        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, dict) for r in results)

    def test_no_match_returns_empty_list_not_exception(self):
        # Failure mode: nothing matches -> empty list, never raises.
        results = search_listings("zzzzqqqq nonexistentkeyword xyzzy")
        assert results == []

    def test_empty_description_returns_empty_list(self):
        # Failure mode: empty query has no keywords, so every score is 0.
        results = search_listings("")
        assert results == []

    def test_max_price_filters_out_expensive_items(self):
        # Failure mode: price ceiling must exclude anything above it.
        max_price = 20.0
        results = search_listings("vintage", max_price=max_price)
        assert all(r["price"] <= max_price for r in results)

    def test_max_price_zero_excludes_everything(self):
        # Edge: an impossibly low ceiling yields no results, no exception.
        results = search_listings("vintage", max_price=0.0)
        assert results == []

    def test_size_filter_is_case_insensitive(self):
        # Failure mode: size matching must be case-insensitive substring.
        lower = search_listings("vintage", size="m")
        upper = search_listings("vintage", size="M")
        assert [r["id"] for r in lower] == [r["id"] for r in upper]
        for r in lower:
            assert "m" in r["size"].lower()

    def test_results_sorted_by_relevance_descending(self):
        # Failure mode: better keyword overlap must rank first.
        results = search_listings("vintage denim jeans levi's")
        desc_words = set("vintage denim jeans levi's".lower().split())

        def score(listing):
            searchable = " ".join([
                listing.get("title", ""),
                listing.get("description", ""),
                " ".join(listing.get("style_tags", [])),
                listing.get("category", ""),
                listing.get("brand", "") or "",
            ]).lower()
            return len(desc_words & set(searchable.split()))

        scores = [score(r) for r in results]
        assert scores == sorted(scores, reverse=True)


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

class TestSuggestOutfit:
    def test_empty_wardrobe_returns_nonempty_string(self, patch_groq):
        # Failure mode: empty wardrobe must not raise / return "".
        patch_groq.reply = "Pair it with neutral basics for a clean look."
        result = suggest_outfit(SAMPLE_ITEM, {"items": []})
        assert isinstance(result, str)
        assert result.strip() != ""

    def test_empty_wardrobe_takes_general_advice_path(self, patch_groq):
        # The empty branch should send the "don't have details" style prompt.
        suggest_outfit(SAMPLE_ITEM, {"items": []})
        assert "wardrobe" in patch_groq.last_prompt.lower()
        assert "don't have details" in patch_groq.last_prompt.lower()

    def test_missing_items_key_treated_as_empty(self, patch_groq):
        # Failure mode: wardrobe with no 'items' key must be handled gracefully.
        result = suggest_outfit(SAMPLE_ITEM, {})
        assert isinstance(result, str)
        assert result.strip() != ""

    def test_populated_wardrobe_includes_item_names_in_prompt(self, patch_groq):
        wardrobe = {
            "items": [
                {"name": "White Sneakers", "category": "shoes", "color": "white"},
                {"name": "Black Jeans", "category": "bottoms", "color": "black"},
            ]
        }
        result = suggest_outfit(SAMPLE_ITEM, wardrobe)
        assert isinstance(result, str)
        assert result.strip() != ""
        assert "White Sneakers" in patch_groq.last_prompt
        assert "Black Jeans" in patch_groq.last_prompt

    def test_no_choices_returns_empty_string(self, patch_groq):
        # Defensive path: an LLM response with no choices returns "".
        patch_groq.reply = None
        result = suggest_outfit(SAMPLE_ITEM, {"items": []})
        assert result == ""


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

class TestCreateFitCard:
    def test_empty_outfit_returns_error_string_without_llm(self, patch_groq):
        # Failure mode: empty outfit -> descriptive message, no LLM call, no raise.
        result = create_fit_card("", SAMPLE_ITEM)
        assert isinstance(result, str)
        assert result.strip() != ""
        assert patch_groq.last_call is None  # LLM was never invoked

    def test_whitespace_only_outfit_returns_error_string(self, patch_groq):
        result = create_fit_card("   \n\t  ", SAMPLE_ITEM)
        assert isinstance(result, str)
        assert result.strip() != ""
        assert patch_groq.last_call is None

    def test_valid_outfit_returns_caption(self, patch_groq):
        patch_groq.reply = "Thrifted gem alert! This vintage band tee is everything."
        result = create_fit_card("Band tee with black jeans and boots.", SAMPLE_ITEM)
        assert isinstance(result, str)
        assert result.strip() != ""
        assert patch_groq.last_call is not None  # LLM was invoked this time

    def test_valid_outfit_prompt_includes_item_and_outfit(self, patch_groq):
        outfit = "Band tee tucked into wide-leg trousers."
        create_fit_card(outfit, SAMPLE_ITEM)
        assert SAMPLE_ITEM["title"] in patch_groq.last_prompt
        assert outfit in patch_groq.last_prompt

    def test_caption_uses_high_temperature_for_variety(self, patch_groq):
        # The spec asks for higher temperature so captions vary.
        create_fit_card("A solid everyday fit.", SAMPLE_ITEM)
        assert patch_groq.last_call["temperature"] >= 0.7
