from datetime import datetime
from app.extensions import db

class PageRankResult(db.Model):
    __tablename__ = "pagerank_results"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    session_id = db.Column(db.BigInteger, db.ForeignKey("crawl_sessions.id"), nullable=False)
    page_id = db.Column(db.BigInteger, db.ForeignKey("pages.id"), nullable=False)
    pagerank_score = db.Column(db.Float, nullable=False, default=0.0)
    ranking_position = db.Column(db.Integer, nullable=True)
    damping_factor = db.Column(db.Float, default=0.85)
    iterations = db.Column(db.Integer, nullable=True)
    calculated_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    session = db.relationship("CrawlSession", back_populates="pagerank_results")
    page = db.relationship("Page", back_populates="pagerank_result")

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "page_id": self.page_id,
            "pagerank_score": self.pagerank_score,
            "ranking_position": self.ranking_position,
            "damping_factor": self.damping_factor,
            "iterations": self.iterations,
            "calculated_at": self.calculated_at.isoformat() if self.calculated_at else None,
        }

    def __repr__(self):
        return f"<PageRankResult Page({self.page_id}): Rank {self.ranking_position} ({self.pagerank_score})>"
