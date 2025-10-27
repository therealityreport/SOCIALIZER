from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.aggregate import Aggregate
    from app.models.alert import AlertEvent, AlertRule
    from app.models.mention import Mention


class CastMember(TimestampMixin, Base):
    __tablename__ = "cast_members"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_cast_members_slug"),
        Index("ix_cast_members_show", "show"),
        Index("ix_cast_members_is_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(120))
    show: Mapped[str] = mapped_column(String(120), nullable=False)
    biography: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    aliases: Mapped[list["CastAlias"]] = relationship(
        back_populates="cast_member",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    mentions: Mapped[list["Mention"]] = relationship(back_populates="cast_member")
    aggregates: Mapped[list["Aggregate"]] = relationship(back_populates="cast_member")
    alert_rules: Mapped[list["AlertRule"]] = relationship(back_populates="cast_member")
    alert_events: Mapped[list["AlertEvent"]] = relationship(back_populates="cast_member")

    def __repr__(self) -> str:
        return f"<CastMember id={self.id} slug={self.slug!r}>"


class CastAlias(TimestampMixin, Base):
    __tablename__ = "cast_member_aliases"
    __table_args__ = (
        UniqueConstraint("cast_member_id", "alias", name="uq_cast_member_alias"),
        Index("ix_cast_alias_alias", "alias"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cast_member_id: Mapped[int] = mapped_column(ForeignKey("cast_members.id", ondelete="CASCADE"), nullable=False)
    alias: Mapped[str] = mapped_column(String(120), nullable=False)

    cast_member: Mapped["CastMember"] = relationship(back_populates="aliases")

    def __repr__(self) -> str:
        return f"<CastAlias id={self.id} alias={self.alias!r}>"
