import pytest
import re
from bs4 import BeautifulSoup
from extractor import Extractor  # Assuming your class is saved in extractor.py


@pytest.fixture
def extractor():
    """Fixture to create a fresh Extractor instance for each test."""
    return Extractor("https://www.olx.bg/dummy/")


# Sample HTML snippets that match the current selectors in your code
SAMPLE_AD_WITH_PRICE = '''
<div class="css-1sw7q4x">
    <p data-testid="ad-price">15 900 лв.</p>
    <h6 class="css-abc123">Volkswagen Golf 1.9 TDI
        Excellent Condition
        2008</h6>
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


def test_get_price_present(extractor):
    soup = BeautifulSoup(SAMPLE_AD_WITH_PRICE, "html.parser")
    assert extractor.get_price(soup) == "15 900 лв."


def test_get_price_missing(extractor):
    soup = BeautifulSoup(SAMPLE_AD_NO_PRICE, "html.parser")
    assert extractor.get_price(soup) == "N/A"


def test_get_product_basic(extractor):
    soup = BeautifulSoup(SAMPLE_AD_WITH_PRICE, "html.parser")
    assert extractor.get_product(soup) == "Volkswagen Golf 1.9 TDI Excellent Condition 2008"


def test_get_product_newlines_cleaned(extractor):
    soup = BeautifulSoup(SAMPLE_AD_WITH_NEWLINES, "html.parser")
    expected = "Audi A4 2.0 TFSI Quattro Full Extras"
    assert extractor.get_product(soup) == expected


def test_get_product_missing(extractor):
    html = '<div class="css-1sw7q4x"><p data-testid="ad-price">10 000 лв.</p></div>'
    soup = BeautifulSoup(html, "html.parser")
    assert extractor.get_product(soup) == "N/A"


def test_get_ad_url_standard(extractor):
    soup = BeautifulSoup(SAMPLE_AD_WITH_PRICE, "html.parser")
    expected = "https://www.olx.bg/d/ad/volkswagen-golf-CID360-IDabc123.html"
    assert extractor.get_ad_url(soup) == expected


def test_get_ad_url_fallback(extractor):
    # Simulate a case where primary regex misses but fallback works
    html = '''
    <div class="css-1sw7q4x">
        <a href="/d/oferta/some-old-pattern-IDfallback.html"></a>
    </div>
    '''
    soup = BeautifulSoup(html, "html.parser")
    expected = "https://www.olx.bg/d/oferta/some-old-pattern-IDfallback.html"
    assert extractor.get_ad_url(soup) == expected


def test_get_ad_url_missing(extractor):
    html = '<div class="css-1sw7q4x"><p data-testid="ad-price">5 000 лв.</p></div>'
    soup = BeautifulSoup(html, "html.parser")
    assert extractor.get_ad_url(soup) == "N/A"


def test_extract_skips_no_price(extractor):
    # Full page with two ads: one with price, one without
    full_html = f'''
    <html><body>
        {SAMPLE_AD_WITH_PRICE}
        {SAMPLE_AD_NO_PRICE}
    </body></html>
    '''

    extractor.extract_information_from_page(full_html)

    assert len(extractor.data) == 1  # Only the one with price is saved
    saved = extractor.data[0]
    assert saved["Price"] == "15 900 лв."
    assert "Volkswagen Golf" in saved["Product/Title"]
    assert "IDabc123.html" in saved["Ad_URL"]


def test_extract_cleans_title_and_saves_all_fields(extractor):
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
    assert "IDxyz789.html" in saved["Ad_URL"]


def test_save_to_csv_creates_file(extractor, tmp_path):
    # tmp_path is a pytest fixture for temporary directory
    extractor.data = [{
        "Price": "10 000 лв.",
        "Product/Title": "Test Car",
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