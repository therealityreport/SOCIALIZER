import { useMemo, useEffect, useState } from 'react';

import { useThreadList } from '../hooks/useThreads';
import { Alert } from '../components/ui/alert';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Spinner } from '../components/ui/spinner';
import { ThreadList } from '../components/threads/thread-list';
import type { Thread } from '../lib/api/types';

type EpisodeDiscussion = {
  id: number;
  show: string;
  season: number;
  episode: number;
  date_utc: string;
  platform: string;
  status: string;
  created_at: string;
  transcript_text?: string;
  links?: string[];
};

export default function ThreadIndex() {
  const { data: threads = [], isLoading: threadsLoading, isError: threadsError, error: threadsErrorMsg } = useThreadList();
  const [episodeDiscussions, setEpisodeDiscussions] = useState<EpisodeDiscussion[]>([]);
  const [discussionsLoading, setDiscussionsLoading] = useState(true);
  const [discussionsError, setDiscussionsError] = useState<string | null>(null);

  useEffect(() => {
    const fetchEpisodeDiscussions = async () => {
      try {
        const response = await fetch('/api/v1/episode-discussions?limit=100');
        if (!response.ok) throw new Error('Failed to fetch episode discussions');
        const data = await response.json();
        setEpisodeDiscussions(data);
      } catch (err) {
        setDiscussionsError(err instanceof Error ? err.message : 'Error loading discussions');
      } finally {
        setDiscussionsLoading(false);
      }
    };
    fetchEpisodeDiscussions();
  }, []);

  // Convert episode discussions to thread-like format
  const discussionThreads: Thread[] = useMemo(() => {
    return episodeDiscussions.map((disc) => ({
      id: disc.id * 10000, // Offset IDs to avoid conflicts
      reddit_id: `episode_${disc.id}`,
      title: `${disc.show} S${disc.season}E${disc.episode}`,
      url: disc.links?.[0] || '',
      subreddit: disc.platform,
      total_comments: 0,
      status: disc.status === 'COMPLETE' ? 'complete' : disc.status.toLowerCase(),
      created_at: disc.created_at,
      synced_at: disc.created_at,
      is_episode_discussion: true,
    } as Thread));
  }, [episodeDiscussions]);

  const allThreads = useMemo(() => [...threads, ...discussionThreads], [threads, discussionThreads]);
  const filteredThreads = useMemo(() => allThreads.filter((thread) => !thread.reddit_id.startsWith('test')), [allThreads]);
  const latestSynced = useMemo(() => computeLatestSynced(filteredThreads), [filteredThreads]);

  const isLoading = threadsLoading || discussionsLoading;
  const isError = threadsError || discussionsError !== null;
  const error = threadsErrorMsg || discussionsError;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>All Threads</CardTitle>
          <CardDescription>
            Browse live threads and episode discussions. Click through to inspect cast sentiment, export data, or queue re-runs.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="text-xs text-muted-foreground">
            {latestSynced ? `Latest processed: ${latestSynced}` : 'No threads yet.'}
          </div>
          <div className="flex gap-4 text-xs text-muted-foreground">
            <div>Live Threads: <span className="font-medium">{threads.length}</span></div>
            <div>Episode Discussions: <span className="font-medium">{episodeDiscussions.length}</span></div>
            <div>Total: <span className="font-medium">{filteredThreads.length}</span></div>
          </div>
        </CardContent>
      </Card>

      {isLoading ? <Spinner label="Loading threads..." /> : null}
      {isError ? <Alert variant="error">{error ?? 'Unable to load threads.'}</Alert> : null}
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
