/**
 * Episode Discussion Detail Page
 *
 * Route: /episode-discussions/:id
 */
import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { AlertCircle, CheckCircle2, Clock, Loader2 } from 'lucide-react';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Spinner } from '../components/ui/spinner';

type EpisodeDiscussion = {
  id: number;
  show: string;
  season: number;
  episode: number;
  date_utc: string;
  platform: string;
  status: string;
  summary: string | null;
  beats: Array<any> | null;
  cast_sentiment_baseline: Record<string, any> | null;
  total_comments_ingested: number;
  total_mentions_created: number;
  error_message: string | null;
};

export default function EpisodeDiscussionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [discussion, setDiscussion] = useState<EpisodeDiscussion | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;

    const fetchDiscussion = async () => {
      try {
        const response = await fetch(`/api/episode-discussions/${id}`);
        if (!response.ok) {
          throw new Error('Failed to fetch episode discussion');
        }
        const data = await response.json();
        setDiscussion(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
      } finally {
        setLoading(false);
      }
    };

    fetchDiscussion();
  }, [id]);

  const getStatusBadge = (status: string) => {
    const variants: Record<string, { variant: 'default' | 'secondary' | 'destructive' | 'outline'; icon: any }> = {
      DRAFT: { variant: 'outline', icon: <Clock className="h-3 w-3" /> },
      QUEUED: { variant: 'secondary', icon: <Clock className="h-3 w-3" /> },
      RUNNING: { variant: 'default', icon: <Loader2 className="h-3 w-3 animate-spin" /> },
      COMPLETE: { variant: 'default', icon: <CheckCircle2 className="h-3 w-3" /> },
      FAILED: { variant: 'destructive', icon: <AlertCircle className="h-3 w-3" /> },
    };

    const config = variants[status] || variants.DRAFT;
    return (
      <Badge variant={config.variant} className="flex items-center gap-1">
        {config.icon}
        {status}
      </Badge>
    );
  };

  if (loading) {
    return (
      <div className="container mx-auto py-8 flex items-center justify-center">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  if (error || !discussion) {
    return (
      <div className="container mx-auto py-8">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error || 'Episode discussion not found'}</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 max-w-6xl">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <h1 className="text-3xl font-bold">
            {discussion.show} S{discussion.season}E{discussion.episode}
          </h1>
          {getStatusBadge(discussion.status)}
        </div>
        <p className="text-muted-foreground">
          Aired {new Date(discussion.date_utc).toLocaleDateString()} • Platform: {discussion.platform}
        </p>
      </div>

      {/* Error Message */}
      {discussion.error_message && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{discussion.error_message}</AlertDescription>
        </Alert>
      )}

      {/* Tabs */}
      <Tabs defaultValue="summary" className="space-y-4">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="summary">Summary</TabsTrigger>
          <TabsTrigger value="beats">Plot Beats</TabsTrigger>
          <TabsTrigger value="cast">Cast Analysis</TabsTrigger>
          <TabsTrigger value="mentions">Mentions</TabsTrigger>
        </TabsList>

        <TabsContent value="summary" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Episode Summary</CardTitle>
              <CardDescription>AI-generated summary from transcript</CardDescription>
            </CardHeader>
            <CardContent>
              {discussion.summary ? (
                <p className="text-sm leading-relaxed">{discussion.summary}</p>
              ) : (
                <p className="text-sm text-muted-foreground italic">
                  {discussion.status === 'COMPLETE'
                    ? 'No summary available'
                    : 'Summary will be generated during analysis...'}
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="beats" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Key Plot Beats</CardTitle>
              <CardDescription>Major moments and conflicts from the episode</CardDescription>
            </CardHeader>
            <CardContent>
              {discussion.beats && discussion.beats.length > 0 ? (
                <div className="space-y-3">
                  {discussion.beats.map((beat: any, index: number) => (
                    <div key={index} className="border-l-2 border-primary pl-4 py-2">
                      <div className="flex items-center gap-2 mb-1">
                        {beat.timestamp && (
                          <Badge variant="outline" className="text-xs">
                            {beat.timestamp}
                          </Badge>
                        )}
                        {beat.cast_involved && (
                          <span className="text-xs text-muted-foreground">
                            {beat.cast_involved.join(', ')}
                          </span>
                        )}
                      </div>
                      <p className="text-sm">{beat.description}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground italic">
                  {discussion.status === 'COMPLETE'
                    ? 'No plot beats available'
                    : 'Plot beats will be generated during analysis...'}
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="cast" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Cast Sentiment Baseline</CardTitle>
              <CardDescription>Initial sentiment for each cast member from transcript</CardDescription>
            </CardHeader>
            <CardContent>
              {discussion.cast_sentiment_baseline &&
              Object.keys(discussion.cast_sentiment_baseline).length > 0 ? (
                <div className="space-y-4">
                  {Object.entries(discussion.cast_sentiment_baseline).map(([name, data]: [string, any]) => (
                    <div key={name} className="border rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-semibold">{name}</h4>
                        <Badge variant="outline">{data.sentiment}</Badge>
                      </div>
                      {data.confidence && (
                        <div className="text-xs text-muted-foreground mb-1">
                          Confidence: {(data.confidence * 100).toFixed(1)}%
                        </div>
                      )}
                      {data.notes && <p className="text-sm">{data.notes}</p>}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground italic">
                  {discussion.status === 'COMPLETE'
                    ? 'No cast sentiment data available'
                    : 'Cast sentiment will be generated during analysis...'}
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="mentions" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Discussion Mentions</CardTitle>
              <CardDescription>
                Comments ingested: {discussion.total_comments_ingested} • Mentions created:{' '}
                {discussion.total_mentions_created}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Alert>
                <AlertDescription>
                  Mention view coming soon. Check the main dashboard for aggregated sentiment.
                </AlertDescription>
              </Alert>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
