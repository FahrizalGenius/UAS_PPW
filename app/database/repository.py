"""Repository layer for database operations."""
import logging
from datetime import datetime
from app.extensions import db
from app.models import CrawlSession, Page, Link, PageRankResult, CrawlLog

logger = logging.getLogger(__name__)

class CrawlRepository:
    """Handles persistence and retrieval for web crawling and PageRank data."""

    # ------------------ Session Operations ------------------ #
    @staticmethod
    def create_session(start_url: str, max_pages: int = 300) -> CrawlSession:
        session = CrawlSession(
            start_url=start_url,
            max_pages=max_pages,
            status="pending",
            total_discovered=1,
            total_crawled=0,
            total_failed=0,
            started_at=datetime.utcnow()
        )
        db.session.add(session)
        db.session.commit()
        return session

    @staticmethod
    def get_session(session_id: int) -> CrawlSession:
        return db.session.get(CrawlSession, session_id)

    @staticmethod
    def get_latest_session() -> CrawlSession:
        return CrawlSession.query.order_by(CrawlSession.id.desc()).first()

    @staticmethod
    def get_all_sessions():
        return CrawlSession.query.order_by(CrawlSession.created_at.desc()).all()

    @staticmethod
    def update_session_status(session_id: int, status: str, finished: bool = False):
        session = db.session.get(CrawlSession, session_id)
        if session:
            session.status = status
            if finished:
                session.finished_at = datetime.utcnow()
            db.session.commit()
        return session

    # ------------------ Page Operations ------------------ #
    @staticmethod
    def get_page_by_hash(session_id: int, url_hash: str) -> Page:
        return Page.query.filter_by(session_id=session_id, url_hash=url_hash).first()

    @staticmethod
    def add_page(
        session_id: int,
        url: str,
        url_hash: str,
        domain: str,
        depth: int = 0,
        final_url: str = None,
        title: str = None,
        status_code: int = None,
        content_type: str = None,
        crawl_status: str = "pending",
        error_message: str = None,
        crawled_at: datetime = None
    ) -> Page:
        page = Page(
            session_id=session_id,
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
            crawled_at=crawled_at
        )
        db.session.add(page)
        db.session.commit()
        return page

    @staticmethod
    def get_pages_by_session(session_id: int, crawl_status: str = None):
        query = Page.query.filter_by(session_id=session_id)
        if crawl_status:
            query = query.filter_by(crawl_status=crawl_status)
        return query.all()

    # ------------------ Link Operations ------------------ #
    @staticmethod
    def add_link(
        session_id: int,
        source_page_id: int,
        target_url: str,
        target_url_hash: str,
        target_page_id: int = None,
        anchor_text: str = None
    ) -> Link:
        link = Link(
            session_id=session_id,
            source_page_id=source_page_id,
            target_url=target_url,
            target_url_hash=target_url_hash,
            target_page_id=target_page_id,
            anchor_text=anchor_text
        )
        db.session.add(link)
        db.session.commit()
        return link

    @staticmethod
    def get_links_by_session(session_id: int):
        return Link.query.filter_by(session_id=session_id).all()

    # ------------------ PageRank Operations ------------------ #
    @staticmethod
    def save_pagerank_results(session_id: int, ranks: list):
        """
        ranks: list of dicts with keys:
            page_id, pagerank_score, ranking_position, damping_factor, iterations
        """
        # Remove any existing pagerank results for this session
        PageRankResult.query.filter_by(session_id=session_id).delete()

        now = datetime.utcnow()
        for item in ranks:
            result = PageRankResult(
                session_id=session_id,
                page_id=item["page_id"],
                pagerank_score=item["pagerank_score"],
                ranking_position=item["ranking_position"],
                damping_factor=item.get("damping_factor", 0.85),
                iterations=item.get("iterations", None),
                calculated_at=now
            )
            db.session.add(result)
        db.session.commit()

    @staticmethod
    def get_pagerank_results(session_id: int, limit: int = None):
        query = (
            PageRankResult.query.filter_by(session_id=session_id)
            .order_by(PageRankResult.ranking_position.asc())
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    # ------------------ Log Operations ------------------ #
    @staticmethod
    def add_log(
        session_id: int,
        message: str,
        log_level: str = "INFO",
        page_url: str = None
    ) -> CrawlLog:
        log = CrawlLog(
            session_id=session_id,
            message=message,
            log_level=log_level,
            page_url=page_url
        )
        db.session.add(log)
        db.session.commit()
        return log
