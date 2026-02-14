import csv
import datetime
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup


class Extractor:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        parsed = urlparse(base_url)
        self.base_domain = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
        self.data: List[Dict[str, str]] = []

    def _clean_text(self, text: str) -> str:
        return " ".join(text.split())

    def get_price(self, ad_soup: BeautifulSoup) -> str:
        price = ad_soup.select_one('p[data-testid="ad-price"]')
        if not price:
            return "N/A"
        return self._clean_text(price.get_text(separator=" ", strip=True))

    def get_product(self, ad_soup: BeautifulSoup) -> str:
        title = ad_soup.find("h6")
        if not title:
            return "N/A"
        return self._clean_text(title.get_text(separator=" ", strip=True))

    def get_model(self, ad_soup: BeautifulSoup) -> str:
        model_label = ad_soup.find(string=re.compile(r"\bМодел\b", re.IGNORECASE))
        if model_label:
            text = self._clean_text(str(model_label))
            match = re.search(r"Модел\s*:\s*([^;|,]+)", text, flags=re.IGNORECASE)
            if match:
                return self._clean_text(match.group(1))

        title = self.get_product(ad_soup)
        if title == "N/A":
            return "N/A"

        tokens = title.split()
        if len(tokens) >= 2:
            return f"{tokens[0]} {tokens[1]}"
        return tokens[0]

    def get_views(self, ad_soup: BeautifulSoup) -> str:
        # Try common DOM locations first (including the user-provided class).
        selectors = [
            ".css-13x8d99",
            '[data-cy="ad-view-counter"]',
            '[data-testid="ad-view-counter"]',
        ]
        for selector in selectors:
            el = ad_soup.select_one(selector)
            if not el:
                continue
            candidate = self._clean_text(el.get_text(separator=" ", strip=True))
            match = re.search(r"(\d[\d\s]*)", candidate)
            if match:
                return re.sub(r"\s+", "", match.group(1))

        # OLX may render label/value in separate nodes, e.g. "Преглеждания:" then "349".
        text = self._clean_text(ad_soup.get_text(separator=" ", strip=True))
        label_match = re.search(r"Преглеждания\s*:\s*([\d\s]+)", text, flags=re.IGNORECASE)
        if label_match:
            return re.sub(r"\s+", "", label_match.group(1))

        # Fallback for script-embedded data on pages where this value is not in visible DOM.
        script_text = " ".join(script.get_text(" ", strip=True) for script in ad_soup.find_all("script"))
        script_match = re.search(r'"(?:views|viewCount|viewsCount|viewsCounter)"\s*:\s*(\d+)', script_text, flags=re.IGNORECASE)
        if script_match:
            return script_match.group(1)

        return "N/A"

    def _normalize_href(self, href: str) -> str:
        if href.startswith("/") and self.base_domain:
            return f"{self.base_domain}{href}"
        if href.startswith("http://") or href.startswith("https://"):
            return href
        if self.base_domain:
            return f"{self.base_domain}/{href.lstrip('/')}"
        return href

    def get_ad_url(self, ad_soup: BeautifulSoup) -> str:
        links = ad_soup.find_all("a", href=True)
        pattern_primary = re.compile(r"/d/ad/.+-ID.+\.html", re.IGNORECASE)
        pattern_fallback = re.compile(r"/d/oferta/.+-ID.+\.html", re.IGNORECASE)

        for link in links:
            href = link.get("href", "")
            if not href:
                continue
            test_href = href
            if not href.startswith("http"):
                test_href = "/" + href.lstrip("/")
            if pattern_primary.search(test_href) or pattern_fallback.search(test_href):
                full_url = self._normalize_href(href)
                if self.base_domain and self.base_domain not in full_url:
                    continue
                return full_url
        return "N/A"

    def extract_information_from_page(self, html: str) -> None:
        soup = BeautifulSoup(html, "html.parser")
        ads = soup.select("div.css-1sw7q4x")
        for ad in ads:
            price = self.get_price(ad)
            if price == "N/A":
                continue
            title = self.get_product(ad)
            model = self.get_model(ad)
            views = self.get_views(ad)
            ad_url = self.get_ad_url(ad)
            record = {
                "Price": price,
                "Product/Title": title,
                "Model": model,
                "Views": views,
                "Ad_URL": ad_url,
                "Source_URL": self.base_url,
                "Extracted_At": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            self.data.append(record)

    def save_to_csv(self, filename: str) -> None:
        if not self.data:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Price", "Product/Title", "Model", "Views", "Ad_URL", "Source_URL", "Extracted_At"])
            return

        fieldnames = ["Price", "Product/Title", "Model", "Views", "Ad_URL", "Source_URL", "Extracted_At"]
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in self.data:
                writer.writerow(row)
