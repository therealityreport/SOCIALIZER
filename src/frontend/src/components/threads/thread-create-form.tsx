import { FormEvent, useEffect, useMemo, useState } from 'react';

import { CalendarDays, Link as LinkIcon, Send, Type } from 'lucide-react';

import { useCreateThread, useThreadLookup } from '../../hooks/useThreads';
import type { Thread, ThreadLookup } from '../../lib/api/types';
import { Alert } from '../ui/alert';
import { Button } from '../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Spinner } from '../ui/spinner';

type ThreadCreateFormProps = {
  onCreated?: (thread: Thread) => void;
};

type FormState = {
  url: string;
  title: string;
  subreddit: string;
  airTime: string;
  synopsis: string;
};

type TouchedState = {
  title: boolean;
  subreddit: boolean;
  airTime: boolean;
  synopsis: boolean;
};

const initialForm: FormState = { url: '', title: '', subreddit: '', airTime: '', synopsis: '' };
const initialTouched: TouchedState = { title: false, subreddit: false, airTime: false, synopsis: false };

export function ThreadCreateForm({ onCreated }: ThreadCreateFormProps) {
  const [form, setForm] = useState<FormState>(initialForm);
  const [touched, setTouched] = useState<TouchedState>(initialTouched);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [autoMeta, setAutoMeta] = useState<ThreadLookup | null>(null);

  const createThreadMutation = useCreateThread();

  const normalizedUrl = form.url.trim();
  const canLookup = useMemo(() => isValidRedditUrl(normalizedUrl), [normalizedUrl]);
  const {
    data: lookupData,
    isFetching: isLookupFetching,
    isError: isLookupError,
    error: lookupError
  } = useThreadLookup(canLookup ? normalizedUrl : undefined);

  useEffect(() => {
    if (!lookupData) {
      setAutoMeta(null);
      return;
    }
    setAutoMeta(lookupData);
    setForm((current) => ({
      ...current,
      title: touched.title ? current.title : lookupData.title ?? current.title,
      subreddit: touched.subreddit ? current.subreddit : lookupData.subreddit ?? current.subreddit,
      airTime: touched.airTime
        ? current.airTime
        : toLocalDateTimeInput(lookupData.air_time_utc ?? lookupData.created_utc ?? current.airTime),
      synopsis: touched.synopsis ? current.synopsis : lookupData.synopsis ?? current.synopsis
    }));
  }, [lookupData, touched]);

  const derivedFields = useMemo(() => parseRedditUrl(form.url), [form.url]);

  useEffect(() => {
    if (touched.subreddit || form.subreddit) {
      return;
    }
    if (derivedFields.subreddit) {
      setForm((current) => ({ ...current, subreddit: derivedFields.subreddit }));
    }
  }, [derivedFields.subreddit, form.subreddit, touched.subreddit]);

  const handleChange = (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = event.target;
    if (name === 'url') {
      setForm({ ...initialForm, url: value });
      setTouched(initialTouched);
      setAutoMeta(null);
      setStatusMessage(null);
      return;
    }
    setForm((current) => ({ ...current, [name]: value }));
    if (name in touched) {
      setTouched((current) => ({ ...current, [name]: true }));
    }
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    setStatusMessage(null);

    const redditId = autoMeta?.reddit_id || derivedFields.redditId;
    if (!redditId) {
      setStatusMessage({ type: 'error', message: 'Please provide a valid Reddit thread URL.' });
      return;
    }

    const airTimeUtc = form.airTime
      ? new Date(form.airTime).toISOString()
      : autoMeta?.air_time_utc ?? autoMeta?.created_utc ?? null;
    const createdUtc = autoMeta?.created_utc ?? new Date().toISOString();

    createThreadMutation.mutate(
      {
        reddit_id: redditId,
        subreddit: form.subreddit || autoMeta?.subreddit || derivedFields.subreddit || null,
        title: form.title || autoMeta?.title || derivedFields.fallbackTitle || redditId,
        url: autoMeta?.url ?? form.url,
        air_time_utc: airTimeUtc,
        created_utc: createdUtc,
        status: 'scheduled',
        total_comments: autoMeta?.num_comments ?? 0,
        synopsis: form.synopsis || autoMeta?.synopsis || null
      },
      {
        onSuccess: (thread) => {
          setStatusMessage({ type: 'success', message: 'Thread submitted! Aggregation will begin shortly.' });
          setForm(initialForm);
          setTouched(initialTouched);
          setAutoMeta(null);
          onCreated?.(thread);
        },
        onError: (error) => {
          setStatusMessage({ type: 'error', message: error.message });
        }
      }
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xl">
          <Send className="h-5 w-5 text-primary" />
          Track a new live thread
        </CardTitle>
        <CardDescription>Drop a Reddit discussion link and we&apos;ll ingest sentiment windows automatically.</CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={handleSubmit}>
          {statusMessage ? (
            <Alert variant={statusMessage.type === 'success' ? 'success' : 'error'}>{statusMessage.message}</Alert>
          ) : null}
          <label className="flex flex-col gap-2">
            <span className="flex items-center gap-2 text-sm font-medium text-foreground">
              <LinkIcon className="h-4 w-4" /> Thread URL
            </span>
            <input
              required
              name="url"
              type="url"
              value={form.url}
              onChange={handleChange}
              placeholder="Paste the Reddit thread URL"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
            {canLookup ? (
              <p className="text-xs text-muted-foreground">We&apos;ll pull the title, posted date, and synopsis automatically.</p>
            ) : null}
            {isLookupFetching ? (
              <Spinner label="Fetching thread details..." className="text-xs text-muted-foreground" />
            ) : null}
            {isLookupError && lookupError instanceof Error ? (
              <Alert variant="error">{lookupError.message}</Alert>
            ) : null}
            {!autoMeta && !isLookupFetching && canLookup && !isLookupError ? (
              <p className="text-xs text-muted-foreground">Unable to fetch metadata yet. We&apos;ll infer details after ingestion.</p>
            ) : null}
          </label>
          <label className="flex flex-col gap-2">
            <span className="flex items-center gap-2 text-sm font-medium text-foreground">
              <Type className="h-4 w-4" /> Episode title
            </span>
            <input
              name="title"
              type="text"
              value={form.title}
              onChange={handleChange}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="Thread title from Reddit"
            />
          </label>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-2">
              <span className="flex items-center gap-2 text-sm font-medium text-foreground">Subreddit</span>
              <input
                name="subreddit"
                type="text"
                value={form.subreddit}
                onChange={handleChange}
                placeholder="BravoRealHousewives"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </label>
            <label className="flex flex-col gap-2">
              <span className="flex items-center gap-2 text-sm font-medium text-foreground">
                <CalendarDays className="h-4 w-4" /> Air time (UTC)
              </span>
              <input
                name="airTime"
                type="datetime-local"
                value={form.airTime}
                onChange={handleChange}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </label>
          </div>
          <label className="flex flex-col gap-2">
            <span className="text-sm font-medium text-foreground">Synopsis (optional)</span>
            <textarea
              name="synopsis"
              value={form.synopsis}
              onChange={handleChange}
              rows={3}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="What producers need to watch for..."
            />
          </label>
          <div className="flex items-center justify-end gap-4">
            {autoMeta?.reddit_id || derivedFields.redditId ? (
              <p className="text-xs text-muted-foreground">
                Reddit ID detected: {autoMeta?.reddit_id ?? derivedFields.redditId}
              </p>
            ) : null}
            <Button type="submit" disabled={createThreadMutation.isPending}>
              {createThreadMutation.isPending ? (
                <Spinner label="Submitting" className="text-primary-foreground" />
              ) : (
                'Submit thread'
              )}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function parseRedditUrl(url: string) {
  try {
    const parsed = new URL(url);
    const parts = parsed.pathname.split('/').filter(Boolean);
    const commentsIndex = parts.findIndex((segment) => segment === 'comments');
    if (commentsIndex === -1 || commentsIndex + 1 >= parts.length) {
      return { redditId: '', subreddit: '', fallbackTitle: '' };
    }
    const subreddit = parts[1] ?? '';
    const redditId = parts[commentsIndex + 1] ?? '';
    const fallbackTitle = decodeURIComponent(parts[commentsIndex + 2] ?? '').replace(/_/g, ' ');
    return { redditId, subreddit, fallbackTitle };
  } catch (error) {
    return { redditId: '', subreddit: '', fallbackTitle: '' };
  }
}

function isValidRedditUrl(url: string) {
  if (!url) {
    return false;
  }
  return /reddit\.com\/r\/.+\/comments\//.test(url);
}

function toLocalDateTimeInput(value: string | null | undefined) {
  if (!value) {
    return '';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  const offset = date.getTimezoneOffset();
  const local = new Date(date.getTime() - offset * 60000);
  return local.toISOString().slice(0, 16);
}
