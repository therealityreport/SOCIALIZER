import { useAuth0 } from '@auth0/auth0-react';
import { useQuery } from '@tanstack/react-query';

import { getBotReport, getBrigadingReport, getReliabilityReport } from '../lib/api/integrity';
import type { BotReport, BrigadingReport, ReliabilityReport } from '../lib/api/types';

async function resolveToken(isAuthenticated: boolean, getToken: () => Promise<string>) {
  if (!isAuthenticated) {
    return undefined;
  }
  return getToken();
}

export function useBrigadingReport(threadId: number | undefined) {
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();
  return useQuery({
    queryKey: ['integrity', 'brigading', threadId],
    enabled: Boolean(threadId),
    queryFn: async (): Promise<BrigadingReport> => {
      if (!threadId) {
        throw new Error('threadId is required');
      }
      const token = await resolveToken(isAuthenticated, getAccessTokenSilently);
      return getBrigadingReport(threadId, token);
    }
  });
}

export function useBotReport(threadId: number | undefined) {
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();
  return useQuery({
    queryKey: ['integrity', 'bots', threadId],
    enabled: Boolean(threadId),
    queryFn: async (): Promise<BotReport> => {
      if (!threadId) {
        throw new Error('threadId is required');
      }
      const token = await resolveToken(isAuthenticated, getAccessTokenSilently);
      return getBotReport(threadId, token);
    }
  });
}

export function useReliabilityReport(threadId: number | undefined) {
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();
  return useQuery({
    queryKey: ['integrity', 'reliability', threadId],
    enabled: Boolean(threadId),
    queryFn: async (): Promise<ReliabilityReport> => {
      if (!threadId) {
        throw new Error('threadId is required');
      }
      const token = await resolveToken(isAuthenticated, getAccessTokenSilently);
      return getReliabilityReport(threadId, token);
    }
  });
}
