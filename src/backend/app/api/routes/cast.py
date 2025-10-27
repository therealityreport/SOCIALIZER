from __future__ import annotations

import re
from typing import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api import deps
from app.models.cast import CastAlias, CastMember
from app.schemas.cast import CastMemberCreate, CastMemberRead, CastMemberUpdate
from app.services.show_names import normalize_show_name

router = APIRouter(prefix="/cast", tags=["cast"])


def _generate_slug(candidate: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", candidate.lower()).strip("-")
    return normalized or "cast-member"


def _sync_aliases(db: Session, cast_member: CastMember, aliases: list[str]) -> None:
    desired = {alias.strip(): None for alias in aliases if alias and alias.strip()}
    existing = {alias.alias: alias for alias in cast_member.aliases}

    for alias_value, alias_obj in list(existing.items()):
        if alias_value not in desired:
            cast_member.aliases.remove(alias_obj)
            db.delete(alias_obj)

    for alias_value in desired:
        if alias_value not in existing:
            cast_member.aliases.append(CastAlias(alias=alias_value))


def _to_schema(cast_member: CastMember) -> CastMemberRead:
    return CastMemberRead(
        id=cast_member.id,
        slug=cast_member.slug,
        full_name=cast_member.full_name,
        display_name=cast_member.display_name,
        show=normalize_show_name(cast_member.show),
        biography=cast_member.biography,
        is_active=cast_member.is_active,
        aliases=[alias.alias for alias in cast_member.aliases],
        created_at=cast_member.created_at,
        updated_at=cast_member.updated_at,
    )


@router.get("", response_model=list[CastMemberRead])
def list_cast(
    db: Session = Depends(deps.get_db),
    show: str | None = Query(default=None, description="Filter cast by show slug or name."),
    is_active: bool | None = Query(default=None),
) -> Sequence[CastMemberRead]:
    query = db.query(CastMember).order_by(CastMember.full_name.asc())
    if show:
        normalized_show = normalize_show_name(show)
        query = query.filter(CastMember.show == normalized_show)
    if is_active is not None:
        query = query.filter(CastMember.is_active == is_active)
    members = query.all()
    return [_to_schema(member) for member in members]


@router.get("/{cast_id}", response_model=CastMemberRead)
def get_cast(cast_id: int, db: Session = Depends(deps.get_db)) -> CastMemberRead:
    cast_member = db.get(CastMember, cast_id)
    if not cast_member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cast member not found.")
    return _to_schema(cast_member)


@router.post("", response_model=CastMemberRead, status_code=status.HTTP_201_CREATED)
def create_cast(cast_in: CastMemberCreate, db: Session = Depends(deps.get_db)) -> CastMemberRead:
    slug = _generate_slug(cast_in.slug.strip() if cast_in.slug else cast_in.full_name)
    show_value = normalize_show_name(cast_in.show)
    cast_member = CastMember(
        slug=slug,
        full_name=cast_in.full_name,
        display_name=cast_in.display_name,
        show=show_value,
        biography=cast_in.biography,
        is_active=cast_in.is_active,
    )
    if cast_in.aliases:
        cast_member.aliases = [CastAlias(alias=alias.strip()) for alias in cast_in.aliases if alias and alias.strip()]

    db.add(cast_member)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cast member with this slug already exists.") from exc
    db.refresh(cast_member)
    return _to_schema(cast_member)


@router.put("/{cast_id}", response_model=CastMemberRead)
def update_cast(cast_id: int, cast_in: CastMemberUpdate, db: Session = Depends(deps.get_db)) -> CastMemberRead:
    cast_member = db.get(CastMember, cast_id)
    if not cast_member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cast member not found.")

    update_data = cast_in.model_dump(exclude_unset=True)
    if "slug" in update_data:
        new_slug = update_data.pop("slug")
        candidate = new_slug.strip() if new_slug else cast_member.full_name
        cast_member.slug = _generate_slug(candidate)

    for field, value in update_data.items():
        if field == "aliases":
            continue
        if field == "show" and value is not None:
            setattr(cast_member, field, normalize_show_name(value))
            continue
        setattr(cast_member, field, value)

    if cast_in.aliases is not None:
        _sync_aliases(db, cast_member, cast_in.aliases)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Update violates constraints.") from exc
    db.refresh(cast_member)
    return _to_schema(cast_member)


@router.delete("/{cast_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_cast(cast_id: int, db: Session = Depends(deps.get_db)) -> Response:
    cast_member = db.get(CastMember, cast_id)
    if not cast_member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cast member not found.")
    db.delete(cast_member)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
