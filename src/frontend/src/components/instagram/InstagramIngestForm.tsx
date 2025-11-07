import { useMemo, useState } from 'react';

import { useAuth0 } from '@auth0/auth0-react';
import { Loader2, Play } from 'lucide-react';

import { ingestInstagramProfiles } from '../../lib/api/instagram';
import type { InstagramIngestRequest, InstagramIngestResponse, UsernameStats } from '../../types/instagram';
import { Alert } from '../ui/alert';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';

const TAG_RE = /^[a-z0-9_]+$/;
const USERNAME_RE = /^@?([A-Za-z0-9._]+)$/;
const SKIP_LABELS: Record<keyof UsernameStats['skipped'], string> = {
  date: 'Date range',
  inc_tag: 'Include tags',
  exc_tag: 'Exclude tags',
  likes: 'Likes threshold',
  comments: 'Comments threshold',
  private: 'Private profile',
  other: 'Other'
};

const DEFAULT_MAX_POSTS = 500;

function formatDateInput(date: Date) {
  return date.toISOString().slice(0, 10);
}

function splitTokens(value: string): string[] {
  return value
    .split(/[\s,]+/)
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function normalizeTags(value: string): string[] {
  return splitTokens(value).map((token) => token.replace(/^#/, '').toLowerCase());
}

function normalizeUsernames(value: string): { usernames: string[]; errors: string[] } {
  const usernames: string[] = [];
  const errors: string[] = [];
  for (const entry of splitTokens(value)) {
    const match = USERNAME_RE.exec(entry);
    if (!match) {
      errors.push(`Invalid username: ${entry}`);
      continue;
    }
    usernames.push(match[1]);
  }
  if (!usernames.length) {
    errors.push('At least one username is required.');
  }
  return { usernames, errors };
}

function toNumber(value: string): number | undefined {
  if (!value.trim()) {
    return undefined;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

export function InstagramIngestForm() {
  const today = useMemo(() => new Date(), []);
  const defaultStart = useMemo(() => {
    const d = new Date(today);
    d.setDate(d.getDate() - 7);
    return formatDateInput(d);
  }, [today]);
  const defaultEnd = useMemo(() => formatDateInput(today), [today]);

  const [formState, setFormState] = useState({
    usernames: '',
    startDate: defaultStart,
    endDate: defaultEnd,
    includeTags: '',
    excludeTags: '',
    minLikes: '',
    minComments: '',
    maxPostsPerUsername: String(DEFAULT_MAX_POSTS),
    includeAbout: false,
    dryRun: false
  });
  const [result, setResult] = useState<InstagramIngestResponse | null>(null);
  const [lastRunWasDryRun, setLastRunWasDryRun] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrors([]);
    setSubmitError(null);

    const validationErrors: string[] = [];
    const { usernames, errors: usernameErrors } = normalizeUsernames(formState.usernames);
    validationErrors.push(...usernameErrors);

    if (!formState.startDate || !formState.endDate) {
      validationErrors.push('Start and end dates are required.');
    } else if (formState.endDate < formState.startDate) {
      validationErrors.push('End date must be after start date.');
    }

    const includeTags = normalizeTags(formState.includeTags).filter((tag) => {
      if (!TAG_RE.test(tag)) {
        validationErrors.push(`Tags must use lowercase letters, numbers, or underscores: ${tag}`);
        return false;
      }
      return true;
    });
    const excludeTags = normalizeTags(formState.excludeTags).filter((tag) => {
      if (!TAG_RE.test(tag)) {
        validationErrors.push(`Tags must use lowercase letters, numbers, or underscores: ${tag}`);
        return false;
      }
      return true;
    });

    const minLikes = toNumber(formState.minLikes);
    const minComments = toNumber(formState.minComments);
    const maxPosts = toNumber(formState.maxPostsPerUsername) ?? DEFAULT_MAX_POSTS;
    if (maxPosts <= 0) {
      validationErrors.push('Max posts must be greater than zero.');
    }

    if (validationErrors.length) {
      setErrors(validationErrors);
      return;
    }

    const payload: InstagramIngestRequest = {
      usernames,
      startDate: formState.startDate,
      endDate: formState.endDate,
      includeTags,
      excludeTags,
      maxPostsPerUsername: maxPosts,
      includeAbout: formState.includeAbout,
      dryRun: formState.dryRun
    };
    if (typeof minLikes === 'number') {
      payload.minLikes = minLikes;
    }
    if (typeof minComments === 'number') {
      payload.minComments = minComments;
    }

    setIsSubmitting(true);
    try {
      const token = isAuthenticated ? await getAccessTokenSilently() : undefined;
      const response = await ingestInstagramProfiles(payload, token);
      setResult(response);
      setLastRunWasDryRun(formState.dryRun);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Instagram ingest failed.');
      setResult(null);
    } finally {
      setIsSubmitting(false);
    }
  }

  function onCheckboxChange(event: React.ChangeEvent<HTMLInputElement>) {
    const { name, checked } = event.target;
    setFormState((prev) => ({ ...prev, [name]: checked }));
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Instagram ingestion</CardTitle>
          <CardDescription>
            Run Apify&apos;s instagram-profile-scraper across multiple usernames, apply hashtag & engagement filters, and optionally persist
            the results.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="usernames">Usernames</Label>
                <Textarea
                  id="usernames"
                  placeholder="@BravoTV\n@AnotherAccount"
                  rows={4}
                  value={formState.usernames}
                  onChange={(event) => setFormState((prev) => ({ ...prev, usernames: event.target.value }))}
                />
                <p className="text-sm text-muted-foreground">Use commas or new lines. Add @ or bare usernames.</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="includeTags">Include hashtags</Label>
                <Textarea
                  id="includeTags"
                  placeholder="bravo, tag_two"
                  rows={4}
                  value={formState.includeTags}
                  onChange={(event) => setFormState((prev) => ({ ...prev, includeTags: event.target.value }))}
                />
                <p className="text-sm text-muted-foreground">Optional. Matching requires at least one of these tags.</p>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="excludeTags">Exclude hashtags</Label>
                <Textarea
                  id="excludeTags"
                  placeholder="spoilers"
                  rows={2}
                  value={formState.excludeTags}
                  onChange={(event) => setFormState((prev) => ({ ...prev, excludeTags: event.target.value }))}
                />
                <p className="text-sm text-muted-foreground">Optional. Posts containing these tags will be skipped.</p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="startDate">Start date</Label>
                  <Input
                    id="startDate"
                    type="date"
                    required
                    value={formState.startDate}
                    onChange={(event) => setFormState((prev) => ({ ...prev, startDate: event.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="endDate">End date</Label>
                  <Input
                    id="endDate"
                    type="date"
                    required
                    value={formState.endDate}
                    onChange={(event) => setFormState((prev) => ({ ...prev, endDate: event.target.value }))}
                  />
                </div>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="minLikes">Minimum likes</Label>
                <Input
                  id="minLikes"
                  type="number"
                  min={0}
                  placeholder="e.g. 25"
                  value={formState.minLikes}
                  onChange={(event) => setFormState((prev) => ({ ...prev, minLikes: event.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="minComments">Minimum comments</Label>
                <Input
                  id="minComments"
                  type="number"
                  min={0}
                  placeholder="e.g. 5"
                  value={formState.minComments}
                  onChange={(event) => setFormState((prev) => ({ ...prev, minComments: event.target.value }))}
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="maxPostsPerUsername">Max posts per username</Label>
                <Input
                  id="maxPostsPerUsername"
                  type="number"
                  min={1}
                  value={formState.maxPostsPerUsername}
                  onChange={(event) => setFormState((prev) => ({ ...prev, maxPostsPerUsername: event.target.value }))}
                />
                <p className="text-xs text-muted-foreground">Used after filtering. Actor still downloads each profile.</p>
              </div>
              <label className="flex items-center gap-2 text-sm font-medium text-foreground">
                <input
                  type="checkbox"
                  name="includeAbout"
                  checked={formState.includeAbout}
                  onChange={onCheckboxChange}
                />
                Include about data
              </label>
              <label className="flex items-center gap-2 text-sm font-medium text-foreground">
                <input type="checkbox" name="dryRun" checked={formState.dryRun} onChange={onCheckboxChange} />
                Dry run (no persistence)
              </label>
            </div>

            {errors.length ? (
              <Alert variant="error" title="Please fix the form">
                <ul className="list-disc space-y-1 pl-5 text-sm">
                  {errors.map((error) => (
                    <li key={error}>{error}</li>
                  ))}
                </ul>
              </Alert>
            ) : null}

            {submitError ? (
              <Alert variant="error" title="Instagram ingest failed">
                {submitError}
              </Alert>
            ) : null}

            <Button type="submit" className="inline-flex items-center gap-2" disabled={isSubmitting}>
              {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              {isSubmitting ? 'Running ingest…' : 'Run ingest'}
            </Button>
          </form>
        </CardContent>
      </Card>

      {result ? <RunSummary result={result} isDryRun={lastRunWasDryRun} /> : null}
    </div>
  );
}

function RunSummary({ result, isDryRun }: { result: InstagramIngestResponse; isDryRun: boolean }) {
  const hasResults = Object.keys(result.perUsername ?? {}).length > 0;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <CardTitle>Run status</CardTitle>
            <CardDescription>{hasResults ? 'Actor completed. Review per-username stats below.' : 'No profiles returned data.'}</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            {isDryRun ? <Badge variant="outline">Dry run</Badge> : null}
            <Badge>{result.actor.status}</Badge>
          </div>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div>
            <p className="text-sm text-muted-foreground">Run ID</p>
            <p className="font-mono text-lg">{result.actor.runId || 'n/a'}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Items kept</p>
            <p className="text-lg font-semibold">{result.itemsKept}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Started</p>
            <p>{result.actor.startedAt ? new Date(result.actor.startedAt).toLocaleString() : 'n/a'}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Finished</p>
            <p>{result.actor.finishedAt ? new Date(result.actor.finishedAt).toLocaleString() : 'n/a'}</p>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {Object.entries(result.perUsername ?? {}).map(([username, stats]) => (
          <Card key={username}>
            <CardHeader>
              <CardTitle className="text-lg">{username}</CardTitle>
              <CardDescription>Fetched {stats.fetched} posts · kept {stats.kept}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <SkipGrid stats={stats} />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function SkipGrid({ stats }: { stats: UsernameStats }) {
  return (
    <dl className="grid grid-cols-2 gap-2 text-sm">
      {(Object.keys(SKIP_LABELS) as Array<keyof UsernameStats['skipped']>).map((key) => (
        <div key={key} className="flex items-center justify-between rounded border border-border/70 px-2 py-1">
          <dt className="text-muted-foreground">{SKIP_LABELS[key]}</dt>
          <dd className="font-semibold text-foreground">{stats.skipped[key]}</dd>
        </div>
      ))}
    </dl>
  );
}
