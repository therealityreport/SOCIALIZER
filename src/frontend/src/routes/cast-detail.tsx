import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { BookOpen, MessageSquare, RefreshCcw, TrendingDown, TrendingUp } from 'lucide-react';

import { useCastAnalytics, useCastHistory } from '../hooks/useAnalytics';
import { useThread, useThreadComments } from '../hooks/useThreads';
import { Alert } from '../components/ui/alert';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Spinner } from '../components/ui/spinner';
import { CommentFeed } from '../components/comments/comment-feed';
import type { CastHistoryEntry } from '../lib/api/types';

const PAGE_SIZE = 5;
const COMMENT_PAGE_SIZE = 25;

export default function CastDetail() {
  const params = useParams<{ threadId: string; castSlug: string }>();
  const threadId = params.threadId ? Number.parseInt(params.threadId, 10) : NaN;
  const castSlug = params.castSlug;

  const {
    data: thread,
    refetch: refreshThread,
    isFetching: isThreadFetching
  } = useThread(Number.isNaN(threadId) ? undefined : threadId);
  const {
    data: analytics,
    isLoading: isAnalyticsLoading,
    isError: isAnalyticsError,
    error: analyticsError,
    refetch: refreshAnalytics,
    isFetching: isAnalyticsFetching
  } = useCastAnalytics(Number.isNaN(threadId) ? undefined : threadId, castSlug);
  const {
    data: history,
    isLoading: isHistoryLoading,
    isError: isHistoryError,
    error: historyError,
    refetch: refreshHistory,
    isFetching: isHistoryFetching
  } = useCastHistory(castSlug);

  const [page, setPage] = useState(0);
  const [commentPage, setCommentPage] = useState(0);
  const [selectedSort, setSelectedSort] = useState('new');
  const {
    data: commentFeed,
    isLoading: isCommentsLoading,
    isError: isCommentsError,
    error: commentsError,
    refetch: refreshComments,
    isFetching: isCommentsFetching
  } = useThreadComments(Number.isNaN(threadId) ? undefined : threadId, {
    castSlug,
    limit: COMMENT_PAGE_SIZE,
    offset: commentPage * COMMENT_PAGE_SIZE,
    sort: selectedSort
  });

  const isRefreshing = isThreadFetching || isAnalyticsFetching || isHistoryFetching || isCommentsFetching;

  if (Number.isNaN(threadId) || !castSlug) {
    return <Alert variant="error">Invalid cast route.</Alert>;
  }

  if (isAnalyticsLoading || isHistoryLoading) {
    return <Spinner label="Loading cast analytics..." className="p-6" />;
  }

  if (isAnalyticsError) {
    return <Alert variant="error" title="Unable to load cast analytics">{analyticsError?.message ?? 'Cast analytics failed.'}</Alert>;
  }

  if (isHistoryError) {
    return <Alert variant="error" title="Unable to load history">{historyError?.message ?? 'Cast history failed.'}</Alert>;
  }

  if (!analytics || !history) {
    return <Alert variant="info">No analytics captured for this cast yet.</Alert>;
  }

  const paginatedHistory = paginateHistory(history.history, page);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="space-y-1">
            <CardTitle className="text-2xl text-foreground">{analytics.full_name}</CardTitle>
            <CardDescription>
              Appearing in {thread ? thread.title : 'thread'} · {analytics.show}
            </CardDescription>
          </div>
          <div className="flex items-center gap-3">
            <Badge variant={pickSentimentBadge(analytics.overall?.net_sentiment ?? null)}>
              Overall sentiment {formatSentiment(analytics.overall?.net_sentiment)}
            </Badge>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="gap-2"
              onClick={() => {
                void Promise.allSettled([refreshThread(), refreshAnalytics(), refreshHistory(), refreshComments()]);
              }}
              disabled={isAnalyticsLoading || isHistoryLoading || isCommentsLoading || isRefreshing}
            >
              <RefreshCcw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              Refresh comments
            </Button>
          </div>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <Metric label="Mentions" value={(analytics.overall?.mention_count ?? 0).toLocaleString()} icon={MessageSquare} />
          <Metric label="Share of voice" value={`${(analytics.share_of_voice * 100).toFixed(1)}%`} icon={BookOpen} />
          <Metric label="Positive %" value={formatSentiment(analytics.overall?.positive_pct)} icon={TrendingUp} />
          <Metric label="Negative %" value={formatSentiment(analytics.overall?.negative_pct)} icon={TrendingDown} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Time window comparison</CardTitle>
          <CardDescription>Live vs Day-Of vs After airing benchmark.</CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {['live', 'day_of', 'after'].map((window) => {
            const metrics = analytics.time_windows[window];
            return (
              <div key={window} className="rounded-lg border border-border p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">{window.replace('_', ' ')}</p>
                <p className="text-2xl font-semibold text-foreground">{formatSentiment(metrics?.net_sentiment)}</p>
                <p className="text-xs text-muted-foreground">{metrics?.mention_count ?? 0} mentions</p>
              </div>
            );
          })}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Historical sentiment</CardTitle>
          <CardDescription>How this cast performed across other monitored episodes.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {history.history.length ? (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="px-3 py-2">Thread</th>
                    <th className="px-3 py-2">Sentiment</th>
                    <th className="px-3 py-2">Mentions</th>
                    <th className="px-3 py-2">Live</th>
                    <th className="px-3 py-2">Day-Of</th>
                    <th className="px-3 py-2">After</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {paginatedHistory.entries.map((entry) => (
                    <tr key={entry.thread.id}>
                      <td className="px-3 py-2">
                        <Link to={`/threads/${entry.thread.id}`} className="text-primary hover:underline">
                          {entry.thread.title}
                        </Link>
                      </td>
                      <td className="px-3 py-2">{formatSentiment(entry.overall?.net_sentiment)}</td>
                      <td className="px-3 py-2">{entry.overall?.mention_count ?? 0}</td>
                      <td className="px-3 py-2">{formatSentiment(entry.time_windows.live?.net_sentiment)}</td>
                      <td className="px-3 py-2">{formatSentiment(entry.time_windows.day_of?.net_sentiment)}</td>
                      <td className="px-3 py-2">{formatSentiment(entry.time_windows.after?.net_sentiment)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Alert variant="info">No history yet for this cast.</Alert>
          )}
          {history.history.length > PAGE_SIZE ? (
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>
                Showing {paginatedHistory.offset + 1}-{paginatedHistory.offset + paginatedHistory.entries.length} of {history.history.length}
              </span>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={() => setPage((prev) => Math.max(prev - 1, 0))} disabled={page === 0}>
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((prev) => (prev + 1) * PAGE_SIZE < history.history.length ? prev + 1 : prev)}
                  disabled={(page + 1) * PAGE_SIZE >= history.history.length}
                >
                  Next
                </Button>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <CommentFeed
        title="Comment feed"
        description="All Reddit comments that mention this cast member in the selected thread."
        response={commentFeed}
        isLoading={isCommentsLoading}
        error={isCommentsError ? commentsError?.message ?? 'Unable to load comments.' : null}
        page={commentPage}
        onPageChange={setCommentPage}
        pageSize={COMMENT_PAGE_SIZE}
        sort={selectedSort}
        onSortChange={(value) => {
          setSelectedSort(value);
          setCommentPage(0);
        }}
        emptyMessage="No mentions recorded for this cast member yet."
      />
    </div>
  );
}

type MetricProps = {
  label: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
};

function Metric({ label, value, icon: Icon }: MetricProps) {
  return (
    <div className="rounded-lg border border-border p-4">
      <div className="flex items-center justify-between text-xs uppercase tracking-wide text-muted-foreground">
        <span>{label}</span>
        <Icon className="h-4 w-4 text-primary" />
      </div>
      <p className="mt-2 text-xl font-semibold text-foreground">{value}</p>
    </div>
  );
}

function paginateHistory(entries: CastHistoryEntry[], page: number) {
  const offset = page * PAGE_SIZE;
  return {
    offset,
    entries: entries.slice(offset, offset + PAGE_SIZE)
  };
}

function pickSentimentBadge(value: number | null) {
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

function formatSentiment(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '—';
  }
  return `${(value * 100).toFixed(1)}%`;
}
