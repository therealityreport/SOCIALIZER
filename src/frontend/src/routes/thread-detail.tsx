import { useMemo, useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';

import { Gauge, MessageSquare, Users2, RefreshCcw } from 'lucide-react';

import { useThread, useThreadComments, useThreadInsights, useReanalyzeThread } from '../hooks/useThreads';
import type { CastAnalytics } from '../lib/api/types';
import { useThreadCastAnalytics } from '../hooks/useAnalytics';
import { useAlertHistory } from '../hooks/useAlerts';
import { useCastRosterMutations } from '../hooks/useCastRoster';
import { Alert } from '../components/ui/alert';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Spinner } from '../components/ui/spinner';
import { CastGrid } from '../components/cast/cast-grid';
import { ExportPanel } from '../components/threads/export-panel';
import { ThreadDiscussionInsights } from '../components/threads/thread-discussion-insights';
import { AddCastMemberDialog } from '../components/cast/add-cast-member-dialog';
import { AlertHistory } from '../components/alerts/alert-history';
import { ThreadIntegrityPanel } from '../components/integrity/thread-integrity-panel';
import { CommentFeed } from '../components/comments/comment-feed';

const COMMENTS_PAGE_SIZE = 25;

export default function ThreadDetail() {
  const params = useParams<{ threadId: string }>();
  const threadId = params.threadId ? Number.parseInt(params.threadId, 10) : NaN;

  const {
    data: thread,
    isLoading: isThreadLoading,
    isError: isThreadError,
    error: threadError,
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
  } = useThreadCastAnalytics(Number.isNaN(threadId) ? undefined : threadId);
  const {
    data: alertHistory,
    isLoading: isHistoryLoading,
    isError: isHistoryError,
    error: historyError,
    refetch: refreshAlertHistory,
    isFetching: isHistoryFetching
  } = useAlertHistory(Number.isNaN(threadId) ? undefined : threadId, 10);

  const [selectedCast, setSelectedCast] = useState<string>('all');
  const [selectedSort, setSelectedSort] = useState<string>('new');
  const [castSort, setCastSort] = useState<'sentiment_desc' | 'sentiment_asc'>('sentiment_desc');
  const [commentPage, setCommentPage] = useState(0);
  const {
    data: commentFeed,
    isLoading: isCommentsLoading,
    isError: isCommentsError,
    error: commentsError,
    refetch: refreshComments,
    isFetching: isCommentsFetching
  } = useThreadComments(Number.isNaN(threadId) ? undefined : threadId, {
    castSlug: selectedCast === 'all' || selectedCast === 'unassigned' ? undefined : selectedCast,
    limit: COMMENTS_PAGE_SIZE,
    offset: commentPage * COMMENTS_PAGE_SIZE,
    sort: selectedSort,
    unassignedOnly: selectedCast === 'unassigned'
  });
  const {
    data: insights,
    isLoading: isInsightsLoading,
    error: insightsError,
    refetch: refreshInsights
  } = useThreadInsights(Number.isNaN(threadId) ? undefined : threadId);
  const reanalyzeMutation = useReanalyzeThread(Number.isNaN(threadId) ? undefined : threadId);
  const { createMutation: createCastMutation } = useCastRosterMutations();
  const [pendingCastName, setPendingCastName] = useState<string | null>(null);
  const [castError, setCastError] = useState<string | null>(null);
  const [analysisMessage, setAnalysisMessage] = useState<string | null>(null);

  const isLoading = isThreadLoading || isAnalyticsLoading || isHistoryLoading || (isInsightsLoading && !insights);
  const isRefreshing =
    isThreadFetching ||
    isAnalyticsFetching ||
    isHistoryFetching ||
    isCommentsFetching ||
    isInsightsLoading ||
    reanalyzeMutation.isPending;
  const castData = analytics?.cast ?? [];
  const sortedCast = useMemo(() => sortCastMembers(castData, castSort), [castData, castSort]);
  const summary = useMemo(() => computeSummary(sortedCast), [sortedCast]);
  const insightsErrorMessage = insightsError instanceof Error ? insightsError.message : null;
  const defaultShow = analytics?.cast[0]?.show ?? 'RHOSLC';

  useEffect(() => {
    if (!analysisMessage) {
      return;
    }
    const timer = window.setTimeout(() => setAnalysisMessage(null), 6000);
    return () => window.clearTimeout(timer);
  }, [analysisMessage]);

  const handleRefresh = async () => {
    if (Number.isNaN(threadId)) {
      return;
    }
    setAnalysisMessage('Re-running analytics and sentiment links...');
    try {
      await reanalyzeMutation.mutateAsync();
      setAnalysisMessage('Re-analysis queued. Data will update as soon as processing finishes.');
    } catch (error) {
      setAnalysisMessage(error instanceof Error ? error.message : 'Failed to queue re-analysis.');
    }
    await Promise.allSettled([
      refreshThread(),
      refreshAnalytics(),
      refreshAlertHistory(),
      refreshComments(),
      refreshInsights()
    ]);
  };

  const handleAddCast = (name: string) => {
    setCastError(null);
    setPendingCastName(name);
  };

  const handleSubmitCast = async (payload: { full_name: string; display_name: string; show: string }) => {
    try {
      await createCastMutation.mutateAsync({
        full_name: payload.full_name,
        display_name: payload.display_name,
        show: payload.show,
        aliases: []
      });
      setPendingCastName(null);
      setCastError(null);
      setAnalysisMessage(`Added ${payload.full_name}. Updating analytics...`);
      await reanalyzeMutation.mutateAsync();
      await Promise.allSettled([refreshAnalytics(), refreshInsights()]);
    } catch (error) {
      setCastError(error instanceof Error ? error.message : 'Failed to add cast member.');
    }
  };

  if (Number.isNaN(threadId)) {
    return <Alert variant="error">Invalid thread identifier.</Alert>;
  }

  if (isLoading) {
    return <Spinner label="Loading episode analytics..." className="p-6" />;
  }

  if (isThreadError) {
    return <Alert variant="error" title="Unable to load thread">{threadError?.message ?? 'Thread fetch failed'}</Alert>;
  }

  if (isAnalyticsError) {
    return <Alert variant="error" title="Unable to load analytics">{analyticsError?.message ?? 'Analytics fetch failed'}</Alert>;
  }

  if (isHistoryError) {
    return <Alert variant="error" title="Unable to load alerts">{historyError?.message ?? 'Alert history fetch failed'}</Alert>;
  }

  if (!thread || !analytics) {
    return <Alert variant="info">No analytics available for this thread yet.</Alert>;
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <CardTitle className="text-2xl text-foreground">{thread.title}</CardTitle>
          <div className="flex flex-col items-start gap-3 md:flex-row md:items-center md:gap-4">
            <CardDescription>
              r/{thread.subreddit ?? 'Unknown'} · Air time {formatDate(thread.air_time_utc ?? thread.created_utc)} · Status {thread.status.toUpperCase()}
            </CardDescription>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="gap-2"
              onClick={() => {
                void handleRefresh();
              }}
              disabled={isLoading || isRefreshing}
            >
              <RefreshCcw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              Refresh analytics
            </Button>
          </div>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-6 text-sm text-muted-foreground">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Reddit URL</p>
            <a href={thread.url} target="_blank" rel="noreferrer" className="text-primary underline">
              {thread.url}
            </a>
          </div>
          {thread.synopsis ? (
            <div className="max-w-xl">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Synopsis</p>
              <p className="text-foreground">{thread.synopsis}</p>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
        <MetricCard
          title="Total mentions"
          icon={MessageSquare}
          value={analytics.total_mentions.toLocaleString()}
          description="Across all cast windows"
        />
        <MetricCard
          title="Overall sentiment"
          icon={Gauge}
          value={summary.weightedSentiment != null ? `${(summary.weightedSentiment * 100).toFixed(1)}%` : '—'}
          description="Weighted by mention count"
        />
        <MetricCard
          title="Cast tracked"
          icon={Users2}
          value={analytics.cast.length.toString()}
          description="Members with analytics this thread"
        />
        <MetricCard
          title="Total comments"
          icon={MessageSquare}
          value={thread.total_comments.toLocaleString()}
          description="Fetched from Reddit"
        />
      </div>

      <TimeWindowSummary summary={summary.windows} />

      <CastSortControls castSort={castSort} onChange={setCastSort} />
      <CastGrid threadId={thread.id} cast={sortedCast} />

      {analysisMessage ? <Alert variant="info">{analysisMessage}</Alert> : null}

      <ThreadDiscussionInsights
        insights={insights}
        isLoading={Boolean(isInsightsLoading && !insights)}
        error={insightsErrorMessage}
        onAddCast={handleAddCast}
        isAdding={createCastMutation.isPending}
      />

      <CommentFeed
        response={commentFeed}
        isLoading={isCommentsLoading}
        error={isCommentsError ? commentsError?.message ?? 'Unable to load comments.' : null}
        page={commentPage}
        onPageChange={setCommentPage}
        pageSize={COMMENTS_PAGE_SIZE}
        castOptions={sortedCast}
        selectedCast={selectedCast}
        onCastChange={(value) => {
          setSelectedCast(value);
          setCommentPage(0);
        }}
        sort={selectedSort}
        onSortChange={(value) => {
          setSelectedSort(value);
          setCommentPage(0);
        }}
        includeUnassignedOption
        filteredEmptyMessage={selectedCast === 'unassigned' ? 'No unassigned comments yet.' : 'No comments matched this cast filter.'}
        description="Inspect individual Reddit comments or narrow the feed to a specific cast member."
      />

      <ExportPanel threadId={thread.id} />

      <div className="grid gap-4 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <AlertHistory events={alertHistory ?? []} />
        </div>
        <div className="lg:col-span-2">
          <ThreadIntegrityPanel threadId={thread.id} />
        </div>
      </div>

      <AddCastMemberDialog
        isOpen={Boolean(pendingCastName)}
        initialName={pendingCastName ?? ''}
        defaultShow={defaultShow}
        isSubmitting={createCastMutation.isPending}
        errorMessage={castError}
        onClose={() => {
          if (!createCastMutation.isPending) {
            setPendingCastName(null);
            setCastError(null);
          }
        }}
        onSubmit={handleSubmitCast}
      />
    </div>
  );
}

type MetricCardProps = {
  title: string;
  value: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
};

function MetricCard({ title, value, description, icon: Icon }: MetricCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle className="text-base text-foreground">{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </div>
        <Icon className="h-5 w-5 text-primary" />
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-semibold text-foreground">{value}</p>
      </CardContent>
    </Card>
  );
}

type CastSortControlsProps = {
  castSort: 'sentiment_desc' | 'sentiment_asc';
  onChange: (value: 'sentiment_desc' | 'sentiment_asc') => void;
};

function CastSortControls({ castSort, onChange }: CastSortControlsProps) {
  return (
    <div className="flex items-center justify-end">
      <label htmlFor="cast-sort" className="mr-2 text-xs uppercase tracking-wide text-muted-foreground">
        Sort cast by sentiment
      </label>
      <select
        id="cast-sort"
        value={castSort}
        onChange={(event) => onChange(event.target.value as 'sentiment_desc' | 'sentiment_asc')}
        className="rounded-md border border-border bg-background px-3 py-1 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
      >
        <option value="sentiment_desc">Highest → lowest</option>
        <option value="sentiment_asc">Lowest → highest</option>
      </select>
    </div>
  );
}


type TimeWindowSummaryProps = {
  summary: Record<string, { mentions: number; sentiment: number | null }>;
};

function TimeWindowSummary({ summary }: TimeWindowSummaryProps) {
  const windows = Object.entries(summary);
  if (!windows.length) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Time window summary</CardTitle>
          <CardDescription>We&apos;ll populate windows once ingestion completes.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Time window summary</CardTitle>
        <CardDescription>Compare Live vs Day-Of vs After airing windows.</CardDescription>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {windows.map(([window, data]) => (
          <div key={window} className="rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">{window.replace('_', ' ')}</p>
            <p className="text-2xl font-semibold text-foreground">{data.sentiment != null ? `${(data.sentiment * 100).toFixed(1)}%` : '—'}</p>
            <p className="text-xs text-muted-foreground">{data.mentions.toLocaleString()} mentions</p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function computeSummary(cast: CastAnalytics[]) {
  let totalMentions = 0;
  let sentimentAccumulator = 0;
  let sentimentWeight = 0;
  const windowMap: Record<string, { mentions: number; sentimentSum: number; sentimentWeight: number }> = {};

  for (const member of cast) {
    if (member.overall?.mention_count) {
      totalMentions += member.overall.mention_count;
      if (typeof member.overall.net_sentiment === 'number') {
        sentimentAccumulator += member.overall.net_sentiment * member.overall.mention_count;
        sentimentWeight += member.overall.mention_count;
      }
    }

    for (const [window, metrics] of Object.entries(member.time_windows)) {
      const bucket = windowMap[window] ?? { mentions: 0, sentimentSum: 0, sentimentWeight: 0 };
      bucket.mentions += metrics.mention_count ?? 0;
      if (typeof metrics.net_sentiment === 'number' && metrics.mention_count) {
        bucket.sentimentSum += metrics.net_sentiment * metrics.mention_count;
        bucket.sentimentWeight += metrics.mention_count;
      }
      windowMap[window] = bucket;
    }
  }

  const windows: Record<string, { mentions: number; sentiment: number | null }> = {};
  for (const [window, data] of Object.entries(windowMap)) {
    windows[window] = {
      mentions: data.mentions,
      sentiment: data.sentimentWeight ? data.sentimentSum / data.sentimentWeight : null
    };
  }

  const weightedSentiment = sentimentWeight ? sentimentAccumulator / sentimentWeight : null;

  return { totalMentions, weightedSentiment, windows };
}

function sortCastMembers(cast: CastAnalytics[], mode: 'sentiment_desc' | 'sentiment_asc') {
  const safeSentiment = (member: CastAnalytics, direction: 'asc' | 'desc') => {
    const value = member.overall?.net_sentiment;
    if (value == null) {
      return direction === 'asc' ? Number.POSITIVE_INFINITY : Number.NEGATIVE_INFINITY;
    }
    return value;
  };

  if (mode === 'sentiment_asc') {
    return [...cast].sort((a, b) => safeSentiment(a, 'asc') - safeSentiment(b, 'asc'));
  }
  return [...cast].sort((a, b) => safeSentiment(b, 'desc') - safeSentiment(a, 'desc'));
}

function formatDate(value: string | null) {
  if (!value) {
    return 'TBD';
  }
  const date = new Date(value);
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}
