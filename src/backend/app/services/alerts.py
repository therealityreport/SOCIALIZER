from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import Aggregate, AlertEvent, AlertRule
from app.services.notifications import SendGridEmailNotifier, SlackNotifier

logger = logging.getLogger(__name__)


class AlertConfigurationError(RuntimeError):
    """Raised when an alert rule configuration is invalid."""


@dataclass(frozen=True)
class MetricSnapshot:
    cast_member_id: int
    time_window: str
    net_sentiment: float | None
    mention_count: int | None


class AlertEvaluationService:
    """Evaluate alert rules for a given thread using precomputed aggregates."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def evaluate_thread(self, thread_id: int) -> list[AlertEvent]:
        rules = self._load_active_rules(thread_id)
        if not rules:
            return []

        metrics = self._collect_metrics(thread_id)
        triggered: list[AlertEvent] = []

        for rule in rules:
            try:
                payload = self._evaluate_rule(rule, metrics)
            except AlertConfigurationError as exc:
                logger.warning("Skipping alert rule %s due to configuration error: %s", rule.id, exc)
                continue
            if payload is None:
                continue
            if self._is_duplicate(rule.id, payload):
                continue

            event = AlertEvent(
                alert_rule_id=rule.id,
                thread_id=thread_id,
                cast_member_id=payload.get("cast_member_id"),
                payload=payload,
                delivered_channels=[],
            )
            self._session.add(event)
            triggered.append(event)

        return triggered

    def _load_active_rules(self, thread_id: int) -> list[AlertRule]:
        stmt: Select[tuple[AlertRule]] = (
            select(AlertRule)
            .where(AlertRule.is_active.is_(True))
            .where((AlertRule.thread_id == thread_id) | (AlertRule.thread_id.is_(None)))
        )
        return list(self._session.execute(stmt).scalars())

    def _collect_metrics(self, thread_id: int) -> dict[tuple[int, str], MetricSnapshot]:
        stmt: Select[tuple[Aggregate]] = select(Aggregate).where(Aggregate.thread_id == thread_id)
        snapshots: dict[tuple[int, str], MetricSnapshot] = {}
        for aggregate in self._session.execute(stmt).scalars():
            key = (aggregate.cast_member_id, aggregate.time_window)
            snapshots[key] = MetricSnapshot(
                cast_member_id=aggregate.cast_member_id,
                time_window=aggregate.time_window,
                net_sentiment=aggregate.net_sentiment,
                mention_count=aggregate.mention_count,
            )
        return snapshots

    def _evaluate_rule(
        self,
        rule: AlertRule,
        metrics: dict[tuple[int, str], MetricSnapshot],
    ) -> dict[str, Any] | None:
        rule_type = rule.rule_type
        if rule_type != "sentiment_drop":
            raise AlertConfigurationError(f"Unsupported rule type: {rule_type}")

        condition = dict(rule.condition or {})
        metric_name = condition.get("metric", "net_sentiment")
        comparison = condition.get("comparison", "lte")
        threshold_raw = condition.get("threshold")
        window = condition.get("window")
        baseline_window = condition.get("baseline_window")
        override_cast = condition.get("cast_member_id")

        if threshold_raw is None or window is None:
            raise AlertConfigurationError("Sentiment drop rule requires 'threshold' and 'window'")

        try:
            threshold = float(threshold_raw)
        except (TypeError, ValueError):
            raise AlertConfigurationError("Threshold must be numeric") from None

        cast_member_id = override_cast or rule.cast_member_id
        if cast_member_id is None:
            raise AlertConfigurationError("Sentiment drop rule requires cast_member_id")

        snapshot = metrics.get((cast_member_id, window))
        if not snapshot:
            return None

        value = self._extract_metric(snapshot, metric_name)
        if value is None:
            return None

        payload: dict[str, Any] = {
            "rule_type": rule_type,
            "metric": metric_name,
            "window": window,
            "cast_member_id": cast_member_id,
            "threshold": threshold,
            "value": value,
        }

        if baseline_window:
            baseline_snapshot = metrics.get((cast_member_id, baseline_window))
            if not baseline_snapshot:
                return None
            baseline_value = self._extract_metric(baseline_snapshot, metric_name)
            if baseline_value is None:
                return None
            delta = value - baseline_value
            payload["baseline_window"] = baseline_window
            payload["baseline_value"] = baseline_value
            payload["delta"] = delta
            comparator = _COMPARISONS.get(comparison) or _COMPARISONS["lte"]
            triggered = comparator(delta, threshold)
        else:
            comparator = _COMPARISONS.get(comparison)
            if comparator is None:
                raise AlertConfigurationError(f"Unsupported comparison operator: {comparison}")
            triggered = comparator(value, threshold)

        return payload if triggered else None

    def _extract_metric(self, snapshot: MetricSnapshot, metric_name: str) -> float | None:
        if metric_name == "net_sentiment":
            return snapshot.net_sentiment
        if metric_name == "mention_count":
            if snapshot.mention_count is None:
                return None
            return float(snapshot.mention_count)
        raise AlertConfigurationError(f"Unsupported metric: {metric_name}")

    def _is_duplicate(self, alert_rule_id: int, payload: dict[str, Any]) -> bool:
        stmt: Select[tuple[AlertEvent]] = (
            select(AlertEvent)
            .where(AlertEvent.alert_rule_id == alert_rule_id)
            .order_by(AlertEvent.triggered_at.desc())
            .limit(1)
        )
        last_event = self._session.execute(stmt).scalars().first()
        if not last_event:
            return False

        last_payload = last_event.payload or {}
        keys_to_compare = ("window", "metric", "cast_member_id", "value", "delta")
        for key in keys_to_compare:
            if last_payload.get(key) != payload.get(key):
                return False
        return True


class AlertDeliveryService:
    """Dispatch alert events to downstream channels (Slack, email, etc.)."""

    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        slack_notifier: SlackNotifier | None = None,
        email_notifier: SendGridEmailNotifier | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._slack = slack_notifier or SlackNotifier(self._settings.slack_webhook_url)
        self._email = email_notifier or SendGridEmailNotifier(
            api_key=self._settings.sendgrid_api_key,
            from_email=self._settings.sendgrid_from_email,
            from_name=self._settings.sendgrid_from_name,
        )

    def deliver(self, event: AlertEvent) -> list[str]:
        rule = event.rule
        if rule is None:
            logger.warning("Alert event %s has no associated rule; skipping delivery.", event.id)
            return []

        delivered_channels: list[str] = []
        summary = self._format_summary(event)
        channels = [channel.lower() for channel in (rule.channels or [])]

        if "slack" in channels:
            if self._slack.send(summary["slack_text"], blocks=summary["slack_blocks"]):
                delivered_channels.append("slack")

        if "email" in channels:
            recipients = self._resolve_email_recipients(rule)
            if self._email.send(recipients, summary["email_subject"], summary["email_html"], summary["email_plain"]):
                delivered_channels.append("email")

        if delivered_channels:
            existing = event.delivered_channels or []
            event.delivered_channels = sorted({*existing, *delivered_channels})

        return delivered_channels

    def _resolve_email_recipients(self, rule: AlertRule) -> list[str]:
        condition = rule.condition or {}
        recipients = condition.get("emails")
        if isinstance(recipients, list):
            return [str(email).strip() for email in recipients if str(email).strip()]
        if isinstance(recipients, str):
            return [email.strip() for email in recipients.split(",") if email.strip()]
        fallback = self._settings.sendgrid_from_email
        return [fallback] if fallback else []

    def _format_summary(self, event: AlertEvent) -> dict[str, str | list[dict[str, object]]]:
        payload = event.payload or {}
        rule = event.rule
        cast_name = event.cast_member.full_name if event.cast_member else "All cast"
        window = payload.get("window", "overall")
        metric = payload.get("metric", "net_sentiment")
        value = payload.get("value")
        threshold = payload.get("threshold")
        delta = payload.get("delta")
        baseline = payload.get("baseline_window")
        thread_title = event.thread.title if event.thread else "Thread"

        metric_label = metric.replace("_", " ").title()
        subject = f"Alert: {cast_name} {metric_label} change on '{thread_title}'"

        lines = [
            f"Thread: {thread_title}",
            f"Cast Member: {cast_name}",
            f"Window: {window}",
            f"Metric: {metric_label}",
            f"Value: {value}",
            f"Threshold: {threshold}",
        ]
        if baseline is not None and delta is not None:
            lines.append(f"Baseline ({baseline}): {payload.get('baseline_value')}")
            lines.append(f"Delta vs baseline: {delta:+}")

        plain = "\n" + "\n".join(lines)
        html = "<br/>".join(lines)

        slack_text = f"{subject}\n" + "\n".join(lines)
        slack_blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{subject}*\nWindow `{window}` exceeded threshold `{threshold}` with value `{value}`.",
                },
            }
        ]

        return {
            "email_subject": subject,
            "email_html": html,
            "email_plain": plain,
            "slack_text": slack_text,
            "slack_blocks": slack_blocks,
        }

def _less_than(value: float, threshold: float) -> bool:
    return value < threshold


def _less_than_or_equal(value: float, threshold: float) -> bool:
    return value <= threshold


def _greater_than(value: float, threshold: float) -> bool:
    return value > threshold


def _greater_than_or_equal(value: float, threshold: float) -> bool:
    return value >= threshold


_COMPARISONS: dict[str, Any] = {
    "lt": _less_than,
    "lte": _less_than_or_equal,
    "gt": _greater_than,
    "gte": _greater_than_or_equal,
}
