# OLX.bg Web Element Tracker

A GUI application for tracking and extracting web elements from any website using CSS selectors, with async fetching, periodic extraction, and JSON/CSV export.

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd olx_scraper

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Requirements

- Python 3.10+
- `aiohttp` -- async HTTP requests
- `beautifulsoup4` / `lxml` -- HTML parsing
- `tkinter` -- GUI (included with Python)

## Usage

```bash
cd src
python main.py
```

The GUI has three tabs:

- **Проследявани** -- add URLs and CSS selectors, manage tracked elements, run one-time or periodic extraction
- **Данни** -- view extracted data, save to JSON/CSV, load from JSON
- **Лог** -- activity log

## Project Structure

```
src/
├── main.py          # Entry point -- launches the app
├── tracker.py       # ClassTracker -- async fetching, HTML extraction, data export
├── app.py           # App -- tkinter GUI
└── test_tracker.py  # Pytest suite for ClassTracker
```

### `main.py`

Entry point. Imports and runs the `App`.

### `tracker.py`

Core tracking logic (`ClassTracker` class):

- Manage URL + CSS selector pairs
- Async fetch pages with `aiohttp`
- Extract text from matched elements
- Save/load data as JSON or CSV

### `app.py`

GUI application (`App` class):

- Add/remove tracked URLs and selectors
- Manual and periodic extraction with configurable interval
- View, export, and import collected data

### `test_tracker.py`

Pytest test suite for `ClassTracker`. Covers:

- `add()` -- adding URLs/selectors, duplicate handling
- `remove_url()` / `remove_selector()` -- removal and cleanup of empty entries
- `extract_from_html()` -- CSS selector matching, multiple matches, whitespace stripping
- `extract_all_async()` -- async extraction with no tracked URLs
- `save_to_json()` / `load_from_json()` -- JSON round-trip serialization
- `save_to_csv()` -- CSV export with correct headers and `None` handling
- `save_fetched_html()` -- saving raw HTML to disk

## Testing

```bash
cd src
pytest test_tracker.py -v
```

Requires `pytest` (`pip install pytest`).