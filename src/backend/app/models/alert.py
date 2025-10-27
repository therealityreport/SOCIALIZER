from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AlertRule(Base):
    __tablename__ = "alert_rules"
    __table_args__ = (
        Index("ix_alert_rules_thread_active", "thread_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    thread_id: Mapped[Optional[int]] = mapped_column(ForeignKey("threads.id", ondelete="CASCADE"))
    cast_member_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cast_members.id", ondelete="SET NULL"))
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False)
    condition: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    channels: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    thread = relationship("Thread", back_populates="alert_rules")
    cast_member = relationship("CastMember", back_populates="alert_rules")
    events = relationship(
        "AlertEvent",
        back_populates="rule",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<AlertRule id={self.id} type={self.rule_type} active={self.is_active}>"


class AlertEvent(Base):
    __tablename__ = "alert_events"
    __table_args__ = (
        Index("ix_alert_events_rule", "alert_rule_id"),
        Index("ix_alert_events_triggered_at", "triggered_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_rule_id: Mapped[int] = mapped_column(ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False)
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    cast_member_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cast_members.id", ondelete="SET NULL"))
    triggered_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    delivered_channels: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    rule = relationship("AlertRule", back_populates="events")
    thread = relationship("Thread", back_populates="alert_events")
    cast_member = relationship("CastMember", back_populates="alert_events")

    def __repr__(self) -> str:
        return f"<AlertEvent id={self.id} rule_id={self.alert_rule_id} at={self.triggered_at.isoformat()}>"
