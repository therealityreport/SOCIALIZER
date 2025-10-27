import { useAuth0 } from '@auth0/auth0-react';
import { useMutation } from '@tanstack/react-query';

import { createExport, downloadExport } from '../lib/api/exports';
import type { ExportFormat, ExportResponse } from '../lib/api/types';

export function useCreateExport() {
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();

  return useMutation({
    mutationFn: async ({ threadId, format }: { threadId: number; format: ExportFormat }) => {
      const token = isAuthenticated ? await getAccessTokenSilently() : undefined;
      return createExport(threadId, format, token);
    }
  });
}

export function useDownloadExport() {
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();

  return useMutation({
    mutationFn: async ({ exportId }: { exportId: number }) => {
      const token = isAuthenticated ? await getAccessTokenSilently() : undefined;
      return downloadExport(exportId, token);
    }
  });
}

export type ExportHistoryEntry = ExportResponse & {
  downloadedAt?: string;
};
