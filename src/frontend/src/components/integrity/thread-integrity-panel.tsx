import { useMemo } from 'react';

import { useBotReport, useBrigadingReport, useReliabilityReport } from '../../hooks/useIntegrity';
import type { BotReport, BrigadingReport, ReliabilityReport } from '../../lib/api/types';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Spinner } from '../ui/spinner';

type ThreadIntegrityPanelProps = {
  threadId: number;
};

export function ThreadIntegrityPanel({ threadId }: ThreadIntegrityPanelProps) {
  const brigadingQuery = useBrigadingReport(threadId);
  const botsQuery = useBotReport(threadId);
  const reliabilityQuery = useReliabilityReport(threadId);

  const loading = brigadingQuery.isLoading || botsQuery.isLoading || reliabilityQuery.isLoading;
  const error = brigadingQuery.error || botsQuery.error || reliabilityQuery.error;

  const entries = useMemo(() => {
    const results: Array<{ title: string; data?: BrigadingReport | BotReport | ReliabilityReport; description: string } & Partial<ScoreCardProps>> = [];
    if (brigadingQuery.data) {
      results.push({
        title: 'Brigading watchdog',
        description: 'Detects sudden participation spikes and repeat authors.',
        score: brigadingQuery.data.score,
        status: brigadingQuery.data.status,
        details: `${brigadingQuery.data.unique_authors} unique authors · ratio ${brigadingQuery.data.participation_ratio.toFixed(2)}`
      });
    }
    if (botsQuery.data) {
      results.push({
        title: 'Bot suspicion',
        description: 'Flags accounts posting high-volume short comments.',
        score: botsQuery.data.score,
        status: botsQuery.data.status,
        details: `${botsQuery.data.flagged_accounts.length} flagged of ${botsQuery.data.total_accounts} accounts`
      });
    }
    if (reliabilityQuery.data) {
      const report = reliabilityQuery.data;
      const minutes = report.minutes_since_last_poll != null ? `${Math.round(report.minutes_since_last_poll)} min since poll` : 'Polling unknown';
      results.push({
        title: 'Score reliability',
        description: 'Measures coverage vs Reddit counters and polling freshness.',
        score: report.score,
        status: report.status,
        details: `${report.ingested_comments}/${report.reported_comments} comments · ${minutes}`
      });
    }
    return results;
  }, [brigadingQuery.data, botsQuery.data, reliabilityQuery.data]);

  if (loading) {
    return <Spinner label="Assessing integrity signals..." className="p-6" />;
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Integrity signals</CardTitle>
          <CardDescription className="text-destructive">
            Unable to fetch integrity metrics: {(error as Error).message}
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Integrity signals</CardTitle>
        <CardDescription>Monitor brigading, automation, and data freshness at a glance.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 md:grid-cols-3">
        {entries.map((entry) => (
          <ScoreCard key={entry.title} title={entry.title} status={entry.status ?? 'green'} score={entry.score ?? 0} description={entry.description} details={entry.details} />
        ))}
      </CardContent>
    </Card>
  );
}

type ScoreCardProps = {
  title: string;
  description: string;
  score: number;
  status: 'green' | 'yellow' | 'red';
  details?: string;
};

function ScoreCard({ title, description, score, status, details }: ScoreCardProps) {
  const badgeClass = status === 'green' ? 'text-emerald-600' : status === 'yellow' ? 'text-amber-600' : 'text-red-600';
  return (
    <div className="rounded-lg border border-border p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <span className={`text-xs font-medium uppercase ${badgeClass}`}>{status}</span>
      </div>
      <p className="mt-2 text-3xl font-bold text-foreground">{score.toFixed(1)}</p>
      <p className="mt-1 text-xs text-muted-foreground">{description}</p>
      {details ? <p className="mt-2 text-xs text-muted-foreground">{details}</p> : null}
    </div>
  );
}
