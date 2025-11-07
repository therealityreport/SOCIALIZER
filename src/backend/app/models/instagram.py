from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin


class InstagramProfile(TimestampMixin, Base):
    __tablename__ = "instagram_profiles"

    username: Mapped[str] = mapped_column(String(128), primary_key=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(300))
    biography: Mapped[Optional[str]] = mapped_column(Text)
    followers_count: Mapped[Optional[int]] = mapped_column(Integer)
    follows_count: Mapped[Optional[int]] = mapped_column(Integer)
    posts_count: Mapped[Optional[int]] = mapped_column(Integer)
    external_url: Mapped[Optional[str]] = mapped_column(String(500))
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    about_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=dict
    )

    posts: Mapped[list["InstagramPost"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class InstagramPost(Base):
    __tablename__ = "instagram_posts"

    shortcode: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(128), ForeignKey("instagram_profiles.username"), nullable=False)
    caption: Mapped[Optional[str]] = mapped_column(Text)
    posted_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    media_type: Mapped[Optional[str]] = mapped_column(String(32))
    product_type: Mapped[Optional[str]] = mapped_column(String(32))
    url: Mapped[Optional[str]] = mapped_column(String(500))
    comments_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    likes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    raw_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    inserted_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    profile: Mapped[InstagramProfile] = relationship(back_populates="posts")
    hashtags: Mapped[list["InstagramPostHashtag"]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class InstagramPostHashtag(Base):
    __tablename__ = "instagram_post_hashtags"

    post_shortcode: Mapped[str] = mapped_column(
        String(64), ForeignKey("instagram_posts.shortcode", ondelete="CASCADE"), primary_key=True
    )
    tag: Mapped[str] = mapped_column(String(64), primary_key=True)

    post: Mapped[InstagramPost] = relationship(back_populates="hashtags")


class InstagramRun(Base):
    __tablename__ = "instagram_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_run_id: Mapped[Optional[str]] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    input_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    stats_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
