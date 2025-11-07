/**
 * Episode Discussions List Page
 *
 * Route: /episode-discussions
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, CheckCircle2, Clock, Loader2, Play, Plus } from 'lucide-react';
import { Alert } from '../components/ui/alert';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Spinner } from '../components/ui/spinner';

type EpisodeDiscussion = {
  id: number;
  show: string;
  season: number;
  episode: number;
  date_utc: string;
  platform: string;
  status: string;
  total_comments_ingested: number;
  total_mentions_created: number;
  error_message: string | null;
  created_at: string;
};

export default function EpisodeDiscussionsPage() {
  const [discussions, setDiscussions] = useState<EpisodeDiscussion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDiscussions = async () => {
    try {
      const response = await fetch('/api/v1/episode-discussions?limit=100');
      if (!response.ok) {
        throw new Error('Failed to fetch episode discussions');
      }
      const data = await response.json();
      setDiscussions(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDiscussions();
  }, []);

  const getStatusBadge = (status: string) => {
    const variants: Record<
      string,
      { variant: 'default' | 'secondary' | 'destructive' | 'outline'; icon: any }
    > = {
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
      <div className="container mx-auto py-8">
        <Spinner label="Loading episode discussions..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto py-8">
        <Alert variant="error">
          <AlertCircle className="h-4 w-4" />
          {error}
        </Alert>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 max-w-6xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Episode Discussions</h1>
          <p className="text-muted-foreground">
            Manage episode transcripts and social media discussion analysis
          </p>
        </div>
        <Link to="/episode-discussions/new">
          <Button className="flex items-center gap-2">
            <Plus className="h-4 w-4" />
            Add Episode Discussion
          </Button>
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{discussions.length}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Complete</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {discussions.filter((d) => d.status === 'COMPLETE').length}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>In Progress</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {discussions.filter((d) => ['QUEUED', 'RUNNING'].includes(d.status)).length}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Drafts</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {discussions.filter((d) => d.status === 'DRAFT').length}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* List */}
      {discussions.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Play className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
            <h3 className="text-lg font-semibold mb-2">No episode discussions yet</h3>
            <p className="text-muted-foreground mb-4">
              Create your first episode discussion to start analyzing fan sentiment
            </p>
            <Link to="/episode-discussions/new">
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Add Episode Discussion
              </Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {discussions.map((discussion) => (
            <Card key={discussion.id} className="hover:bg-muted/50 transition-colors">
              <Link to={`/episode-discussions/${discussion.id}`}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <CardTitle className="text-lg">
                        {discussion.show} S{discussion.season}E{discussion.episode}
                      </CardTitle>
                      <CardDescription>
                        Aired {new Date(discussion.date_utc).toLocaleDateString()} •{' '}
                        {discussion.platform} • Created{' '}
                        {new Date(discussion.created_at).toLocaleDateString()}
                      </CardDescription>
                    </div>
                    {getStatusBadge(discussion.status)}
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-6 text-sm text-muted-foreground">
                    <div>
                      <span className="font-medium">{discussion.total_comments_ingested}</span>{' '}
                      comments
                    </div>
                    <div>
                      <span className="font-medium">{discussion.total_mentions_created}</span>{' '}
                      mentions
                    </div>
                    {discussion.error_message && (
                      <div className="flex items-center gap-1 text-destructive">
                        <AlertCircle className="h-3 w-3" />
                        Error
                      </div>
                    )}
                  </div>
                </CardContent>
              </Link>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
