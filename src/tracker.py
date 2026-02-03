import aiohttp
import asyncio
import datetime
import json
import csv
from bs4 import BeautifulSoup


class ClassTracker:
    def __init__(self):
        self.tracked = {}  # dict[str, set[str]]

    def add(self, url: str, selector: str):
        if url not in self.tracked:
            self.tracked[url] = {selector}
            return 1
        if selector in self.tracked[url]:
            return 0
        self.tracked[url].add(selector)
        return 2

    def remove_url(self, url: str):
        return self.tracked.pop(url, None) is not None

    def remove_selector(self, url: str, selector: str):
        if url in self.tracked and selector in self.tracked[url]:
            self.tracked[url].remove(selector)
            if not self.tracked[url]:
                del self.tracked[url]
            return True
        return False

    def extract_from_html(self, url: str, html: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        result = {}
        for selector in self.tracked[url]:
            elements = soup.select(selector)
            print(elements)
            result[selector] = [el.get_text(separator=" ", strip=True) for el in elements]
        return result

    async def fetch(self, session: aiohttp.ClientSession, url: str, timeout: int = 10) -> str:
        try:
            async with session.get(url, timeout=timeout) as response:
                response.raise_for_status()
                return await response.text()
        except Exception:
            return None

    async def extract_all_async(self, timeout: int = 10) -> dict:
        all_data = {}
        if not self.tracked:
            return all_data

        timestamp = datetime.datetime.now().isoformat()

        async with aiohttp.ClientSession() as session:
            fetch_coroutines = [self.fetch(session, url, timeout) for url in self.tracked]
            html_pages = await asyncio.gather(*fetch_coroutines)

            for url, html in zip(self.tracked.keys(), html_pages):
                if html is not None:
                    all_data[url] = self.extract_from_html(url, html)
                else:
                    all_data[url] = None

        return all_data

    def save_fetched_html(self, url: str, html: str, timestamp: str):
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

    def save_to_json(self, data: dict, filename: str):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def load_from_json(self, filename: str) -> dict:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_to_csv(self, data: dict, filename: str):
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "url", "selector", "text"])
            for timestamp, urls in data.items():
                for url, selectors in urls.items():
                    if selectors:
                        for selector, texts in selectors.items():
                            for text in texts:
                                writer.writerow([timestamp, url, selector, text])