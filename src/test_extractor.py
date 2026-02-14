from typing import List, Dict
import sys
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

repo_root = Path(__file__).resolve().parents[1]
src_root = repo_root / "src"
if str(src_root) not in sys.path:
    sys.path.insert(0, str(src_root))

from extractor import Extractor


@pytest.fixture
def extractor() -> Extractor:
    """Fixture to create a fresh Extractor instance for each test."""
    return Extractor("https://www.olx.bg/dummy/")


SAMPLE_AD_WITH_PRICE = '''
<div class="css-1sw7q4x">
    <p data-testid="ad-price">15 900 лв.</p>
    <h6 class="css-abc123">Volkswagen Golf 1.9 TDI
        Excellent Condition
        2008</h6>
    <p>Преглеждания: 349;</p>
    <a href="/d/ad/volkswagen-golf-CID360-IDabc123.html"></a>
</div>
'''

SAMPLE_AD_NO_PRICE = '''
<div class="css-1sw7q4x">
    <h6 class="css-def456">BMW 320d No Price Listed</h6>
    <a href="/d/ad/bmw-320d-CID360-IDdef456.html"></a>
</div>
'''

SAMPLE_AD_WITH_NEWLINES = '''
<div class="css-1sw7q4x">
    <p data-testid="ad-price">10 500 лв.</p>
    <h6 class="css-xyz789">Audi A4



        2.0 TFSI   Quattro

        Full Extras</h6>
    <a href="/d/ad/audi-a4-CID360-IDxyz789.html"></a>
</div>
'''

SAMPLE_AD_BAD_LINK = '''
<div class="css-1sw7q4x">
    <p data-testid="ad-price">8 000 лв.</p>
    <h6 class="css-123">Mercedes Old Model</h6>
    <a href="https://external-site.com">Wrong link</a>
</div>
'''


def test_get_price_present(extractor: Extractor) -> None:
    soup = BeautifulSoup(SAMPLE_AD_WITH_PRICE, "html.parser")
    assert extractor.get_price(soup) == "15 900 лв."


def test_get_price_missing(extractor: Extractor) -> None:
    soup = BeautifulSoup(SAMPLE_AD_NO_PRICE, "html.parser")
    assert extractor.get_price(soup) == "N/A"


def test_get_product_basic(extractor: Extractor) -> None:
    soup = BeautifulSoup(SAMPLE_AD_WITH_PRICE, "html.parser")
    assert extractor.get_product(soup) == "Volkswagen Golf 1.9 TDI Excellent Condition 2008"


def test_get_product_newlines_cleaned(extractor: Extractor) -> None:
    soup = BeautifulSoup(SAMPLE_AD_WITH_NEWLINES, "html.parser")
    expected = "Audi A4 2.0 TFSI Quattro Full Extras"
    assert extractor.get_product(soup) == expected


def test_get_product_missing(extractor: Extractor) -> None:
    html = '<div class="css-1sw7q4x"><p data-testid="ad-price">10 000 лв.</p></div>'
    soup = BeautifulSoup(html, "html.parser")
    assert extractor.get_product(soup) == "N/A"


def test_get_model_from_title(extractor: Extractor) -> None:
    soup = BeautifulSoup(SAMPLE_AD_WITH_PRICE, "html.parser")
    assert extractor.get_model(soup) == "Volkswagen Golf"


def test_get_model_missing(extractor: Extractor) -> None:
    html = '<div class="css-1sw7q4x"><p data-testid="ad-price">10 000 лв.</p></div>'
    soup = BeautifulSoup(html, "html.parser")
    assert extractor.get_model(soup) == "N/A"


def test_get_views_present(extractor: Extractor) -> None:
    soup = BeautifulSoup(SAMPLE_AD_WITH_PRICE, "html.parser")
    assert extractor.get_views(soup) == "349"


def test_get_views_missing(extractor: Extractor) -> None:
    soup = BeautifulSoup(SAMPLE_AD_NO_PRICE, "html.parser")
    assert extractor.get_views(soup) == "N/A"


def test_get_views_split_nodes(extractor: Extractor) -> None:
    html = '''
    <div class="css-1sw7q4x">
        <span>Преглеждания:</span><span> 3 490 </span>
    </div>
    '''
    soup = BeautifulSoup(html, "html.parser")
    assert extractor.get_views(soup) == "3490"


def test_get_views_from_css_selector(extractor: Extractor) -> None:
    html = '''
    <div class="css-1sw7q4x">
        <div class="css-13x8d99">Преглеждания: 777</div>
    </div>
    '''
    soup = BeautifulSoup(html, "html.parser")
    assert extractor.get_views(soup) == "777"


def test_get_views_from_script_data(extractor: Extractor) -> None:
    html = '''
    <html><body>
        <script type="application/ld+json">
            {"viewsCounter": 456}
        </script>
    </body></html>
    '''
    soup = BeautifulSoup(html, "html.parser")
    assert extractor.get_views(soup) == "456"


def test_get_ad_url_standard(extractor: Extractor) -> None:
    soup = BeautifulSoup(SAMPLE_AD_WITH_PRICE, "html.parser")
    expected = "https://www.olx.bg/d/ad/volkswagen-golf-CID360-IDabc123.html"
    assert extractor.get_ad_url(soup) == expected


def test_get_ad_url_fallback(extractor: Extractor) -> None:
    html = '''
    <div class="css-1sw7q4x">
        <a href="/d/oferta/some-old-pattern-IDfallback.html"></a>
    </div>
    '''
    soup = BeautifulSoup(html, "html.parser")
    expected = "https://www.olx.bg/d/oferta/some-old-pattern-IDfallback.html"
    assert extractor.get_ad_url(soup) == expected


def test_get_ad_url_missing(extractor: Extractor) -> None:
    html = '<div class="css-1sw7q4x"><p data-testid="ad-price">5 000 лв.</p></div>'
    soup = BeautifulSoup(html, "html.parser")
    assert extractor.get_ad_url(soup) == "N/A"


def test_extract_skips_no_price(extractor: Extractor) -> None:
    full_html = f'''
    <html><body>
        {SAMPLE_AD_WITH_PRICE}
        {SAMPLE_AD_NO_PRICE}
    </body></html>
    '''

    extractor.extract_information_from_page(full_html)

    assert len(extractor.data) == 1
    saved = extractor.data[0]
    assert saved["Price"] == "15 900 лв."
    assert "Volkswagen Golf" in saved["Product/Title"]
    assert saved["Model"] == "Volkswagen Golf"
    assert saved["Views"] == "349"
    assert "IDabc123.html" in saved["Ad_URL"]


def test_extract_cleans_title_and_saves_all_fields(extractor: Extractor) -> None:
    full_html = f'''
    <html><body>
        {SAMPLE_AD_WITH_NEWLINES}
    </body></html>
    '''

    extractor.extract_information_from_page(full_html)

    assert len(extractor.data) == 1
    saved = extractor.data[0]
    assert saved["Price"] == "10 500 лв."
    assert saved["Product/Title"] == "Audi A4 2.0 TFSI Quattro Full Extras"
    assert saved["Model"] == "Audi A4"
    assert saved["Views"] == "N/A"
    assert "IDxyz789.html" in saved["Ad_URL"]


def test_save_to_csv_creates_file(extractor: Extractor, tmp_path) -> None:
    extractor.data = [{
        "Price": "10 000 лв.",
        "Product/Title": "Test Car",
        "Model": "Test Car",
        "Views": "123",
        "Ad_URL": "https://www.olx.bg/d/ad/test-ID123.html",
        "Source_URL": "https://dummy",
        "Extracted_At": "2026-01-29 12:00:00"
    }]

    test_filename = tmp_path / "test_output.csv"
    extractor.save_to_csv(filename=str(test_filename))

    assert test_filename.exists()
    content = test_filename.read_text(encoding="utf-8")
    assert "10 000 лв." in content
    assert "Test Car" in content


def test_get_ad_url_ignores_external_domain(extractor: Extractor) -> None:
    html = '''
    <div class="css-1sw7q4x">
        <a href="https://external-site.com/d/ad/foo-ID123.html"></a>
        <a href="/d/ad/local-ID999.html"></a>
    </div>
    '''
    soup = BeautifulSoup(html, "html.parser")
    expected = "https://www.olx.bg/d/ad/local-ID999.html"
    assert extractor.get_ad_url(soup) == expected


def test_save_to_csv_with_no_data(extractor: Extractor, tmp_path) -> None:
    extractor.data = []
    test_filename = tmp_path / "empty.csv"
    extractor.save_to_csv(filename=str(test_filename))
    assert test_filename.exists()
    content = test_filename.read_text(encoding="utf-8")
    assert "Price" in content


def test_normalize_relative_href(extractor: Extractor) -> None:
    html = '''
    <div class="css-1sw7q4x">
        <a href="d/ad/local-ID777.html"></a>
    </div>
    '''
    soup = BeautifulSoup(html, "html.parser")
    expected = "https://www.olx.bg/d/ad/local-ID777.html"
    assert extractor.get_ad_url(soup) == expected


def test_extract_includes_na_ad_url(extractor: Extractor) -> None:
    html = '''
    <html><body>
        <div class="css-1sw7q4x">
            <p data-testid="ad-price">5 500 лв.</p>
            <h6>Test Title</h6>
        </div>
    </body></html>
    '''
    extractor.extract_information_from_page(html)
    assert len(extractor.data) == 1
    assert extractor.data[0]["Ad_URL"] == "N/A"
