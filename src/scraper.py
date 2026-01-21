import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
from typing import Optional


def scrape_website(domain: str, timeout: int = 15) -> dict:
    """
    Scrape key information from a company's website.

    Returns a dict with:
    - title: Page title
    - meta_description: Meta description
    - headlines: List of h1/h2 headlines
    - cta_buttons: Call-to-action text found (book demo, contact, etc.)
    - pricing_signals: Any pricing-related text found
    - main_content: Extracted main text content (truncated)
    - error: Error message if scraping failed
    """

    url = f"https://{domain}"

    result = {
        "domain": domain,
        "url": url,
        "title": "",
        "meta_description": "",
        "headlines": [],
        "cta_buttons": [],
        "pricing_signals": [],
        "main_content": "",
        "error": None
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
    except requests.exceptions.SSLError:
        # Try HTTP if HTTPS fails
        try:
            url = f"http://{domain}"
            response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
        except Exception as e:
            result["error"] = f"Connection failed: {str(e)}"
            return result
    except requests.exceptions.RequestException as e:
        result["error"] = f"Request failed: {str(e)}"
        return result

    try:
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        # Title
        title_tag = soup.find("title")
        if title_tag:
            result["title"] = title_tag.get_text(strip=True)

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            result["meta_description"] = meta_desc.get("content", "")

        # OG description as fallback
        if not result["meta_description"]:
            og_desc = soup.find("meta", attrs={"property": "og:description"})
            if og_desc:
                result["meta_description"] = og_desc.get("content", "")

        # Headlines (h1 and h2)
        headlines = []
        for tag in soup.find_all(["h1", "h2"]):
            text = tag.get_text(strip=True)
            if text and len(text) > 3 and len(text) < 200:
                headlines.append(text)
        result["headlines"] = headlines[:10]  # Limit to 10

        # CTA buttons - look for demo/sales/contact CTAs
        cta_patterns = [
            r"book.{0,5}(demo|call|meeting)",
            r"schedule.{0,5}(demo|call|meeting)",
            r"get.{0,5}(demo|started|quote|pricing)",
            r"request.{0,5}(demo|quote|pricing)",
            r"contact.{0,5}(sales|us)",
            r"talk.{0,5}(sales|expert|us)",
            r"free.{0,5}(trial|consultation)",
            r"start.{0,5}(free|trial)",
        ]

        cta_buttons = set()
        for link in soup.find_all(["a", "button"]):
            text = link.get_text(strip=True).lower()
            for pattern in cta_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    cta_buttons.add(link.get_text(strip=True))
                    break
        result["cta_buttons"] = list(cta_buttons)[:5]

        # Pricing signals
        pricing_patterns = [
            r"\$[\d,]+(?:\.\d{2})?(?:\s*[/-]\s*(?:mo|month|year|yr))?",
            r"[\d,]+\s*(?:per|/)\s*(?:month|mo|year|yr)",
            r"starting\s+(?:at|from)\s+\$?[\d,]+",
            r"pricing|plans|packages",
            r"enterprise.{0,10}(?:plan|pricing|contact)",
            r"custom.{0,10}(?:plan|pricing|quote)",
        ]

        page_text = soup.get_text()
        pricing_signals = set()
        for pattern in pricing_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for match in matches[:3]:
                if isinstance(match, str) and len(match) < 50:
                    pricing_signals.add(match.strip())
        result["pricing_signals"] = list(pricing_signals)[:5]

        # Main content - get text from main/article or body
        main_content = ""
        main_elem = soup.find("main") or soup.find("article") or soup.find("body")
        if main_elem:
            main_content = main_elem.get_text(separator=" ", strip=True)
            # Clean up whitespace
            main_content = re.sub(r'\s+', ' ', main_content)
            # Truncate to ~2000 chars
            main_content = main_content[:2000]

        result["main_content"] = main_content

    except Exception as e:
        result["error"] = f"Parse error: {str(e)}"

    return result


def format_scraped_data(data: dict) -> str:
    """Format scraped data into a string for the LLM prompt."""

    if data.get("error"):
        return f"[Website scraping failed: {data['error']}. Analyze based on domain name only.]"

    parts = []

    if data.get("title"):
        parts.append(f"Title: {data['title']}")

    if data.get("meta_description"):
        parts.append(f"Description: {data['meta_description']}")

    if data.get("headlines"):
        parts.append(f"Headlines: {'; '.join(data['headlines'][:5])}")

    if data.get("cta_buttons"):
        parts.append(f"CTAs found: {', '.join(data['cta_buttons'])}")

    if data.get("pricing_signals"):
        parts.append(f"Pricing signals: {', '.join(data['pricing_signals'])}")

    if data.get("main_content"):
        # Truncate main content for prompt
        content = data["main_content"][:1000]
        parts.append(f"Page content: {content}...")

    if not parts:
        return "[No content could be extracted from website]"

    return "\n".join(parts)
