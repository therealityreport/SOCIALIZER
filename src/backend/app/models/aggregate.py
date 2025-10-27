from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.cast import CastMember
    from app.models.thread import Thread


class Aggregate(TimestampMixin, Base):
    __tablename__ = "aggregates"
    __table_args__ = (
        Index("ix_aggregates_thread_cast", "thread_id", "cast_member_id"),
        Index("ix_aggregates_time_window", "time_window"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    cast_member_id: Mapped[int] = mapped_column(ForeignKey("cast_members.id", ondelete="CASCADE"), nullable=False)
    time_window: Mapped[str] = mapped_column(String(32), nullable=False)
    net_sentiment: Mapped[Optional[float]] = mapped_column(Float)
    ci_lower: Mapped[Optional[float]] = mapped_column(Float)
    ci_upper: Mapped[Optional[float]] = mapped_column(Float)
    positive_pct: Mapped[Optional[float]] = mapped_column(Float)
    neutral_pct: Mapped[Optional[float]] = mapped_column(Float)
    negative_pct: Mapped[Optional[float]] = mapped_column(Float)
    agreement_score: Mapped[Optional[float]] = mapped_column(Float)
    mention_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    thread: Mapped["Thread"] = relationship(back_populates="aggregates")
    cast_member: Mapped["CastMember"] = relationship(back_populates="aggregates")

    def __repr__(self) -> str:
        return f"<Aggregate id={self.id} thread_id={self.thread_id} cast_member_id={self.cast_member_id}>"
