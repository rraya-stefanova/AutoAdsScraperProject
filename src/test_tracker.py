import pytest
import asyncio
import csv
import json
from tracker import ClassTracker


@pytest.fixture
def tracker():
    return ClassTracker()


# --- add() ---

def test_add_new_url(tracker):
    result = tracker.add("https://example.com", ".title")
    assert result == 1
    assert "https://example.com" in tracker.tracked
    assert ".title" in tracker.tracked["https://example.com"]


def test_add_duplicate_selector(tracker):
    tracker.add("https://example.com", ".title")
    result = tracker.add("https://example.com", ".title")
    assert result == 0


def test_add_second_selector(tracker):
    tracker.add("https://example.com", ".title")
    result = tracker.add("https://example.com", ".price")
    assert result == 2
    assert len(tracker.tracked["https://example.com"]) == 2


# --- remove_url() ---

def test_remove_url_exists(tracker):
    tracker.add("https://example.com", ".title")
    assert tracker.remove_url("https://example.com") is True
    assert "https://example.com" not in tracker.tracked


def test_remove_url_missing(tracker):
    assert tracker.remove_url("https://nonexistent.com") is False


# --- remove_selector() ---

def test_remove_selector_exists(tracker):
    tracker.add("https://example.com", ".title")
    tracker.add("https://example.com", ".price")
    assert tracker.remove_selector("https://example.com", ".title") is True
    assert ".title" not in tracker.tracked["https://example.com"]


def test_remove_last_selector_removes_url(tracker):
    tracker.add("https://example.com", ".title")
    tracker.remove_selector("https://example.com", ".title")
    assert "https://example.com" not in tracker.tracked


def test_remove_selector_missing(tracker):
    tracker.add("https://example.com", ".title")
    assert tracker.remove_selector("https://example.com", ".nope") is False


def test_remove_selector_missing_url(tracker):
    assert tracker.remove_selector("https://nope.com", ".title") is False


# --- extract_from_html() ---

SAMPLE_HTML = """
<html><body>
    <h1 class="title">Hello World</h1>
    <p class="price">100 лв.</p>
    <p class="price">200 лв.</p>
</body></html>
"""


def test_extract_single_selector(tracker):
    tracker.add("https://example.com", ".title")
    result = tracker.extract_from_html("https://example.com", SAMPLE_HTML)
    assert result[".title"] == ["Hello World"]


def test_extract_multiple_matches(tracker):
    tracker.add("https://example.com", ".price")
    result = tracker.extract_from_html("https://example.com", SAMPLE_HTML)
    assert result[".price"] == ["100 лв.", "200 лв."]


def test_extract_no_matches(tracker):
    tracker.add("https://example.com", ".nonexistent")
    result = tracker.extract_from_html("https://example.com", SAMPLE_HTML)
    assert result[".nonexistent"] == []


def test_extract_strips_whitespace(tracker):
    html = '<html><body><span class="x">  spaced  out  </span></body></html>'
    tracker.add("https://example.com", ".x")
    result = tracker.extract_from_html("https://example.com", html)
    assert result[".x"] == ["spaced  out"]


# --- extract_all_async() ---

def test_extract_all_async_empty(tracker):
    result = asyncio.run(tracker.extract_all_async())
    assert result == {}


# --- save_to_json() / load_from_json() ---

def test_json_round_trip(tracker, tmp_path):
    data = {"2026-01-01T00:00:00": {"https://example.com": {".title": ["Hello"]}}}
    path = str(tmp_path / "out.json")
    tracker.save_to_json(data, path)
    loaded = tracker.load_from_json(path)
    assert loaded == data


# --- save_to_csv() ---

def test_save_to_csv(tracker, tmp_path):
    data = {
        "2026-01-01T00:00:00": {
            "https://example.com": {
                ".title": ["Hello"],
                ".price": ["100 лв.", "200 лв."],
            }
        }
    }
    path = str(tmp_path / "out.csv")
    tracker.save_to_csv(data, path)

    with open(path, encoding="utf-8") as f:
        reader = list(csv.reader(f))

    assert reader[0] == ["timestamp", "url", "selector", "text"]
    data_rows = reader[1:]
    assert len(data_rows) == 3
    texts = [row[3] for row in data_rows]
    assert "Hello" in texts
    assert "100 лв." in texts
    assert "200 лв." in texts


def test_save_to_csv_skips_none(tracker, tmp_path):
    data = {
        "2026-01-01T00:00:00": {
            "https://example.com": None,
        }
    }
    path = str(tmp_path / "out.csv")
    tracker.save_to_csv(data, path)

    with open(path, encoding="utf-8") as f:
        reader = list(csv.reader(f))

    assert len(reader) == 1  # header only


# --- save_fetched_html() ---

def test_save_fetched_html(tracker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tracker.save_fetched_html("https://example.com/page", "<html></html>", "2026-01-01T00:00:00")
    saved = list(tmp_path.glob("saved_htmls/*.html"))
    assert len(saved) == 1
    assert saved[0].read_text(encoding="utf-8") == "<html></html>"