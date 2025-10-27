import { useMemo } from 'react';

import { useCastRoster } from '../hooks/useCastRoster';
import { useThreadList } from '../hooks/useThreads';
import { Alert } from '../components/ui/alert';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Spinner } from '../components/ui/spinner';
import { canonicalizeShowName, displayShowName } from '../lib/showNames';

export default function ShowsPage() {
  const { data: roster, isLoading: rosterLoading, isError: rosterError, error: rosterErrorMessage } = useCastRoster();
  const { data: threads, isLoading: threadsLoading, isError: threadsError, error: threadsErrorMessage } = useThreadList();

  const grouped = useMemo(() => {
    const result = new Map<string, { cast: number; episodes: number }>();
    if (roster) {
      for (const member of roster) {
        const key = canonicalizeShowName(member.show);
        const entry = result.get(key) ?? { cast: 0, episodes: 0 };
        entry.cast += 1;
        result.set(key, entry);
      }
    }
    if (threads) {
      for (const thread of threads) {
        const [rawShow] = thread.title.split('-');
        const key = canonicalizeShowName(rawShow?.trim() ?? thread.title);
        const entry = result.get(key) ?? { cast: 0, episodes: 0 };
        entry.episodes += 1;
        result.set(key, entry);
      }
    }
    return Array.from(result.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [roster, threads]);

  if (rosterLoading || threadsLoading) {
    return <Spinner label="Loading show analytics..." className="p-6" />;
  }

  if (rosterError) {
    return <Alert variant="error">{rosterErrorMessage?.message ?? 'Unable to load cast roster.'}</Alert>;
  }

  if (threadsError) {
    return <Alert variant="error">{threadsErrorMessage instanceof Error ? threadsErrorMessage.message : 'Unable to load episodes.'}</Alert>;
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Shows</CardTitle>
          <CardDescription>Snapshot of tracked shows and coverage.</CardDescription>
        </CardHeader>
      </Card>
      {grouped.length ? (
        <div className="grid gap-4 md:grid-cols-3">
          {grouped.map(([showKey, data]) => (
            <Card key={showKey || 'unknown-show'}>
              <CardHeader>
                <CardTitle>{displayShowName(showKey) || 'Unknown Show'}</CardTitle>
                <CardDescription>Tracked within Socializer</CardDescription>
              </CardHeader>
              <CardContent className="flex items-center justify-between text-sm text-muted-foreground">
                <div>
                  <p className="text-xs uppercase tracking-wide">Cast members</p>
                  <p className="text-xl font-semibold text-foreground">{data.cast.toLocaleString()}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide">Episodes</p>
                  <p className="text-xl font-semibold text-foreground">{data.episodes.toLocaleString()}</p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Alert variant="info">No shows detected yet. Add cast members to populate this view.</Alert>
      )}
    </div>
  );
}
