import { useMemo } from 'react';

import { useThreadList } from '../hooks/useThreads';
import { Alert } from '../components/ui/alert';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Spinner } from '../components/ui/spinner';
import { ThreadList } from '../components/threads/thread-list';
import type { Thread } from '../lib/api/types';

export default function ThreadIndex() {
  const { data: threads = [], isLoading, isError, error } = useThreadList();
  const filteredThreads = useMemo(() => threads.filter((thread) => !thread.reddit_id.startsWith('test')), [threads]);
  const latestSynced = useMemo(() => computeLatestSynced(filteredThreads), [filteredThreads]);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Episode library</CardTitle>
          <CardDescription>
            Browse every Reddit live thread we&apos;ve processed. Click through to inspect cast sentiment, export data, or queue re-runs.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-xs text-muted-foreground">
          {latestSynced ? `Latest processed thread: ${latestSynced}` : 'No threads have been processed yet.'}
        </CardContent>
      </Card>

      {isLoading ? <Spinner label="Loading threads..." /> : null}
      {isError ? <Alert variant="error">{error?.message ?? 'Unable to load threads.'}</Alert> : null}
      {!isLoading && !isError ? <ThreadList threads={filteredThreads} /> : null}
    </div>
  );
}

function computeLatestSynced(threads: Thread[]) {
  if (!threads.length) {
    return null;
  }
  const sorted = [...threads].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  const mostRecent = sorted[0];
  return `${mostRecent.title} · ${new Date(mostRecent.created_at).toLocaleString()}`;
}
