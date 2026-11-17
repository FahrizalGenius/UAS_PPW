from datetime import datetime
from app.extensions import db

class Link(db.Model):
    __tablename__ = "links"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    session_id = db.Column(db.BigInteger, db.ForeignKey("crawl_sessions.id"), nullable=False)
    source_page_id = db.Column(db.BigInteger, db.ForeignKey("pages.id"), nullable=False)
    target_url = db.Column(db.String(2048), nullable=False)
    target_url_hash = db.Column(db.String(64), nullable=False)
    target_page_id = db.Column(db.BigInteger, db.ForeignKey("pages.id"), nullable=True)
    anchor_text = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    session = db.relationship("CrawlSession", back_populates="links")
    source_page = db.relationship(
        "Page",
        foreign_keys=[source_page_id],
        back_populates="outgoing_links"
    )
    target_page = db.relationship(
        "Page",
        foreign_keys=[target_page_id],
        back_populates="incoming_links"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "source_page_id": self.source_page_id,
            "target_url": self.target_url,
            "target_url_hash": self.target_url_hash,
            "target_page_id": self.target_page_id,
            "anchor_text": self.anchor_text,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Link {self.id}: Page({self.source_page_id}) -> {self.target_url}>"
