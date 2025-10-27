import { Image, Link as LinkIcon, PlusCircle, Video } from 'lucide-react';

import type { ThreadInsights } from '../../lib/api/types';
import { Alert } from '../ui/alert';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Spinner } from '../ui/spinner';

type ThreadDiscussionInsightsProps = {
  insights?: ThreadInsights;
  isLoading: boolean;
  error?: string | null;
  onAddCast?: (name: string) => void;
  isAdding?: boolean;
};

export function ThreadDiscussionInsights({
  insights,
  isLoading,
  error,
  onAddCast,
  isAdding
}: ThreadDiscussionInsightsProps) {
  if (isLoading) {
    return <Spinner label="Analyzing recent conversation..." className="py-6" />;
  }

  if (error) {
    return <Alert variant="error">{error}</Alert>;
  }

  if (!insights) {
    return null;
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Emoji analytics</CardTitle>
          <CardDescription>Most used emoji reactions in this discussion.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          {insights.emojis.length ? (
            insights.emojis.map((emoji) => (
              <Badge key={emoji.emoji} variant="outline" className="text-lg leading-none">
                <span className="mr-2">{emoji.emoji}</span>
                <span className="text-xs text-muted-foreground">{emoji.count.toLocaleString()}</span>
              </Badge>
            ))
          ) : (
            <Alert variant="info">No emoji usage detected yet.</Alert>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Hot topics</CardTitle>
          <CardDescription>Words and phrases dominating the conversation.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {insights.hot_topics.length ? (
            insights.hot_topics.map((topic) => (
              <Badge key={topic.term} variant="secondary">
                #{topic.term} <span className="ml-1 text-xs text-muted-foreground">{topic.count}</span>
              </Badge>
            ))
          ) : (
            <Alert variant="info">Not enough chatter to surface trending topics.</Alert>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Names spotted</CardTitle>
          <CardDescription>
            People mentioned in the thread. Add new faces to the cast roster to start tracking their sentiment.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {insights.names.length ? (
            insights.names.map((name) => (
              <div key={name.name} className="flex items-center justify-between rounded-md border border-border px-3 py-2">
                <div>
                  <p className="text-sm font-medium text-foreground">{name.name}</p>
                  <p className="text-xs text-muted-foreground">
                    Mentioned {name.count.toLocaleString()} time{name.count === 1 ? '' : 's'}
                    {name.is_cast ? ' · Already on the cast roster' : ' · Not tracked'}
                  </p>
                </div>
                {!name.is_cast && onAddCast ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onAddCast(name.name)}
                    disabled={isAdding}
                    className="gap-2"
                  >
                    <PlusCircle className="h-4 w-4" />
                    Add to cast
                  </Button>
                ) : null}
              </div>
            ))
          ) : (
            <Alert variant="info">No distinct names surfaced yet.</Alert>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Media gallery</CardTitle>
          <CardDescription>Links, GIFs, and media dropped in the thread.</CardDescription>
        </CardHeader>
        <CardContent>
          {insights.media.length ? (
            <div className="grid gap-4 md:grid-cols-3">
              {insights.media.map((item) => (
                <MediaPreview key={`${item.comment_id}-${item.url}`} url={item.url} type={item.media_type} />
              ))}
            </div>
          ) : (
            <Alert variant="info">No media shared yet.</Alert>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

type MediaPreviewProps = {
  url: string;
  type: 'image' | 'gif' | 'video' | 'link';
};

function MediaPreview({ url, type }: MediaPreviewProps) {
  const icon =
    type === 'video' ? <Video className="h-4 w-4 text-primary" /> : type === 'link' ? <LinkIcon className="h-4 w-4 text-primary" /> : <Image className="h-4 w-4 text-primary" />;

  const preview =
    type === 'image' || type === 'gif' ? (
      <img src={url} alt="" className="h-40 w-full rounded-md object-cover" loading="lazy" />
    ) : (
      <div className="flex h-40 w-full items-center justify-center rounded-md border border-dashed border-border bg-muted/40 text-sm text-muted-foreground">
        Preview unavailable
      </div>
    );

  return (
    <div className="space-y-2">
      {preview}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted-foreground">
          {icon}
          <span>{type}</span>
        </div>
        <a href={url} target="_blank" rel="noreferrer" className="text-xs text-primary underline">
          Open link
        </a>
      </div>
    </div>
  );
}
