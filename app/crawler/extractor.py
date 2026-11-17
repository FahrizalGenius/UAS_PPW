"""HTML link and metadata extractor using BeautifulSoup4."""
import re
from dataclasses import dataclass
from typing import List, Set
from bs4 import BeautifulSoup
from app.crawler.url_normalizer import normalize_url, get_url_hash, extract_domain

@dataclass
class ExtractedLink:
    target_url: str
    target_url_hash: str
    anchor_text: str
    target_domain: str

@dataclass
class ExtractedData:
    title: str
    links: List[ExtractedLink]

class HTMLExtractor:
    """Extracts page title and outbound hyperlinks from raw HTML."""

    @staticmethod
    def extract(html: str, base_url: str) -> ExtractedData:
        """
        Parse HTML and extract title and normalized outbound hyperlinks.
        
        Args:
            html: Raw HTML string.
            base_url: The final URL of the fetched page (for resolving relative paths).
            
        Returns:
            ExtractedData containing page title and unique list of ExtractedLink.
        """
        if not html:
            return ExtractedData(title="", links=[])

        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            return ExtractedData(title="", links=[])

        # 1. Extract Page Title
        title = ""
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            title = title_tag.get_text(strip=True)
        elif soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)

        # Clean title whitespace
        title = re.sub(r"\s+", " ", title).strip()

        # 2. Extract and Normalize Hyperlinks
        seen_targets: Set[str] = set()
        extracted_links: List[ExtractedLink] = []

        for a_tag in soup.find_all("a", href=True):
            raw_href = a_tag["href"]
            if not raw_href or not isinstance(raw_href, str):
                continue

            cleaned_href = raw_href.strip()
            # Ignore empty links, in-page fragment anchors, and non-web protocols
            if not cleaned_href or cleaned_href.startswith(("#", "javascript:", "mailto:", "tel:", "data:", "sms:", "whatsapp:")):
                continue

            normalized_target = normalize_url(cleaned_href, base_url=base_url)
            if not normalized_target:
                continue

            # Compute hash for target URL
            target_hash = get_url_hash(normalized_target)

            # Avoid adding duplicate edges from the exact same source page
            if target_hash in seen_targets:
                continue
            seen_targets.add(target_hash)

            # Extract anchor text
            anchor_text = a_tag.get_text(separator=" ", strip=True)
            anchor_text = re.sub(r"\s+", " ", anchor_text).strip()
            if len(anchor_text) > 500:
                anchor_text = anchor_text[:497] + "..."

            target_domain = extract_domain(normalized_target)

            extracted_links.append(
                ExtractedLink(
                    target_url=normalized_target,
                    target_url_hash=target_hash,
                    anchor_text=anchor_text or None,
                    target_domain=target_domain
                )
            )

        return ExtractedData(title=title, links=extracted_links)
