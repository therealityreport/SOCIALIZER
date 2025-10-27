import { useMemo } from 'react';

import { useAuth0 } from '@auth0/auth0-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createCastMember,
  deleteCastMember,
  listCastMembers,
  updateCastMember,
  type CastMemberCreateRequest,
  type CastMemberUpdateRequest
} from '../lib/api/cast';
import type { CastMember } from '../lib/api/types';

const CAST_ROSTER_KEY = ['cast-roster'] as const;

async function resolveToken(isAuthenticated: boolean, getToken: () => Promise<string>) {
  if (!isAuthenticated) {
    return undefined;
  }
  return getToken();
}

export function useCastRoster() {
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();

  return useQuery({
    queryKey: CAST_ROSTER_KEY,
    queryFn: async () => {
      const token = await resolveToken(isAuthenticated, getAccessTokenSilently);
      return listCastMembers(token);
    }
  });
}

export function useCastRosterMutations() {
  const queryClient = useQueryClient();
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();

  const invalidate = useMemo(() => {
    return async () => {
      await queryClient.invalidateQueries({ queryKey: CAST_ROSTER_KEY });
    };
  }, [queryClient]);

  const createMutation = useMutation({
    mutationFn: async (payload: CastMemberCreateRequest) => {
      const token = await resolveToken(isAuthenticated, getAccessTokenSilently);
      return createCastMember(payload, token);
    },
    onSuccess: invalidate
  });

  const updateMutation = useMutation({
    mutationFn: async ({ castId, payload }: { castId: number; payload: CastMemberUpdateRequest }) => {
      const token = await resolveToken(isAuthenticated, getAccessTokenSilently);
      return updateCastMember(castId, payload, token);
    },
    onSuccess: invalidate
  });

  const deleteMutation = useMutation({
    mutationFn: async (castId: number) => {
      const token = await resolveToken(isAuthenticated, getAccessTokenSilently);
      await deleteCastMember(castId, token);
    },
    onSuccess: invalidate
  });

  return { createMutation, updateMutation, deleteMutation };
}
