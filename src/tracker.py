import aiohttp
import asyncio
import datetime
import json
import csv
from typing import Dict, List, Optional, Set, Tuple
from bs4 import BeautifulSoup


class ClassTracker:
    def __init__(self) -> None:
        self.tracked: Dict[str, Set[str]] = {}
        self.last_errors: Dict[str, str] = {}

    def add(self, url: str, selector: str) -> int:
        if url not in self.tracked:
            self.tracked[url] = {selector}
            return 1
        if selector in self.tracked[url]:
            return 0
        self.tracked[url].add(selector)
        return 2

    def remove_url(self, url: str) -> bool:
        return self.tracked.pop(url, None) is not None

    def remove_selector(self, url: str, selector: str) -> bool:
        if url in self.tracked and selector in self.tracked[url]:
            self.tracked[url].remove(selector)
            if not self.tracked[url]:
                del self.tracked[url]
            return True
        return False

    def extract_from_html(self, url: str, html: str) -> Dict[str, List[str]]:
        soup = BeautifulSoup(html, "lxml")
        result: Dict[str, List[str]] = {}
        for selector in self.tracked[url]:
            elements = soup.select(selector)
            result[selector] = [el.get_text(separator=" ", strip=True) for el in elements]
        return result

    # asynchronously downloads url and check for an http error
    # returns [html_string, None] or [None, Exception message]
    async def fetch(self, session: aiohttp.ClientSession, url: str, timeout: int = 10) -> Tuple[Optional[str], Optional[str]]:
        try:
            async with session.get(url, timeout=timeout) as response:
                response.raise_for_status()
                return await response.text(), None
        except Exception as exc:
            return None, f"{type(exc).__name__}: {exc}"

    async def extract_all_async(self, timeout: int = 10) -> Dict[str, Optional[Dict[str, List[str]]]]:
        all_data: Dict[str, Optional[Dict[str, List[str]]]] = {}
        if not self.tracked:
            return all_data

        self.last_errors = {}

        async with aiohttp.ClientSession() as session:
            # fetches all URLs concurrently, so total time is close to the slowest request, not the sum of all request times.
            fetch_coroutines = [self.fetch(session, url, timeout) for url in self.tracked]

            # waits for all of them to finish, then returns their results in order.
            html_pages = await asyncio.gather(*fetch_coroutines)

            for url, (html, error) in zip(self.tracked.keys(), html_pages):
                if error:
                    self.last_errors[url] = error
                if html is not None:
                    all_data[url] = self.extract_from_html(url, html)
                else:
                    all_data[url] = None

        return all_data

    def save_fetched_html(self, url: str, html: str, timestamp: str) -> None:
        import os

        safe_url = url.removeprefix("https://").removeprefix("http://")
        for invalid in r'\/:*?"<>|':
            safe_url = safe_url.replace(invalid, "_")
        safe_url = safe_url[:150]
        if not safe_url:
            safe_url = "unknown_url"

        timestamp_safe = timestamp.replace(":", "_").replace(".", "_")

        filename = f"{safe_url}_{timestamp_safe}.html"
        folder = "saved_htmls"
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, filename)

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"[DEBUG] Saved HTML for {url} at {path}")
        except Exception as e:
            print(f"[ERROR] Failed to save HTML for {url}: {e}")

    def save_to_json(self, data: Dict[str, Dict[str, Optional[Dict[str, List[str]]]]], filename: str) -> None:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def load_from_json(self, filename: str) -> Dict[str, Dict[str, Optional[Dict[str, List[str]]]]]:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_to_csv(self, data: Dict[str, Dict[str, Optional[Dict[str, List[str]]]]], filename: str) -> None:
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "url", "selector", "text"])
            for timestamp, urls in data.items():
                for url, selectors in urls.items():
                    if selectors:
                        for selector, texts in selectors.items():
                            for text in texts:
                                writer.writerow([timestamp, url, selector, text])
