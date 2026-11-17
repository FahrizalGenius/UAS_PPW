from datetime import datetime
from app.extensions import db

class CrawlLog(db.Model):
    __tablename__ = "crawl_logs"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    session_id = db.Column(db.BigInteger, db.ForeignKey("crawl_sessions.id"), nullable=False)
    page_url = db.Column(db.String(2048), nullable=True)
    log_level = db.Column(
        db.Enum("INFO", "WARNING", "ERROR", name="crawl_log_level"),
        default="INFO"
    )
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    session = db.relationship("CrawlSession", back_populates="logs")

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "page_url": self.page_url,
            "log_level": self.log_level,
            "message": self.message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<CrawlLog [{self.log_level}] Session {self.session_id}: {self.message[:50]}>"
