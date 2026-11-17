"""URL normalization and SHA-256 hashing utilities for web crawling."""
import hashlib
import re
import posixpath
from urllib.parse import urlsplit, urlunsplit, urljoin, parse_qsl, urlencode

# Schemes accepted by the crawler
ALLOWED_SCHEMES = {"http", "https"}

def is_valid_http_url(url: str) -> bool:
    """Check if the string is a valid HTTP/HTTPS URL."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    try:
        parsed = urlsplit(url)
        return parsed.scheme in ALLOWED_SCHEMES and bool(parsed.netloc)
    except Exception:
        return False

def extract_domain(url: str) -> str:
    """Extract lowercase hostname/domain from a URL."""
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        return hostname.lower() if hostname else ""
    except Exception:
        return ""

def normalize_url(url: str, base_url: str = None) -> str:
    """
    Normalize a URL according to RFC 3986 standards.
    
    Args:
        url: The candidate URL string (may be relative or absolute).
        base_url: The source page URL for resolving relative links.
        
    Returns:
        The normalized absolute URL string, or None if invalid or unsupported scheme.
    """
    if not url or not isinstance(url, str):
        return None

    cleaned_url = url.strip()
    # Reject common non-http schemes and empty links immediately
    if cleaned_url.startswith(("mailto:", "javascript:", "tel:", "data:", "sms:", "whatsapp:")):
        return None

    # Resolve relative URL against base_url
    if base_url:
        try:
            cleaned_url = urljoin(base_url, cleaned_url)
        except Exception:
            return None

    try:
        parsed = urlsplit(cleaned_url)
    except Exception:
        return None

    # Only process HTTP and HTTPS schemes
    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        return None

    # Validate and normalize netloc (host and port)
    hostname = parsed.hostname
    if not hostname:
        return None
    hostname = hostname.lower()

    # Drop default ports
    port = parsed.port
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None

    if port:
        netloc = f"{hostname}:{port}"
    else:
        netloc = hostname

    # Normalize path
    raw_path = parsed.path or "/"
    # Collapse duplicate slashes
    raw_path = re.sub(r"/+", "/", raw_path)
    
    # Resolve dot segments (/../ and /./)
    ends_with_slash = raw_path.endswith("/")
    norm_path = posixpath.normpath(raw_path)
    if norm_path != "/" and ends_with_slash and not norm_path.endswith("/"):
        norm_path += "/"
    elif not norm_path.startswith("/"):
        norm_path = "/" + norm_path

    # Canonicalize query parameters (sort alphabetically to avoid duplicate URLs)
    query_string = ""
    if parsed.query:
        query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
        # Sort by key, then value
        sorted_pairs = sorted(query_pairs, key=lambda x: (x[0], x[1]))
        query_string = urlencode(sorted_pairs)

    # Reconstruct URL without fragment
    normalized = urlunsplit((scheme, netloc, norm_path, query_string, ""))
    return normalized

def get_url_hash(url: str) -> str:
    """
    Compute the SHA-256 hash of a normalized URL.
    Returns a 64-character lowercase hex string.
    """
    if not url:
        return ""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()
