import { useCallback } from 'react';

import { useAuth0 } from '@auth0/auth0-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createThread,
  downloadThreadCommentsCsv,
  getThread,
  getThreadComments,
  getThreadInsights,
  listThreads,
  lookupThreadMetadata,
  reanalyzeThread
} from '../lib/api/threads';
import type { CommentListResponse, Thread, ThreadCreateRequest, ThreadInsights, ThreadLookup } from '../lib/api/types';

const THREADS_KEY = ['threads'] as const;
const THREAD_COMMENTS_KEY = ['thread-comments'] as const;
const THREAD_INSIGHTS_KEY = ['thread-insights'] as const;
const THREAD_LOOKUP_KEY = ['thread-lookup'] as const;

async function resolveToken(isAuthenticated: boolean, getToken: () => Promise<string>) {
  if (!isAuthenticated) {
    return undefined;
  }
  return getToken();
}

export function useThreadList() {
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();

  const queryFn = useCallback(async () => {
    const token = await resolveToken(isAuthenticated, getAccessTokenSilently);
    return listThreads(token);
  }, [getAccessTokenSilently, isAuthenticated]);

  return useQuery({ queryKey: THREADS_KEY, queryFn });
}

export function useThread(threadId: number | undefined) {
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();

  return useQuery({
    queryKey: [...THREADS_KEY, threadId],
    enabled: Boolean(threadId),
    queryFn: async () => {
      if (!threadId) {
        throw new Error('Thread id is required');
      }
      const token = await resolveToken(isAuthenticated, getAccessTokenSilently);
      return getThread(threadId, token);
    }
  });
}

export function useCreateThread() {
  const queryClient = useQueryClient();
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();

  return useMutation({
    mutationFn: async (payload: ThreadCreateRequest) => {
      const token = await resolveToken(isAuthenticated, getAccessTokenSilently);
      return createThread(payload, token);
    },
    onSuccess: async (thread: Thread) => {
      await queryClient.invalidateQueries({ queryKey: THREADS_KEY });
      await queryClient.invalidateQueries({ queryKey: [...THREADS_KEY, thread.id] });
    }
  });
}

type CommentParams = {
  castSlug?: string;
  limit?: number;
  offset?: number;
  sort?: string;
};

export function useThreadComments(threadId: number | undefined, params: CommentParams) {
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();

  return useQuery<CommentListResponse>({
    queryKey: [
      ...THREAD_COMMENTS_KEY,
      threadId ?? 'unknown',
      params.castSlug ?? 'all',
      params.limit ?? 50,
      params.offset ?? 0,
      params.sort ?? 'new',
      params.unassignedOnly ?? false
    ],
    enabled: Boolean(threadId),
    queryFn: async () => {
      if (!threadId) {
        throw new Error('Thread id is required');
      }
      const token = await resolveToken(isAuthenticated, getAccessTokenSilently);
      return getThreadComments(threadId, params, token);
    }
  });
}

export function useThreadInsights(threadId: number | undefined) {
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();

  return useQuery<ThreadInsights>({
    queryKey: [...THREAD_INSIGHTS_KEY, threadId ?? 'unknown'],
    enabled: Boolean(threadId),
    queryFn: async () => {
      if (!threadId) {
        throw new Error('Thread id is required');
      }
      const token = await resolveToken(isAuthenticated, getAccessTokenSilently);
      return getThreadInsights(threadId, token);
    }
  });
}

export function useReanalyzeThread(threadId: number | undefined) {
  const queryClient = useQueryClient();
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();

  return useMutation({
    mutationFn: async () => {
      if (!threadId) {
        throw new Error('Thread id is required');
      }
      const token = await resolveToken(isAuthenticated, getAccessTokenSilently);
      await reanalyzeThread(threadId, token);
    },
    onSuccess: async () => {
      if (!threadId) {
        return;
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: [...THREAD_COMMENTS_KEY, threadId] }),
        queryClient.invalidateQueries({ queryKey: [...THREAD_INSIGHTS_KEY, threadId] }),
        queryClient.invalidateQueries({ queryKey: [...THREADS_KEY, threadId] })
      ]);
    }
  });
}

export function useThreadLookup(url: string | undefined) {
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();

  return useQuery<ThreadLookup>({
    queryKey: [...THREAD_LOOKUP_KEY, url ?? 'missing'],
    enabled: Boolean(url),
    queryFn: async () => {
      if (!url) {
        throw new Error('Thread url is required');
      }
      const token = await resolveToken(isAuthenticated, getAccessTokenSilently);
      return lookupThreadMetadata(url, token);
    },
    staleTime: 5 * 60 * 1000
  });
}

export function useThreadCommentsExport(threadId: number | undefined) {
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();

  return useMutation({
    mutationFn: async () => {
      if (!threadId) {
        throw new Error('Thread id is required');
      }
      const token = await resolveToken(isAuthenticated, getAccessTokenSilently);
      return downloadThreadCommentsCsv(threadId, token);
    }
  });
}
