"""Service layer for orchestrating web crawling operations."""
import logging
from typing import Dict, Tuple, Optional
from datetime import datetime

from app.extensions import db
from app.models import CrawlSession, Page, Link, CrawlLog
from app.crawler import BFSCrawlerEngine, normalize_url, is_valid_http_url
from config import Config

logger = logging.getLogger(__name__)

class CrawlingService:
    """Orchestrates web crawling sessions, validation, and database operations."""

    @staticmethod
    def start_crawl_session(
        start_url: str,
        max_pages: int = 300,
        delay: float = None,
        timeout: int = None
    ) -> Tuple[bool, Optional[CrawlSession], str]:
        """
        Validate parameters, initialize session record, and execute BFS crawler.
        
        Returns:
            (success, session, message)
        """
        # 1. Parameter Validation
        if not is_valid_http_url(start_url):
            return False, None, f"URL awal '{start_url}' tidak valid atau skema bukan HTTP/HTTPS."

        norm_start_url = normalize_url(start_url)
        if not norm_start_url:
            return False, None, f"Gagal menormalisasi URL awal '{start_url}'."

        if max_pages <= 0 or max_pages > 1000:
            return False, None, "Jumlah batas maksimal halaman harus antara 1 sampai 1000."

        if delay is None:
            delay = Config.CRAWL_REQUEST_DELAY
        if timeout is None:
            timeout = Config.CRAWL_REQUEST_TIMEOUT

        # 2. Create CrawlSession record in MySQL
        session = CrawlSession(
            start_url=norm_start_url,
            max_pages=max_pages,
            total_discovered=1,
            total_crawled=0,
            total_failed=0,
            status="pending",
            started_at=datetime.utcnow()
        )
        try:
            db.session.add(session)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.error(f"Failed to create CrawlSession record: {exc}")
            return False, None, f"Gagal membuat sesi database: {str(exc)}"

        # 3. Instantiate and run BFS Crawler Engine
        try:
            engine = BFSCrawlerEngine(
                session_id=session.id,
                start_url=norm_start_url,
                max_pages=max_pages,
                delay=delay,
                user_agent=Config.CRAWL_USER_AGENT,
                timeout=timeout
            )
            result = engine.run()
            # Refresh session object from DB
            db.session.refresh(session)
            return True, session, "Proses crawling berhasil diselesaikan."
        except Exception as exc:
            logger.error(f"Error during crawl execution for session #{session.id}: {exc}")
            session.status = "failed"
            session.finished_at = datetime.utcnow()
            db.session.commit()
            return False, session, f"Terjadi kesalahan saat crawling: {str(exc)}"

    @staticmethod
    def get_session_stats(session_id: int) -> Dict:
        """Retrieve aggregated statistics for a specific session."""
        session = db.session.get(CrawlSession, session_id)
        if not session:
            return {}

        success_count = Page.query.filter_by(session_id=session_id, crawl_status="success").count()
        failed_count = Page.query.filter_by(session_id=session_id, crawl_status="failed").count()
        links_count = Link.query.filter_by(session_id=session_id).count()

        return {
            "session_id": session.id,
            "start_url": session.start_url,
            "max_pages": session.max_pages,
            "total_discovered": session.total_discovered,
            "total_crawled": success_count,
            "total_failed": failed_count,
            "total_links": links_count,
            "status": session.status,
            "started_at": session.started_at,
            "finished_at": session.finished_at,
        }
