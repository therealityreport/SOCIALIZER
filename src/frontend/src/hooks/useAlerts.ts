import { useMemo } from 'react';

import { useAuth0 } from '@auth0/auth0-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createAlertRule,
  deleteAlertRule,
  listAlertHistory,
  listAlertRules,
  updateAlertRule
} from '../lib/api/alerts';
import type { AlertEvent, AlertRule, AlertRuleCreateRequest, AlertRuleUpdateRequest } from '../lib/api/types';

const ALERT_RULES_KEY = ['alert-rules'] as const;
const ALERT_HISTORY_KEY = ['alert-history'] as const;

async function resolveToken(isAuthenticated: boolean, getToken: () => Promise<string>) {
  if (!isAuthenticated) {
    return undefined;
  }
  return getToken();
}

export function useAlertRules(threadId?: number) {
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();
  return useQuery({
    queryKey: [...ALERT_RULES_KEY, threadId ?? 'global'],
    queryFn: async (): Promise<AlertRule[]> => {
      const token = await resolveToken(isAuthenticated, getAccessTokenSilently);
      return listAlertRules({ threadId, includeGlobal: true }, token);
    }
  });
}

export function useAlertHistory(threadId?: number, limit = 20) {
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();
  return useQuery({
    queryKey: [...ALERT_HISTORY_KEY, threadId ?? 'all', limit],
    queryFn: async (): Promise<AlertEvent[]> => {
      const token = await resolveToken(isAuthenticated, getAccessTokenSilently);
      return listAlertHistory({ threadId, limit }, token);
    }
  });
}

export function useAlertRuleMutations(threadId?: number) {
  const queryClient = useQueryClient();
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();

  const invalidate = useMemo(() => {
    return async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ALERT_RULES_KEY }),
        queryClient.invalidateQueries({ queryKey: ALERT_HISTORY_KEY })
      ]);
    };
  }, [queryClient]);

  const createMutation = useMutation({
    mutationFn: async (payload: AlertRuleCreateRequest) => {
      const token = await resolveToken(isAuthenticated, getAccessTokenSilently);
      return createAlertRule(payload, token);
    },
    onSuccess: invalidate
  });

  const updateMutation = useMutation({
    mutationFn: async ({ ruleId, payload }: { ruleId: number; payload: AlertRuleUpdateRequest }) => {
      const token = await resolveToken(isAuthenticated, getAccessTokenSilently);
      return updateAlertRule(ruleId, payload, token);
    },
    onSuccess: invalidate
  });

  const deleteMutation = useMutation({
    mutationFn: async (ruleId: number) => {
      const token = await resolveToken(isAuthenticated, getAccessTokenSilently);
      await deleteAlertRule(ruleId, token);
    },
    onSuccess: invalidate
  });

  return { createMutation, updateMutation, deleteMutation };
}
