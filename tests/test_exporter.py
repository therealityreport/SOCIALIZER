import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

pytest.importorskip("jose")

from app.db.base import Base  # type: ignore  # noqa: E402
from app.models import Aggregate, CastAlias, CastMember, Thread
from app.models.export import ExportFormat
from app.models.thread import ThreadStatus
from app.services import exporter


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", echo=False, future=True)
    from app.models import Export  # local import to avoid circulars

    Base.metadata.create_all(
        engine,
        tables=[
            Thread.__table__,
            CastMember.__table__,
            CastAlias.__table__,
            Aggregate.__table__,
            Export.__table__,
        ],
    )
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _seed_data(db: Session) -> Thread:
    thread = Thread(
        reddit_id="xyz789",
        subreddit="bravo",
        title="Cast Drama",
        url="https://reddit.com/r/bravo/xyz789",
        air_time_utc=dt.datetime(2024, 2, 1, tzinfo=dt.timezone.utc),
        created_utc=dt.datetime(2024, 2, 1, tzinfo=dt.timezone.utc),
        status=ThreadStatus.LIVE,
        total_comments=120,
    )
    cast = CastMember(slug="john-doe", full_name="John Doe", show="Bravo Show")
    db.add_all([thread, cast])
    db.flush()
    aggregate = Aggregate(
        thread_id=thread.id,
        cast_member_id=cast.id,
        time_window="overall",
        net_sentiment=0.5,
        ci_lower=0.3,
        ci_upper=0.7,
        positive_pct=0.7,
        neutral_pct=0.2,
        negative_pct=0.1,
        agreement_score=0.9,
        mention_count=40,
    )
    db.add(aggregate)
    db.commit()
    return thread


def test_create_csv_export(session: Session) -> None:
    thread = _seed_data(session)
    export = exporter.create_export(session, thread.id, ExportFormat.CSV)
    session.commit()

    assert export.format == ExportFormat.CSV
    assert export.filename.endswith(".csv")
    assert b"cast_slug" in export.content
    assert b"john-doe" in export.content


def test_create_json_export(session: Session) -> None:
    thread = _seed_data(session)
    export = exporter.create_export(session, thread.id, ExportFormat.JSON)
    session.commit()

    assert export.format == ExportFormat.JSON
    assert export.filename.endswith(".json")
    assert b"john-doe" in export.content
