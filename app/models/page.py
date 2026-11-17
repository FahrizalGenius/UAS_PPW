from datetime import datetime
from app.extensions import db

class Page(db.Model):
    __tablename__ = "pages"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    session_id = db.Column(db.BigInteger, db.ForeignKey("crawl_sessions.id"), nullable=False)
    url = db.Column(db.String(2048), nullable=False)
    url_hash = db.Column(db.String(64), nullable=False)
    final_url = db.Column(db.String(2048), nullable=True)
    domain = db.Column(db.String(255), nullable=False)
    title = db.Column(db.Text, nullable=True)
    status_code = db.Column(db.Integer, nullable=True)
    content_type = db.Column(db.String(255), nullable=True)
    depth = db.Column(db.Integer, default=0)
    crawl_status = db.Column(
        db.Enum("pending", "success", "failed", "skipped", name="page_crawl_status"),
        default="pending"
    )
    error_message = db.Column(db.Text, nullable=True)
    crawled_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    session = db.relationship("CrawlSession", back_populates="pages")
    outgoing_links = db.relationship(
        "Link",
        foreign_keys="Link.source_page_id",
        back_populates="source_page",
        cascade="all, delete-orphan"
    )
    incoming_links = db.relationship(
        "Link",
        foreign_keys="Link.target_page_id",
        back_populates="target_page"
    )
    pagerank_result = db.relationship(
        "PageRankResult",
        back_populates="page",
        uselist=False,
        cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "url": self.url,
            "url_hash": self.url_hash,
            "final_url": self.final_url,
            "domain": self.domain,
            "title": self.title,
            "status_code": self.status_code,
            "content_type": self.content_type,
            "depth": self.depth,
            "crawl_status": self.crawl_status,
            "error_message": self.error_message,
            "crawled_at": self.crawled_at.isoformat() if self.crawled_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Page {self.id}: {self.url} [{self.crawl_status}]>"
