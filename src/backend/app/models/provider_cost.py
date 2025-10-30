"""Provider Cost Models

Models for tracking LLM provider usage, costs, and automated selection.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProviderCost(Base):
    """Daily cost tracking per LLM provider"""

    __tablename__ = "provider_costs"

    id: Mapped[int] = mapped_column(Integer, autoincrement=True, primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    tokens_consumed: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False, server_default="0")
    comments_analyzed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ProviderCost provider={self.provider} date={self.date} cost=${self.cost_usd}>"


class ProviderSelectionLog(Base):
    """Log of automated provider selections"""

    __tablename__ = "provider_selection_log"

    id: Mapped[int] = mapped_column(Integer, autoincrement=True, primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_score: Mapped[float] = mapped_column(Float, nullable=False)
    mean_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cost_per_1k_tokens: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    fallback_provider: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    selected_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ProviderSelectionLog provider={self.provider} at={self.selected_at}>"


class DriftCheck(Base):
    """QA drift monitoring results"""

    __tablename__ = "drift_checks"

    id: Mapped[int] = mapped_column(Integer, autoincrement=True, primary_key=True)
    check_date: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    primary_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    secondary_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    samples_checked: Mapped[int] = mapped_column(Integer, nullable=False)
    agreement_score: Mapped[float] = mapped_column(Float, nullable=False)
    sentiment_agreement: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sarcasm_agreement: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # "ok", "warning", "critical"
    alert_sent: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)

    def __repr__(self) -> str:
        return f"<DriftCheck primary={self.primary_provider} agreement={self.agreement_score:.3f} status={self.status}>"
