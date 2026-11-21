"""Database models and portability (SQLite local / PostgreSQL on hosted service)."""
import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.pool import StaticPool

Base = declarative_base()

def now():
    return datetime.now(timezone.utc)

class Incident(Base):
    __tablename__ = "incidents"
    id = Column(Integer, primary_key=True)
    title = Column(String(180), nullable=False)
    description = Column(Text, nullable=False)
    ward = Column(String(80), nullable=False)
    location = Column(String(150), nullable=False, default="")
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    category_key = Column(String(30), nullable=False)
    category = Column(String(90), nullable=False)
    department = Column(String(90), nullable=False)
    confidence = Column(Float, default=0)
    priority = Column(Integer, nullable=False)
    priority_label = Column(String(20), nullable=False)
    reasons_json = Column(Text, nullable=False, default="[]")
    status = Column(String(30), nullable=False, default="reported")
    assigned_to = Column(String(60), nullable=False, default="")
    resolution_round = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now, nullable=False)
    reports = relationship("Report", back_populates="incident", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="incident", cascade="all, delete-orphan")
    verifications = relationship("Verification", back_populates="incident", cascade="all, delete-orphan")

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    reporter_alias = Column(String(45), nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now, nullable=False)
    incident = relationship("Incident", back_populates="reports")
    __table_args__ = (UniqueConstraint("incident_id", "reporter_alias", name="uq_incident_reporter"),)

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    actor = Column(String(60), nullable=False)
    kind = Column(String(30), nullable=False)
    note = Column(Text, default="", nullable=False)
    attachment = Column(String(200), default="", nullable=False)
    created_at = Column(DateTime(timezone=True), default=now, nullable=False)
    incident = relationship("Incident", back_populates="events")

class Verification(Base):
    __tablename__ = "verifications"
    id = Column(Integer, primary_key=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    reporter_alias = Column(String(45), nullable=False)
    round_no = Column(Integer, nullable=False)
    verdict = Column(String(15), nullable=False)
    note = Column(Text, default="", nullable=False)
    created_at = Column(DateTime(timezone=True), default=now, nullable=False)
    incident = relationship("Incident", back_populates="verifications")
    __table_args__ = (UniqueConstraint("incident_id", "reporter_alias", "round_no", name="uq_verification_round"),)

# create_app() supports per-test database injection, no globals used for sessions.
def make_session(database_url: str | None = None):
    database_url = database_url or os.environ.get("DATABASE_URL", "sqlite:///./civicresolve.db")
    # Some providers still return postgres://; SQLAlchemy requires postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    opts = {"connect_args": {"check_same_thread":False}} if database_url.startswith("sqlite") else {}
    if database_url == "sqlite://":
        opts["poolclass"] = StaticPool
    engine = create_engine(database_url, pool_pre_ping=True, **opts)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False), engine
