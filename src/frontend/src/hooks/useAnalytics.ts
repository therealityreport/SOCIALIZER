import { useCallback } from 'react';

import { useAuth0 } from '@auth0/auth0-react';
import { useQuery } from '@tanstack/react-query';

import { getCastHistory, getThreadCastAnalytics, getThreadCastMember } from '../lib/api/analytics';

export function useThreadCastAnalytics(threadId: number | undefined) {
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();

  const queryFn = useCallback(async () => {
    if (!threadId) {
      throw new Error('threadId is required');
    }
    const token = isAuthenticated ? await getAccessTokenSilently() : undefined;
    return getThreadCastAnalytics(threadId, token);
  }, [getAccessTokenSilently, isAuthenticated, threadId]);

  return useQuery({
    queryKey: ['thread-cast-analytics', threadId],
    enabled: Boolean(threadId),
    queryFn
  });
}

export function useCastAnalytics(threadId: number | undefined, castSlug: string | undefined) {
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();

  const queryFn = useCallback(async () => {
    if (!threadId || !castSlug) {
      throw new Error('threadId and castSlug are required');
    }
    const token = isAuthenticated ? await getAccessTokenSilently() : undefined;
    return getThreadCastMember(threadId, castSlug, token);
  }, [castSlug, getAccessTokenSilently, isAuthenticated, threadId]);

  return useQuery({
    queryKey: ['cast-analytics', threadId, castSlug],
    enabled: Boolean(threadId && castSlug),
    queryFn
  });
}

export function useCastHistory(castSlug: string | undefined) {
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();

  const queryFn = useCallback(async () => {
    if (!castSlug) {
      throw new Error('castSlug is required');
    }
    const token = isAuthenticated ? await getAccessTokenSilently() : undefined;
    return getCastHistory(castSlug, token);
  }, [castSlug, getAccessTokenSilently, isAuthenticated]);

  return useQuery({
    queryKey: ['cast-history', castSlug],
    enabled: Boolean(castSlug),
    queryFn
  });
}
