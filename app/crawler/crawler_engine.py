"""BFS Web Crawler Engine with MySQL persistence, politeness delay, and robots.txt checking."""
import time
import logging
from datetime import datetime
from collections import deque
from typing import Set, Dict, Optional
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from app.extensions import db
from app.models import CrawlSession, Page, Link, CrawlLog
from app.crawler.url_normalizer import normalize_url, get_url_hash, extract_domain
from app.crawler.fetcher import WebFetcher, FetchResult, validate_url_security
from app.crawler.extractor import HTMLExtractor

logger = logging.getLogger(__name__)

class RobotsChecker:
    """Fetches and caches robots.txt rules for encountered domains."""

    def __init__(self, user_agent: str, timeout: int = 5):
        self.user_agent = user_agent
        self.timeout = timeout
        self.cache: Dict[str, Optional[RobotFileParser]] = {}

    def can_fetch(self, url: str) -> bool:
        """Check whether the User-Agent is allowed to crawl the given URL according to robots.txt."""
        try:
            parsed = urlsplit(url)
            domain = parsed.hostname.lower() if parsed.hostname else ""
            if not domain:
                return False

            base_netloc = f"{parsed.scheme}://{parsed.netloc}"
            if base_netloc not in self.cache:
                robots_url = f"{base_netloc}/robots.txt"
                is_safe, _ = validate_url_security(robots_url)
                if not is_safe:
                    # If robots.txt URL resolves to private IP, reject crawling
                    self.cache[base_netloc] = None
                    return False

                rfp = RobotFileParser()
                rfp.set_url(robots_url)
                try:
                    # Read robots.txt with safe timeout
                    rfp.read()
                    self.cache[base_netloc] = rfp
                except Exception as e:
                    logger.debug(f"Could not read robots.txt for {domain}: {e}")
                    # In accordance with web standard: if robots.txt unreachable / 404, allow crawling
                    self.cache[base_netloc] = None

            rfp = self.cache.get(base_netloc)
            if rfp is None:
                return True
            return rfp.can_fetch(self.user_agent, url)
        except Exception as exc:
            logger.warning(f"Error checking robots.txt for {url}: {exc}")
            return True


class BFSCrawlerEngine:
    """
    Breadth-First Search (BFS) Web Crawler.
    Traverses hyperlinks level by level up to max_pages successful HTML pages.
    """

    def __init__(
        self,
        session_id: int,
        start_url: str = "https://trunojoyo.ac.id/",
        max_pages: int = 300,
        delay: float = 0.5,
        user_agent: str = "Mozilla/5.0 (compatible; PPW-PageRankBot/1.0; +https://trunojoyo.ac.id/)",
        timeout: int = 10
    ):
        self.session_id = session_id
        self.start_url = start_url
        self.max_pages = max_pages
        self.delay = delay
        self.user_agent = user_agent
        self.timeout = timeout

        self.fetcher = WebFetcher(user_agent=self.user_agent, timeout=self.timeout)
        self.robots_checker = RobotsChecker(user_agent=self.user_agent)

        # FIFO Queue for BFS traversal: tuple of (normalized_url, depth)
        self.queue: deque = deque()

        # Deduplication sets by SHA-256 hash
        self.visited_hashes: Set[str] = set()
        self.crawled_hashes: Set[str] = set()

        # Mapping of url_hash -> page_id in MySQL
        self.url_to_page_id: Dict[str, int] = {}

        # Counter metrics
        self.total_discovered: int = 0
        self.total_crawled: int = 0
        self.total_failed: int = 0

    def _log(self, message: str, log_level: str = "INFO", page_url: str = None):
        """Append log entry to database and application logger."""
        try:
            log_entry = CrawlLog(
                session_id=self.session_id,
                page_url=page_url,
                log_level=log_level,
                message=message,
                created_at=datetime.utcnow()
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.error(f"Failed to write crawl log to DB: {exc}")

        if log_level == "ERROR":
            logger.error(message)
        elif log_level == "WARNING":
            logger.warning(message)
        else:
            logger.info(message)

    def _sync_session_status(self, status: str = None, finished: bool = False):
        """Update crawl_sessions record with current metrics."""
        try:
            session = db.session.get(CrawlSession, self.session_id)
            if session:
                if status:
                    session.status = status
                session.total_discovered = self.total_discovered
                session.total_crawled = self.total_crawled
                session.total_failed = self.total_failed
                if finished:
                    session.finished_at = datetime.utcnow()
                db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.error(f"Error syncing crawl session #{self.session_id}: {exc}")

    def run(self) -> Dict:
        """
        Execute the BFS crawling loop.
        Returns a summary dictionary of the crawling session results.
        """
        norm_start_url = normalize_url(self.start_url)
        if not norm_start_url:
            self._log(f"Seed URL '{self.start_url}' tidak valid atau skema tidak didukung.", "ERROR")
            self._sync_session_status(status="failed", finished=True)
            return {"success": False, "error": "Seed URL invalid"}

        start_hash = get_url_hash(norm_start_url)

        # Mark session as running
        self._sync_session_status(status="running")
        self._log(
            f"Memulai sesi crawling #{self.session_id} dengan Seed URL: {norm_start_url} (Target maks: {self.max_pages} halaman)",
            "INFO",
            page_url=norm_start_url
        )

        # Enqueue seed URL
        self.queue.append((norm_start_url, 0))
        self.visited_hashes.add(start_hash)
        self.total_discovered = 1

        # Load existing page IDs for this session if any (e.g., resuming)
        existing_pages = Page.query.filter_by(session_id=self.session_id).all()
        for p in existing_pages:
            self.url_to_page_id[p.url_hash] = p.id
            self.visited_hashes.add(p.url_hash)
            if p.crawl_status == "success":
                self.crawled_hashes.add(p.url_hash)

        # ----------------- MAIN BFS LOOP ----------------- #
        while self.queue and self.total_crawled < self.max_pages:
            current_url, depth = self.queue.popleft()
            current_hash = get_url_hash(current_url)
            current_domain = extract_domain(current_url)

            # 1. Check robots.txt
            if not self.robots_checker.can_fetch(current_url):
                self.total_failed += 1
                self._record_page(
                    url=current_url,
                    url_hash=current_hash,
                    domain=current_domain,
                    depth=depth,
                    crawl_status="failed",
                    error_message="Dilarang oleh aturan robots.txt situs."
                )
                self._log(f"[ROBOTS.TXT BLOCKED] Halaman dilarang untuk di-crawl: {current_url}", "WARNING", current_url)
                continue

            # 2. Politeness delay between requests
            if self.delay > 0:
                time.sleep(self.delay)

            # 3. Fetch Page
            fetch_result = self.fetcher.fetch(current_url)

            # 4. Handle Fetch Failure
            if not fetch_result.success:
                self.total_failed += 1
                self._record_page(
                    url=current_url,
                    url_hash=current_hash,
                    final_url=fetch_result.final_url,
                    domain=current_domain,
                    depth=depth,
                    status_code=fetch_result.status_code,
                    content_type=fetch_result.content_type,
                    crawl_status="failed",
                    error_message=fetch_result.error_message
                )
                self._log(
                    f"[CRAWL GAGAL] Level {depth}: {current_url} | Error: {fetch_result.error_message}",
                    "WARNING",
                    current_url
                )
                self._sync_session_status()
                continue

            # 5. Handle Fetch Success (HTML page)
            final_url = fetch_result.final_url or current_url
            final_domain = extract_domain(final_url) or current_domain

            # Extract title and outbound links
            extracted = HTMLExtractor.extract(fetch_result.html, base_url=final_url)

            # Save page record to MySQL
            page = self._record_page(
                url=current_url,
                url_hash=current_hash,
                final_url=final_url,
                domain=final_domain,
                title=extracted.title,
                status_code=fetch_result.status_code,
                content_type=fetch_result.content_type,
                depth=depth,
                crawl_status="success",
                crawled_at=datetime.utcnow()
            )

            self.total_crawled += 1
            self.crawled_hashes.add(current_hash)
            self._log(
                f"[CRAWL SUKSES #{self.total_crawled}] Level {depth}: {current_url} "
                f"({fetch_result.status_code}) '{extracted.title[:50]}' - Ditemukan {len(extracted.links)} link",
                "INFO",
                current_url
            )

            # 6. Save outbound links and enqueue new URLs for BFS
            self._process_links(source_page=page, links=extracted.links, current_depth=depth)

            # Update session metrics in database
            self._sync_session_status()

        # ----------------- LOOP COMPLETE ----------------- #
        self._sync_session_status(status="completed", finished=True)
        self._log(
            f"Sesi crawling #{self.session_id} selesai. Berhasil: {self.total_crawled}, "
            f"Gagal: {self.total_failed}, Total ditemukan: {self.total_discovered}.",
            "INFO"
        )

        return {
            "success": True,
            "session_id": self.session_id,
            "total_crawled": self.total_crawled,
            "total_failed": self.total_failed,
            "total_discovered": self.total_discovered,
            "queue_remaining": len(self.queue)
        }

    def _record_page(
        self,
        url: str,
        url_hash: str,
        domain: str,
        depth: int,
        crawl_status: str,
        final_url: str = None,
        title: str = None,
        status_code: int = None,
        content_type: str = None,
        error_message: str = None,
        crawled_at: datetime = None
    ) -> Page:
        """Insert or update a page record in MySQL and resolve dangling links."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                page = Page.query.filter_by(session_id=self.session_id, url_hash=url_hash).first()
                if not page:
                    page = Page(
                        session_id=self.session_id,
                        url=url,
                        url_hash=url_hash,
                        final_url=final_url,
                        domain=domain,
                        title=title,
                        status_code=status_code,
                        content_type=content_type,
                        depth=depth,
                        crawl_status=crawl_status,
                        error_message=error_message,
                        crawled_at=crawled_at or datetime.utcnow()
                    )
                    db.session.add(page)
                else:
                    page.final_url = final_url or page.final_url
                    page.domain = domain or page.domain
                    page.title = title or page.title
                    page.status_code = status_code or page.status_code
                    page.content_type = content_type or page.content_type
                    page.crawl_status = crawl_status
                    page.error_message = error_message
                    page.crawled_at = crawled_at or datetime.utcnow()

                db.session.flush()
                self.url_to_page_id[url_hash] = page.id

                # Update target_page_id for any prior links that pointed to this URL hash
                Link.query.filter_by(
                    session_id=self.session_id,
                    target_url_hash=url_hash,
                    target_page_id=None
                ).update({"target_page_id": page.id})

                db.session.commit()
                return page
            except Exception as exc:
                db.session.rollback()
                err_str = str(exc)
                if ("1213" in err_str or "Deadlock" in err_str or "1205" in err_str) and attempt < max_retries - 1:
                    logger.warning(f"Deadlock in _record_page for {url}, retrying ({attempt + 1}/{max_retries})...")
                    time.sleep(0.2 * (attempt + 1))
                    continue
                logger.error(f"Error saving page {url} to database: {exc}")
                raise

    def _process_links(self, source_page: Page, links: list, current_depth: int):
        """Save outbound links to the links table and enqueue unvisited targets."""
        # Prepare links to add
        links_to_add = []
        for link_info in links:
            target_url = link_info.target_url
            target_hash = link_info.target_url_hash
            anchor_text = link_info.anchor_text

            # Check if target page already exists in this session
            target_page_id = self.url_to_page_id.get(target_hash, None)

            try:
                # Avoid inserting exact duplicate edge (source_page_id -> target_url_hash)
                existing_link = Link.query.filter_by(
                    session_id=self.session_id,
                    source_page_id=source_page.id,
                    target_url_hash=target_hash
                ).first()

                if not existing_link:
                    links_to_add.append({
                        "session_id": self.session_id,
                        "source_page_id": source_page.id,
                        "target_url": target_url,
                        "target_url_hash": target_hash,
                        "target_page_id": target_page_id,
                        "anchor_text": anchor_text
                    })
            except Exception as e:
                logger.error(f"Error checking link from {source_page.id} to {target_url}: {e}")

            # Enqueue target URL for BFS if not yet visited and still within discovery quota
            if target_hash not in self.visited_hashes:
                self.visited_hashes.add(target_hash)
                self.total_discovered += 1
                # Only enqueue if we have not reached max successful pages
                if self.total_crawled < self.max_pages:
                    self.queue.append((target_url, current_depth + 1))

        # Bulk commit with deadlock retry
        max_retries = 3
        for attempt in range(max_retries):
            try:
                for item in links_to_add:
                    link_record = Link(
                        session_id=item["session_id"],
                        source_page_id=item["source_page_id"],
                        target_url=item["target_url"],
                        target_url_hash=item["target_url_hash"],
                        target_page_id=item["target_page_id"],
                        anchor_text=item["anchor_text"]
                    )
                    db.session.add(link_record)
                db.session.commit()
                break
            except Exception as exc:
                db.session.rollback()
                err_str = str(exc)
                if ("1213" in err_str or "Deadlock" in err_str or "1205" in err_str) and attempt < max_retries - 1:
                    logger.warning(
                        f"Deadlock committing links for source page {source_page.id}, retrying ({attempt + 1}/{max_retries})..."
                    )
                    time.sleep(0.2 * (attempt + 1))
                    continue
                logger.error(f"Error committing links for source page {source_page.id}: {exc}")
                break
