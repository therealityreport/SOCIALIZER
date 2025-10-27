import type { AlertEvent } from '../../lib/api/types';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';

type AlertHistoryProps = {
  events: AlertEvent[];
};

export function AlertHistory({ events }: AlertHistoryProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent alert deliveries</CardTitle>
        <CardDescription>Quickly review which rules triggered and where notifications were sent.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {events.length === 0 ? <p className="text-sm text-muted-foreground">No alerts have fired yet.</p> : null}
        {events.map((event) => {
          const channels = event.delivered_channels.join(', ') || 'not delivered';
          const metric = String(event.payload.metric ?? 'net_sentiment');
          const value = event.payload.value ?? '—';
          return (
            <div key={event.id} className="rounded-lg border border-border p-3 text-sm">
              <div className="flex items-center justify-between">
                <p className="font-medium text-foreground">Rule #{event.alert_rule_id}</p>
                <span className="text-xs text-muted-foreground">{formatRelativeTime(event.triggered_at)}</span>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                Metric <strong>{metric}</strong> measured <strong>{String(value)}</strong> in window
                <strong> {String(event.payload.window ?? 'overall')}</strong>.
              </div>
              <div className="mt-1 text-xs text-muted-foreground">Channels: {channels}</div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

function formatRelativeTime(dateIso: string): string {
  const then = new Date(dateIso).getTime();
  const now = Date.now();
  const diffMs = now - then;
  const diffMinutes = Math.round(diffMs / 60000);

  if (Number.isNaN(diffMinutes)) {
    return 'just now';
  }

  if (diffMinutes <= 1) {
    return 'just now';
  }
  if (diffMinutes < 60) {
    return `${diffMinutes} minutes ago`;
  }
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours} hours ago`;
  }
  const diffDays = Math.round(diffHours / 24);
  return `${diffDays} days ago`;
}
