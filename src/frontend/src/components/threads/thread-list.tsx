import { Link } from 'react-router-dom';

import { CalendarClock, MessageSquare } from 'lucide-react';

import type { Thread } from '../../lib/api/types';
import { Badge } from '../ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';

type ThreadListProps = {
  threads: Thread[];
};

const statusVariantMap: Record<Thread['status'], 'positive' | 'neutral' | 'destructive'> = {
  completed: 'positive',
  live: 'positive',
  scheduled: 'neutral',
  archived: 'destructive'
};

const statusLabelMap: Record<Thread['status'], string> = {
  completed: 'Complete',
  live: 'Live',
  scheduled: 'Scheduled',
  archived: 'Archived'
};

export function ThreadList({ threads }: ThreadListProps) {
  if (!threads.length) {
    return <p className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">No threads yet. Submit one to begin analyzing sentiment.</p>;
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {threads.map((thread) => (
        <Card key={thread.id} className="flex flex-col justify-between">
          <CardHeader className="space-y-3">
            <div className="flex items-start justify-between gap-4">
              <CardTitle className="text-lg leading-tight text-foreground">{thread.title}</CardTitle>
              <Badge variant={statusVariantMap[thread.status]}>{statusLabelMap[thread.status]}</Badge>
            </div>
            <CardDescription className="flex items-center gap-3 text-xs uppercase tracking-wide text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <MessageSquare className="h-3.5 w-3.5" /> {thread.total_comments.toLocaleString()} comments
              </span>
              <span className="inline-flex items-center gap-1">
                <CalendarClock className="h-3.5 w-3.5" /> {formatDate(thread.air_time_utc ?? thread.created_utc)}
              </span>
            </CardDescription>
          </CardHeader>
          <CardContent className="flex items-center justify-between">
            <div className="text-xs text-muted-foreground">
              <p>Subreddit: {thread.subreddit ? `r/${thread.subreddit}` : 'Unknown'}</p>
              <a href={thread.url} target="_blank" rel="noreferrer" className="text-primary underline">
                View Reddit thread
              </a>
            </div>
            <Link
              to={`/threads/${thread.id}`}
              className="rounded-md border border-primary px-3 py-2 text-sm font-medium text-primary transition hover:bg-primary hover:text-primary-foreground"
            >
              View analytics
            </Link>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function formatDate(value: string | null) {
  if (!value) {
    return 'TBD';
  }
  const date = new Date(value);
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}
