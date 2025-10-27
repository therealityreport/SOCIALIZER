import { useEffect, useMemo, useState } from 'react';

import { Activity, Radio, MessageCircle, RefreshCcw } from 'lucide-react';

import { useThreadComments, useThreadList } from '../hooks/useThreads';
import { Alert } from '../components/ui/alert';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Spinner } from '../components/ui/spinner';
import { ThreadCreateForm } from '../components/threads/thread-create-form';
import { ThreadList } from '../components/threads/thread-list';
import type { Thread, CommentListResponse } from '../lib/api/types';

export default function Dashboard() {
  const { data: threads = [], isLoading, isError, error } = useThreadList();
  const [selectedThreadId, setSelectedThreadId] = useState<number | undefined>(undefined);
  const [page, setPage] = useState(0);

  useEffect(() => {
    if (!threads.length) {
      setSelectedThreadId(undefined);
      return;
    }
    const exists = selectedThreadId ? threads.some((thread) => thread.id === selectedThreadId) : false;
    if (!selectedThreadId || !exists) {
      setSelectedThreadId(threads[0].id);
      setPage(0);
    }
  }, [threads, selectedThreadId]);

  const {
    data: unassignedFeed,
    isLoading: isUnassignedLoading,
    isError: isUnassignedError,
    error: unassignedError,
    refetch: refreshUnassignedFeed,
    isFetching: isUnassignedFetching
  } = useThreadComments(selectedThreadId, {
    limit: 10,
    offset: page * 10,
    sort: 'new',
    unassignedOnly: true
  });

  const stats = useMemo(() => computeDashboardMetrics(threads), [threads]);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <MetricCard
          title="Threads tracked"
          description="Total live threads monitored"
          value={stats.totalThreads.toString()}
          icon={Radio}
        />
        <MetricCard
          title="Comments processed"
          description="Reddit comments ingested across threads"
          value={stats.totalComments.toLocaleString()}
          icon={MessageCircle}
        />
        <MetricCard
          title="Live right now"
          description="Threads currently marked live"
          value={stats.liveThreads.toString()}
          icon={Activity}
        />
      </div>

      <ThreadCreateForm />

      {isLoading ? <Spinner label="Loading tracked threads..." /> : null}
      {isError ? <Alert variant="error">{error?.message ?? 'Unable to fetch threads.'}</Alert> : null}
      {!isLoading && !isError ? <ThreadList threads={threads} /> : null}

      <UnassignedCommentPanel
        threads={threads}
        selectedThreadId={selectedThreadId}
        onSelectThread={(id) => {
          setSelectedThreadId(id);
          setPage(0);
        }}
        feed={unassignedFeed}
        isLoading={isUnassignedLoading}
        isError={isUnassignedError}
        error={unassignedError?.message}
        page={page}
        onPageChange={setPage}
        onRefresh={refreshUnassignedFeed}
        isFetching={isUnassignedFetching}
      />
    </div>
  );
}

type MetricCardProps = {
  title: string;
  description: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
};

function MetricCard({ title, description, value, icon: Icon }: MetricCardProps) {
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
        <p className="text-3xl font-semibold text-foreground">{value}</p>
      </CardContent>
    </Card>
  );
}

function computeDashboardMetrics(threads: Thread[]) {
  const totalThreads = threads.length;
  const totalComments = threads.reduce((acc, thread) => acc + (thread?.total_comments ?? 0), 0);
  const liveThreads = threads.filter((thread) => thread?.status === 'live').length;
  return { totalThreads, totalComments, liveThreads };
}

type UnassignedCommentPanelProps = {
  threads: Thread[];
  selectedThreadId: number | undefined;
  onSelectThread: (id: number) => void;
  feed: CommentListResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  error?: string;
  page: number;
  onPageChange: (page: number) => void;
  onRefresh: () => Promise<unknown>;
  isFetching: boolean;
};

function UnassignedCommentPanel({
  threads,
  selectedThreadId,
  onSelectThread,
  feed,
  isLoading,
  isError,
  error,
  page,
  onPageChange,
  onRefresh,
  isFetching
}: UnassignedCommentPanelProps) {
  if (!threads.length) {
    return null;
  }

  return (
    <Card>
      <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <CardTitle>Unassigned comments</CardTitle>
          <CardDescription>Comments without a cast match. Review aliases or tag manually.</CardDescription>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2">
            <label htmlFor="unassigned-thread" className="text-xs uppercase tracking-wide text-muted-foreground">
              Thread
            </label>
            <select
              id="unassigned-thread"
              value={selectedThreadId ?? ''}
              onChange={(event) => {
                const value = event.target.value;
                if (!value) {
                  return;
                }
                onSelectThread(Number.parseInt(value, 10));
              }}
              className="rounded-md border border-border bg-background px-3 py-1 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            >
              {threads.map((thread) => (
                <option key={thread.id} value={thread.id}>
                  {thread.title}
                </option>
              ))}
            </select>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              void onRefresh();
            }}
            disabled={isLoading || isFetching}
            className="gap-1"
          >
            <RefreshCcw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? <Spinner label="Loading unassigned comments..." /> : null}
        {isError ? <Alert variant="error">{error ?? 'Unable to load unassigned comments.'}</Alert> : null}
        {!isLoading && !isError ? (
          feed && feed.comments.length ? (
            <div className="space-y-4">
              {feed.comments.map((comment) => (
                <div key={comment.id} className="space-y-2 rounded-lg border border-border p-4">
                  <div className="text-xs text-muted-foreground">
                    {new Date(comment.created_utc).toLocaleString()} · Score {comment.score}
                  </div>
                  <p className="text-sm text-foreground whitespace-pre-wrap">{comment.body}</p>
                </div>
              ))}
            </div>
          ) : (
            <Alert variant="info">No unassigned comments for this thread.</Alert>
          )
        ) : null}
        {feed && feed.total > feed.limit ? (
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>
              Showing {feed.offset + 1}-{feed.offset + feed.comments.length} of {feed.total}
            </span>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => onPageChange(Math.max(page - 1, 0))} disabled={page === 0}>
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => onPageChange((page + 1) * feed.limit < feed.total ? page + 1 : page)}
                disabled={(page + 1) * feed.limit >= feed.total}
              >
                Next
              </Button>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
