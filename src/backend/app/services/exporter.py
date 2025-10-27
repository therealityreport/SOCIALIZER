from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Export, ExportFormat, Thread
from app.services.analytics import get_thread_cast_analytics
from app.schemas.analytics import ThreadCastAnalyticsResponse


def _generate_csv_payload(analytics: ThreadCastAnalyticsResponse) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "cast_slug",
            "cast_name",
            "show",
            "time_window",
            "mention_count",
            "share_of_voice",
            "net_sentiment",
            "ci_lower",
            "ci_upper",
            "positive_pct",
            "neutral_pct",
            "negative_pct",
            "agreement_score",
        ]
    )

    for cast in analytics.cast:
        base_row = [cast.cast_slug, cast.full_name, cast.show]
        if cast.overall:
            writer.writerow(
                base_row
                + [
                    "overall",
                    cast.overall.mention_count,
                    f"{cast.share_of_voice:.6f}",
                    cast.overall.net_sentiment,
                    cast.overall.ci_lower,
                    cast.overall.ci_upper,
                    cast.overall.positive_pct,
                    cast.overall.neutral_pct,
                    cast.overall.negative_pct,
                    cast.overall.agreement_score,
                ]
            )
        for window, metrics in cast.time_windows.items():
            writer.writerow(
                base_row
                + [
                    window,
                    metrics.mention_count,
                    f"{cast.share_of_voice:.6f}",
                    metrics.net_sentiment,
                    metrics.ci_lower,
                    metrics.ci_upper,
                    metrics.positive_pct,
                    metrics.neutral_pct,
                    metrics.negative_pct,
                    metrics.agreement_score,
                ]
            )

    return output.getvalue().encode("utf-8")


def _generate_json_payload(analytics: ThreadCastAnalyticsResponse) -> bytes:
    payload = analytics.model_dump(mode="json")
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def create_export(session: Session, thread_id: int, export_format: ExportFormat) -> Export:
    analytics = get_thread_cast_analytics(session, thread_id)

    if export_format == ExportFormat.CSV:
        content = _generate_csv_payload(analytics)
        extension = "csv"
    elif export_format == ExportFormat.JSON:
        content = _generate_json_payload(analytics)
        extension = "json"
    else:  # pragma: no cover - safeguard for future formats
        raise ValueError(f"Unsupported export format: {export_format}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"thread-{analytics.thread.id}-{timestamp}.{extension}"

    export = Export(
        thread_id=analytics.thread.id,
        format=export_format,
        filename=filename,
        content=content,
    )
    session.add(export)
    session.flush()
    session.refresh(export)
    return export


def get_export(session: Session, export_id: int) -> Export | None:
    return session.get(Export, export_id)
