from datetime import datetime
from app.extensions import db

class CrawlSession(db.Model):
    __tablename__ = "crawl_sessions"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    start_url = db.Column(db.String(2048), nullable=False)
    max_pages = db.Column(db.Integer, nullable=False, default=300)
    total_discovered = db.Column(db.Integer, default=0)
    total_crawled = db.Column(db.Integer, default=0)
    total_failed = db.Column(db.Integer, default=0)
    status = db.Column(
        db.Enum("pending", "running", "completed", "failed", "cancelled", name="crawl_session_status"),
        default="pending"
    )
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    pages = db.relationship("Page", back_populates="session", cascade="all, delete-orphan")
    links = db.relationship("Link", back_populates="session", cascade="all, delete-orphan")
    pagerank_results = db.relationship("PageRankResult", back_populates="session", cascade="all, delete-orphan")
    logs = db.relationship("CrawlLog", back_populates="session", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "start_url": self.start_url,
            "max_pages": self.max_pages,
            "total_discovered": self.total_discovered,
            "total_crawled": self.total_crawled,
            "total_failed": self.total_failed,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<CrawlSession {self.id}: {self.start_url} [{self.status}]>"
