import os
import json
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String,
    DateTime, Text, Boolean, Float
)
from sqlalchemy.orm import declarative_base, sessionmaker

# SQLite — stores everything in a single file, zero setup
# For production you'd swap this for PostgreSQL
DB_PATH = "reviews.db"
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class PRReview(Base):
    """
    Stores every review your bot generates.
    This becomes your dataset for evaluation.
    """
    __tablename__ = "pr_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo = Column(String, nullable=False)
    pr_number = Column(Integer, nullable=False)
    pr_title = Column(String)
    changed_files = Column(Text)       # JSON list
    impacted_files = Column(Text)      # JSON list
    summary = Column(Text)
    risks = Column(Text)               # JSON list
    suggestions = Column(Text)         # JSON list
    test_coverage = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class SuggestionLabel(Base):
    """
    Ground truth labels for individual suggestions.
    You manually fill these in after a PR merges.
    
    acted_on=True means the author made a change based on this suggestion.
    acted_on=False means it was ignored — potential noise.
    """
    __tablename__ = "suggestion_labels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(Integer, nullable=False)  # FK to PRReview
    suggestion_text = Column(Text)
    is_risk = Column(Boolean, default=False)     # True if this is a risk, False if suggestion
    acted_on = Column(Boolean, nullable=True)    # None = unlabeled, True/False = labeled
    labeled_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)


def init_db():
    """Creates all tables if they don't exist."""
    Base.metadata.create_all(engine)
    print("✅ Database initialized")


def save_review(
    repo: str,
    pr_number: int,
    pr_title: str,
    changed_files: list,
    impacted_files: list,
    review: dict
) -> int:
    """
    Saves a generated review to the database.
    Returns the review ID — useful for linking labels later.
    Also creates unlabeled SuggestionLabel rows for each
    risk and suggestion, ready for you to label later.
    """
    session = SessionLocal()
    try:
        pr_review = PRReview(
            repo=repo,
            pr_number=pr_number,
            pr_title=pr_title,
            changed_files=json.dumps(changed_files),
            impacted_files=json.dumps(impacted_files),
            summary=review.get("summary", ""),
            risks=json.dumps(review.get("risks", [])),
            suggestions=json.dumps(review.get("suggestions", [])),
            test_coverage=review.get("test_coverage", ""),
        )
        session.add(pr_review)
        session.flush()  # get the ID before commit

        # Create unlabeled label rows for each risk + suggestion
        for risk in review.get("risks", []):
            session.add(SuggestionLabel(
                review_id=pr_review.id,
                suggestion_text=risk,
                is_risk=True,
                acted_on=None,
            ))

        for suggestion in review.get("suggestions", []):
            session.add(SuggestionLabel(
                review_id=pr_review.id,
                suggestion_text=suggestion,
                is_risk=False,
                acted_on=None,
            ))

        session.commit()
        return pr_review.id

    finally:
        session.close()


def get_all_reviews() -> list[dict]:
    """Fetches all reviews for the dashboard."""
    session = SessionLocal()
    try:
        reviews = session.query(PRReview).order_by(PRReview.created_at.desc()).all()
        return [
            {
                "id": r.id,
                "repo": r.repo,
                "pr_number": r.pr_number,
                "pr_title": r.pr_title,
                "summary": r.summary,
                "risks": json.loads(r.risks or "[]"),
                "suggestions": json.loads(r.suggestions or "[]"),
                "test_coverage": r.test_coverage,
                "created_at": r.created_at,
            }
            for r in reviews
        ]
    finally:
        session.close()


def get_labels() -> list[dict]:
    """Fetches all suggestion labels for precision calculation."""
    session = SessionLocal()
    try:
        labels = session.query(SuggestionLabel).all()
        return [
            {
                "id": l.id,
                "review_id": l.review_id,
                "suggestion_text": l.suggestion_text,
                "is_risk": l.is_risk,
                "acted_on": l.acted_on,
            }
            for l in labels
        ]
    finally:
        session.close()


def label_suggestion(label_id: int, acted_on: bool, notes: str = ""):
    """Marks a suggestion as acted on or ignored."""
    session = SessionLocal()
    try:
        label = session.query(SuggestionLabel).filter(
            SuggestionLabel.id == label_id
        ).first()
        if label:
            label.acted_on = acted_on
            label.labeled_at = datetime.utcnow()
            label.notes = notes
            session.commit()
    finally:
        session.close()