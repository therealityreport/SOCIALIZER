import { Link } from 'react-router-dom';

import { ArrowUpRight, TrendingDown, TrendingUp } from 'lucide-react';

import type { CastAnalytics } from '../../lib/api/types';
import { Badge } from '../ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';

type CastGridProps = {
  threadId: number;
  cast: CastAnalytics[];
};

export function CastGrid({ threadId, cast }: CastGridProps) {
  if (!cast.length) {
    return <p className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">No cast analytics yet. Once ingestion finishes you&apos;ll see sentiment and share of voice here.</p>;
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
      {cast.map((member) => (
        <Card key={member.cast_id} className="flex flex-col justify-between">
          <CardHeader>
            <div className="flex items-center justify-between gap-4">
              <div>
                <CardTitle className="text-lg">{member.cast_slug === 'britani' ? 'Britani Bateman' : member.full_name}</CardTitle>
                <CardDescription>{normalizeShow(member.show)}</CardDescription>
              </div>
              <Badge variant={getSentimentVariant(member.overall?.net_sentiment ?? null)}>
                {formatSentiment(member.overall?.net_sentiment)}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="flex items-center justify-between rounded-lg bg-muted/60 px-3 py-2">
              <span className="font-medium text-foreground">Share of voice</span>
              <span className="text-foreground">{(member.share_of_voice * 100).toFixed(1)}%</span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-xs text-muted-foreground">
              {['live', 'day_of', 'after'].map((window) => {
                const metrics = member.time_windows[window];
                return (
                  <div key={window} className="rounded-md border border-border/60 p-2">
                    <p className="uppercase tracking-wide">{window.replace('_', ' ')}</p>
                    <p className="font-semibold text-foreground">{formatSentiment(metrics?.net_sentiment)}</p>
                    <p>{metrics?.mention_count ?? 0} mentions</p>
                  </div>
                );
              })}
            </div>
            <SentimentShift shifts={member.sentiment_shifts} />
            <Link
              to={`/threads/${threadId}/cast/${member.cast_slug}`}
              className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
            >
              Dive deeper <ArrowUpRight className="h-4 w-4" />
            </Link>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function formatSentiment(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '—';
  }
  return `${(value * 100).toFixed(1)}%`;
}

function getSentimentVariant(value: number | null) {
  if (value === null || value === undefined) {
    return 'neutral' as const;
  }
  if (value >= 0.1) {
    return 'positive' as const;
  }
  if (value <= -0.05) {
    return 'destructive' as const;
  }
  return 'neutral' as const;
}

type SentimentShiftProps = {
  shifts: Record<string, number>;
};

function SentimentShift({ shifts }: SentimentShiftProps) {
  const entries = Object.entries(shifts);
  if (!entries.length) {
    return <p className="text-xs text-muted-foreground">No notable shifts yet.</p>;
  }

  return (
    <div className="space-y-1 text-xs text-muted-foreground">
      {entries.map(([label, value]) => (
        <div key={label} className="flex items-center justify-between rounded-md border border-border/60 px-2 py-1">
          <span>{humanizeShiftLabel(label)}</span>
          <span className="flex items-center gap-1 text-foreground">
            {value >= 0 ? <TrendingUp className="h-3.5 w-3.5 text-sentiment-positive" /> : <TrendingDown className="h-3.5 w-3.5 text-sentiment-negative" />}
            {formatDelta(value)}
          </span>
        </div>
      ))}
    </div>
  );
}

function humanizeShiftLabel(label: string) {
  return label
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function formatDelta(value: number) {
  const percent = (value * 100).toFixed(1);
  return value >= 0 ? `+${percent}%` : `${percent}%`;
}

function normalizeShow(show: string) {
  if (show === 'The Real Housewives of Salt Lake City') {
    return 'RHOSLC';
  }
  return show;
}
