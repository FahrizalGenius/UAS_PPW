"""HTTP Fetcher with SSRF protection, content-type filtering, and redirect handling."""
import socket
import ipaddress
import logging
from dataclasses import dataclass
from typing import Optional, Tuple
from urllib.parse import urlsplit
import requests
from app.crawler.url_normalizer import normalize_url, is_valid_http_url

logger = logging.getLogger(__name__)

# Default limits
DEFAULT_TIMEOUT = 10
MAX_RESPONSE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_REDIRECTS = 5
DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; PPW-PageRankBot/1.0; +https://trunojoyo.ac.id/)"

@dataclass
class FetchResult:
    success: bool
    url: str
    final_url: str
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    html: Optional[str] = None
    error_message: Optional[str] = None

class SSRFSecurityError(Exception):
    """Raised when a URL resolves to a prohibited internal or private IP address."""
    pass

def is_ip_allowed(ip_str: str) -> bool:
    """
    Check if an IP address string is safe to connect to (public and routable).
    Rejects private, loopback, link-local, multicast, reserved, and unspecified addresses.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        if (
            ip.is_private or
            ip.is_loopback or
            ip.is_link_local or
            ip.is_multicast or
            ip.is_reserved or
            ip.is_unspecified
        ):
            return False
        # Specific cloud metadata address protection (AWS, GCP, Azure, DigitalOcean)
        if str(ip) in {"169.254.169.254", "fd00:ec2::254"}:
            return False
        return True
    except ValueError:
        return False

def validate_url_security(url: str) -> Tuple[bool, str]:
    """
    Perform SSRF checks on a URL by resolving its hostname via DNS.
    Returns:
        (is_safe, error_or_first_ip)
    """
    if not is_valid_http_url(url):
        return False, "Bukan skema HTTP/HTTPS yang valid."

    parsed = urlsplit(url)
    hostname = parsed.hostname
    if not hostname:
        return False, "Hostname tidak ditemukan."

    # Direct block for localhost / local domains
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".local") or hostname.endswith(".internal"):
        return False, f"Akses ke hostname lokal/internal ({hostname}) ditolak (SSRF protection)."

    # Resolve hostname to IP addresses
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addr_info = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        if not addr_info:
            return False, f"DNS resolution gagal untuk hostname {hostname}."

        for family, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            if not is_ip_allowed(ip_str):
                return False, f"Hostname {hostname} merujuk ke IP privat/terlarang ({ip_str}) - SSRF ditolak."
        
        return True, addr_info[0][4][0]
    except socket.gaierror as e:
        return False, f"Gagal resolusi DNS untuk {hostname}: {str(e)}"
    except Exception as e:
        return False, f"Kesalahan validasi keamanan URL: {str(e)}"

class WebFetcher:
    """HTTP Fetcher designed specifically for the PPW-PageRank web crawler."""

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: int = DEFAULT_TIMEOUT,
        max_size: int = MAX_RESPONSE_SIZE,
        max_redirects: int = MAX_REDIRECTS
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_size = max_size
        self.max_redirects = max_redirects
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "id,en-US;q=0.9,en;q=0.8",
        })

    def fetch(self, url: str) -> FetchResult:
        """
        Fetch a single web page with SSRF protection, size caps, and manual redirect validation.
        """
        current_url = url
        redirect_count = 0

        while redirect_count <= self.max_redirects:
            # 1. SSRF Validation
            is_safe, sec_info = validate_url_security(current_url)
            if not is_safe:
                return FetchResult(
                    success=False,
                    url=url,
                    final_url=current_url,
                    error_message=f"SSRF Protection: {sec_info}"
                )

            # 2. Make Request with stream=True to inspect headers before downloading body
            try:
                response = self.session.get(
                    current_url,
                    timeout=self.timeout,
                    allow_redirects=False,
                    stream=True,
                    verify=True
                )
            except requests.exceptions.SSLError as ssl_err:
                return FetchResult(
                    success=False,
                    url=url,
                    final_url=current_url,
                    error_message=f"SSL Error: {str(ssl_err)}"
                )
            except requests.exceptions.Timeout:
                return FetchResult(
                    success=False,
                    url=url,
                    final_url=current_url,
                    error_message=f"Request timeout setelah {self.timeout} detik"
                )
            except requests.exceptions.ConnectionError as conn_err:
                return FetchResult(
                    success=False,
                    url=url,
                    final_url=current_url,
                    error_message=f"Koneksi gagal: {str(conn_err)}"
                )
            except Exception as exc:
                return FetchResult(
                    success=False,
                    url=url,
                    final_url=current_url,
                    error_message=f"Request error: {str(exc)}"
                )

            status_code = response.status_code
            content_type = response.headers.get("Content-Type", "").lower()

            # 3. Handle Redirects (301, 302, 303, 307, 308)
            if status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("Location")
                if not location:
                    response.close()
                    return FetchResult(
                        success=False,
                        url=url,
                        final_url=current_url,
                        status_code=status_code,
                        error_message="Redirect header Location kosong."
                    )
                
                # Normalize target redirect URL using current URL as base
                next_url = normalize_url(location, base_url=current_url)
                response.close()

                if not next_url:
                    return FetchResult(
                        success=False,
                        url=url,
                        final_url=current_url,
                        status_code=status_code,
                        error_message=f"Redirect ke URL tidak valid: {location}"
                    )

                current_url = next_url
                redirect_count += 1
                continue

            # 4. Check Status Code
            if status_code != 200:
                response.close()
                return FetchResult(
                    success=False,
                    url=url,
                    final_url=current_url,
                    status_code=status_code,
                    content_type=content_type,
                    error_message=f"HTTP Status Code {status_code}"
                )

            # 5. Check Content-Type: Only accept HTML
            if "text/html" not in content_type:
                response.close()
                return FetchResult(
                    success=False,
                    url=url,
                    final_url=current_url,
                    status_code=status_code,
                    content_type=content_type,
                    error_message=f"Tipe konten bukan HTML ({content_type})"
                )

            # 6. Stream content safely up to MAX_RESPONSE_SIZE
            try:
                chunks = []
                total_bytes = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        total_bytes += len(chunk)
                        if total_bytes > self.max_size:
                            response.close()
                            return FetchResult(
                                success=False,
                                url=url,
                                final_url=current_url,
                                status_code=status_code,
                                content_type=content_type,
                                error_message=f"Ukuran respons melebihi batas maksimal ({self.max_size} bytes)"
                            )
                        chunks.append(chunk)

                # Decode HTML with fallback
                raw_bytes = b"".join(chunks)
                encoding = response.encoding or "utf-8"
                try:
                    html_text = raw_bytes.decode(encoding, errors="replace")
                except Exception:
                    html_text = raw_bytes.decode("utf-8", errors="replace")

                response.close()
                return FetchResult(
                    success=True,
                    url=url,
                    final_url=current_url,
                    status_code=status_code,
                    content_type=content_type,
                    html=html_text
                )
            except Exception as stream_err:
                response.close()
                return FetchResult(
                    success=False,
                    url=url,
                    final_url=current_url,
                    status_code=status_code,
                    error_message=f"Gagal membaca konten stream: {str(stream_err)}"
                )

        return FetchResult(
            success=False,
            url=url,
            final_url=current_url,
            error_message=f"Terlalu banyak redirect (melebihi {self.max_redirects})"
        )
