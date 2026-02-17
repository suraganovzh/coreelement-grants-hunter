"""SQLAlchemy models for Grant Hunter AI."""

import os
from datetime import datetime, date

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    Date,
    DateTime,
    Boolean,
    Float,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


def get_engine(database_url: str | None = None):
    """Create database engine."""
    url = database_url or os.getenv("DATABASE_URL", "sqlite:///data/grants_hunter.db")
    return create_engine(url, echo=False)


def get_session(database_url: str | None = None):
    """Create a new database session."""
    engine = get_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()


def init_db(database_url: str | None = None):
    """Initialize database — create all tables."""
    engine = get_engine(database_url)
    Base.metadata.create_all(engine)
    return engine


class Grant(Base):
    """Grant opportunity."""

    __tablename__ = "grants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    funder = Column(String(200))
    description = Column(Text)
    amount_min = Column(Integer)
    amount_max = Column(Integer)
    currency = Column(String(3), default="USD")
    deadline = Column(Date)
    url = Column(Text)
    source = Column(String(100))
    grant_type = Column(String(50))  # federal, private, international, etc.
    industry_tags = Column(JSON, default=list)
    eligibility_text = Column(Text)
    requirements_text = Column(Text)
    evaluation_criteria = Column(Text)
    complexity_score = Column(Integer)  # 1-10
    fit_score = Column(Integer)  # 0-100%
    estimated_prep_hours = Column(Integer)
    status = Column(String(50), default="found")  # found, qualified, not_relevant, archived
    urgency = Column(String(20))  # urgent, important, planning
    ai_analysis = Column(Text)  # JSON: detailed AI analysis
    found_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    applications = relationship("Application", back_populates="grant", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="grant", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Grant(id={self.id}, title='{self.title[:50]}', fit={self.fit_score}%)>"

    @property
    def amount_display(self) -> str:
        from src.utils.text_processor import TextProcessor
        if self.amount_min and self.amount_max and self.amount_min != self.amount_max:
            low = TextProcessor.format_currency(self.amount_min, self.currency)
            high = TextProcessor.format_currency(self.amount_max, self.currency)
            return f"{low} - {high}"
        return TextProcessor.format_currency(self.amount_max or self.amount_min, self.currency)

    @property
    def days_until_deadline(self) -> int | None:
        if self.deadline is None:
            return None
        return (self.deadline - date.today()).days


class Application(Base):
    """Grant application tracking."""

    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    grant_id = Column(Integer, ForeignKey("grants.id"), nullable=False)
    status = Column(String(50), default="draft")
    # draft, review, ready, submitted, under_review, won, rejected, archived
    draft_text = Column(Text)
    executive_summary = Column(Text)
    technical_approach = Column(Text)
    budget_justification = Column(Text)
    impact_statement = Column(Text)
    submission_date = Column(Date)
    decision_date = Column(Date)
    award_amount = Column(Integer)
    notes = Column(Text)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    grant = relationship("Grant", back_populates="applications")
    documents = relationship("Document", back_populates="application", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Application(id={self.id}, grant_id={self.grant_id}, status='{self.status}')>"


class Document(Base):
    """Documents attached to applications."""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    document_type = Column(String(100))  # pitch_deck, financials, technical_spec, etc.
    file_path = Column(Text)
    file_name = Column(String(255))
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    application = relationship("Application", back_populates="documents")


class Alert(Base):
    """Alert/notification records."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    grant_id = Column(Integer, ForeignKey("grants.id"))
    alert_type = Column(String(50))  # new_grant, deadline_warning, status_change
    urgency = Column(String(20))  # urgent, important, planning
    message = Column(Text)
    sent_date = Column(DateTime)
    read = Column(Boolean, default=False)

    # Relationships
    grant = relationship("Grant", back_populates="alerts")


class SearchLog(Base):
    """Search history for tracking scraper runs."""

    __tablename__ = "search_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(100))
    search_query = Column(Text)
    results_count = Column(Integer, default=0)
    new_grants_found = Column(Integer, default=0)
    errors = Column(Text)
    duration_seconds = Column(Float)
    search_date = Column(DateTime, default=datetime.utcnow)
