import { useMemo } from 'react';

import { useThreadList } from '../hooks/useThreads';
import { Alert } from '../components/ui/alert';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Spinner } from '../components/ui/spinner';

export default function CommunitiesPage() {
  const { data: threads, isLoading, isError, error } = useThreadList();

  const grouped = useMemo(() => {
    const result = new Map<string, number>();
    if (threads) {
      for (const thread of threads) {
        const key = thread.subreddit ?? 'unknown';
        result.set(key, (result.get(key) ?? 0) + 1);
      }
    }
    return Array.from(result.entries()).sort((a, b) => b[1] - a[1]);
  }, [threads]);

  if (isLoading) {
    return <Spinner label="Compiling community activity..." className="p-6" />;
  }

  if (isError) {
    return <Alert variant="error">{error?.message ?? 'Unable to load communities.'}</Alert>;
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Communities</CardTitle>
          <CardDescription>Subreddits that Socializer is currently monitoring.</CardDescription>
        </CardHeader>
      </Card>
      {grouped.length ? (
        <div className="grid gap-4 md:grid-cols-2">
          {grouped.map(([subreddit, count]) => (
            <Card key={subreddit}>
              <CardHeader>
                <CardTitle>r/{subreddit}</CardTitle>
                <CardDescription>Tracked discussions</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold text-foreground">{count.toLocaleString()}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Alert variant="info">No communities tracked yet.</Alert>
      )}
    </div>
  );
}
