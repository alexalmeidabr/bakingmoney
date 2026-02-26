from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, UniqueConstraint

from .database import Base


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(16), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Scenario(Base):
    __tablename__ = "scenarios"
    __table_args__ = (
        UniqueConstraint("ticker", "horizon_years", "scenario_type", name="uq_scenario_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(16), index=True, nullable=False)
    scenario_type = Column(String(16), nullable=False)
    horizon_years = Column(Integer, default=5, nullable=False)
    price_low = Column(Float, nullable=False)
    price_high = Column(Float, nullable=False)
    cagr_low = Column(Float, nullable=False)
    cagr_high = Column(Float, nullable=False)
    probability = Column(Float, nullable=False)
    assumptions_risks = Column(Text, default="", nullable=False)
    what_to_look_for = Column(Text, default="", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class RatioCache(Base):
    __tablename__ = "ratio_cache"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(16), unique=True, nullable=False, index=True)
    pe = Column(Float, nullable=True)
    ps = Column(Float, nullable=True)
    ev_ebitda = Column(Float, nullable=True)
    dividend_yield = Column(Float, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
