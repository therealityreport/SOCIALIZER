import { Download } from 'lucide-react';

import type { CastAnalytics, CommentListResponse, CommentMention, ThreadComment } from '../../lib/api/types';
import { cn } from '../../lib/utils';
import { Alert } from '../ui/alert';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Spinner } from '../ui/spinner';

type CommentFeedProps = {
  title?: string;
  description?: string;
  response: CommentListResponse | undefined;
  isLoading: boolean;
  error?: string | null;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  castOptions?: CastAnalytics[];
  selectedCast?: string;
  onCastChange?: (value: string) => void;
  sort?: string;
  onSortChange?: (value: string) => void;
  sortOptions?: { value: string; label: string }[];
  includeUnassignedOption?: boolean;
  emptyMessage?: string;
  filteredEmptyMessage?: string;
  onExport?: () => void;
  isExporting?: boolean;
  exportError?: string | null;
};

export function CommentFeed({
  title = 'Comment feed',
  description = 'Inspect ingested Reddit comments.',
  response,
  isLoading,
  error,
  page,
  pageSize,
  onPageChange,
  castOptions,
  selectedCast = 'all',
  onCastChange,
  sort = 'new',
  onSortChange,
  sortOptions = defaultSortOptions,
  includeUnassignedOption = false,
  emptyMessage = 'No comments have been ingested yet.',
  filteredEmptyMessage = 'No comments matched this filter.',
  onExport,
  isExporting = false,
  exportError
}: CommentFeedProps) {
  const total = response?.total ?? 0;
  const comments = response?.comments ?? [];
  const start = total ? (response?.offset ?? 0) + 1 : 0;
  const end = total ? (response?.offset ?? 0) + comments.length : 0;
  const hasPrev = page > 0;
  const hasNext = response ? response.offset + pageSize < total : false;
  const showFilter = Array.isArray(castOptions) && castOptions.length > 0 && typeof onCastChange === 'function';
  const showSort = typeof onSortChange === 'function';
  const canExport = typeof onExport === 'function';

  return (
    <Card>
      <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          {showSort ? (
            <div className="flex items-center gap-2">
              <label htmlFor="comment-feed-sort" className="text-xs uppercase tracking-wide text-muted-foreground">
                Sort
              </label>
              <select
                id="comment-feed-sort"
                value={sort}
                onChange={(event) => onSortChange(event.target.value)}
                className="rounded-md border border-border bg-background px-3 py-1 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              >
                {sortOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          {showFilter ? (
            <div className="flex items-center gap-2">
              <label htmlFor="comment-feed-filter" className="text-xs uppercase tracking-wide text-muted-foreground">
                Filter by cast
              </label>
              <select
                id="comment-feed-filter"
                value={selectedCast}
                onChange={(event) => onCastChange(event.target.value)}
                className="rounded-md border border-border bg-background px-3 py-1 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="all">All comments</option>
                {includeUnassignedOption ? <option value="unassigned">Unassigned</option> : null}
                {castOptions.map((member) => (
                  <option key={member.cast_slug} value={member.cast_slug}>
                    {member.full_name}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          {canExport ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="gap-2"
              onClick={() => {
                onExport?.();
              }}
              disabled={isExporting}
            >
              {isExporting ? (
                <>
                  <span className="inline-flex h-4 w-4 animate-spin rounded-full border-2 border-muted-foreground/40 border-t-transparent" />
                  Preparing…
                </>
              ) : (
                <>
                  <Download className="h-4 w-4 text-muted-foreground" />
                  Download CSV
                </>
              )}
            </Button>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? <Alert variant="error">{error}</Alert> : null}
        {exportError ? <Alert variant="error">{exportError}</Alert> : null}
        {isLoading ? (
          <Spinner label="Loading comments..." className="py-8" />
        ) : comments.length ? (
          <CommentList comments={comments} />
        ) : (
          <Alert variant="info">{selectedCast === 'all' ? emptyMessage : filteredEmptyMessage}</Alert>
        )}
        {total > pageSize ? (
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>
              Showing {start}-{end} of {total}
            </span>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => onPageChange(Math.max(page - 1, 0))} disabled={!hasPrev}>
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => onPageChange(hasNext ? page + 1 : page)}
                disabled={!hasNext}
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

type CommentListProps = {
  comments: ThreadComment[];
  depth?: number;
};

function CommentList({ comments, depth = 0 }: CommentListProps) {
  return (
    <div className="space-y-4">
      {comments.map((comment) => (
        <CommentCard key={comment.id} comment={comment} depth={depth} />
      ))}
    </div>
  );
}

type CommentCardProps = {
  comment: ThreadComment;
  depth?: number;
};

function CommentCard({ comment, depth = 0 }: CommentCardProps) {
  const sentimentText =
    typeof comment.sentiment_score === 'number' ? `${(comment.sentiment_score * 100).toFixed(1)}%` : undefined;
  const sentimentClues = extractSentimentClues(comment.body);
  const modelBreakdown = comment.sentiment_models ?? [];
  const combinedScore =
    typeof comment.sentiment_combined_score === 'number' ? comment.sentiment_combined_score : undefined;

  return (
    <div className="space-y-3 rounded-lg border border-border p-4" style={{ marginLeft: depth ? depth * 16 : 0 }}>
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>{formatDateTime(comment.created_utc)}</span>
        <div className="flex flex-wrap items-center gap-3">
          {comment.time_window ? <span className="uppercase tracking-wide">Window: {humanizeTimeWindow(comment.time_window)}</span> : null}
          <span>Score: {comment.score}</span>
        </div>
      </div>
      <p className="whitespace-pre-wrap text-sm text-foreground">{comment.body}</p>
      <MentionList mentions={comment.mentions} />
      <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
        <span>
          Sentiment: {comment.sentiment_label ?? 'unclassified'}
          {sentimentText ? ` (${sentimentText})` : ''}
        </span>
        {comment.is_sarcastic ? (
          <Badge variant="neutral">
            Sarcasm {comment.sarcasm_confidence ? `${(comment.sarcasm_confidence * 100).toFixed(0)}%` : ''}
          </Badge>
        ) : null}
      {comment.is_toxic ? (
        <Badge variant="destructive">
          Flagged toxicity{comment.toxicity_confidence ? ` ${(comment.toxicity_confidence * 100).toFixed(0)}%` : ''}
        </Badge>
      ) : null}
      </div>
      {sentimentClues.length ? (
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">Sentiment drivers:</span>
          {sentimentClues.map((clue) => (
            <Badge key={clue} variant="secondary">
              {clue}
            </Badge>
          ))}
        </div>
      ) : null}
      {modelBreakdown.length ? (
        <div className="space-y-2 rounded-md border border-dashed border-border p-3">
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
            <span className="font-medium text-foreground">Model breakdown</span>
            <div className="flex flex-wrap items-center gap-3 text-muted-foreground">
              {combinedScore !== undefined ? (
                <span>Combined score (sum): {combinedScore.toFixed(2)}</span>
              ) : null}
              {comment.sentiment_final_source ? (
                <span>Final source: {comment.sentiment_final_source}</span>
              ) : null}
            </div>
          </div>
          <div className="space-y-2">
            {modelBreakdown.map((model, index) => {
              const scoreText =
                typeof model.sentiment_score === 'number' ? `${(model.sentiment_score * 100).toFixed(1)}%` : undefined;
              return (
                <div key={`${model.name}-${index}`} className="text-xs text-muted-foreground">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-foreground">{model.name}</span>
                    <span className="capitalize text-foreground">{model.sentiment_label ?? 'n/a'}</span>
                    {scoreText ? <span className="text-muted-foreground">({scoreText})</span> : null}
                  </div>
                  {model.reasoning ? <p className="mt-1 text-xs text-muted-foreground">{model.reasoning}</p> : null}
                </div>
              );
            })}
          </div>
        </div>
      ) : null}
      {comment.replies.length ? <CommentList comments={comment.replies} depth={depth + 1} /> : null}
    </div>
  );
}

const defaultSortOptions = [
  { value: 'new', label: 'Latest activity' },
  { value: 'latest', label: 'Recently updated' },
  { value: 'old', label: 'Oldest' },
  { value: 'most_upvotes', label: 'Most Upvotes' },
  { value: 'most_replies', label: 'Most Replies' },
  { value: 'sentiment_desc', label: 'Highest Sentiment' },
  { value: 'sentiment_asc', label: 'Lowest Sentiment' }
];

function formatDateTime(value: string) {
  const date = new Date(value);
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

function humanizeTimeWindow(value: string) {
  return value
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

const COMMENT_STOP_WORDS = new Set([
  'the',
  'and',
  'with',
  'that',
  'have',
  'this',
  'from',
  'just',
  'about',
  'they',
  'them',
  'when',
  'what',
  'been',
  'because',
  'into',
  'your',
  'you',
  'were',
  'there',
  'their',
  'cant',
  'dont',
  'doesnt',
  'really',
  'still'
]);

function extractSentimentClues(body: string): string[] {
  const matches = body.toLowerCase().match(/[a-z']{3,}/g) ?? [];
  const counts = new Map<string, number>();
  for (const token of matches) {
    if (COMMENT_STOP_WORDS.has(token)) {
      continue;
    }
    counts.set(token, (counts.get(token) ?? 0) + 1);
  }
  const sorted = Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([token]) => token);
  return sorted;
}

type MentionListProps = {
  mentions: CommentMention[];
};

function MentionList({ mentions }: MentionListProps) {
  if (!mentions.length) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-2 text-xs">
      {mentions.map((mention) => {
        const label = mention.sentiment_label?.toLowerCase();
        const score = typeof mention.sentiment_score === 'number' ? `${Math.round(mention.sentiment_score * 100)}%` : null;
        return (
          <Badge
            key={`${mention.cast_slug}-${mention.cast_name}`}
            variant="outline"
            className={cn(
              'border-border text-muted-foreground',
              label === 'positive' && 'border-emerald-400 bg-emerald-50 text-emerald-700',
              label === 'negative' && 'border-rose-400 bg-rose-50 text-rose-700'
            )}
          >
            <span className="font-medium text-foreground">{mention.cast_name}</span>
            {label ? <span className="ml-2 capitalize">{label}</span> : null}
            {score ? <span className="ml-1 text-xs text-muted-foreground">({score})</span> : null}
          </Badge>
        );
      })}
    </div>
  );
}
