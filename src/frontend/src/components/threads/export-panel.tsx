import { useState } from 'react';

import { Download, FileJson, FileText } from 'lucide-react';

import { useCreateExport, useDownloadExport, type ExportHistoryEntry } from '../../hooks/useExports';
import { triggerFileDownload } from '../../lib/utils';
import { Alert } from '../ui/alert';
import { Button } from '../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Spinner } from '../ui/spinner';

type ExportPanelProps = {
  threadId: number;
};

const FORMATS = [
  { label: 'CSV Export', format: 'csv' as const, icon: FileText, description: 'Ready for spreadsheets' },
  { label: 'JSON Export', format: 'json' as const, icon: FileJson, description: 'Raw analytics payload' }
];

export function ExportPanel({ threadId }: ExportPanelProps) {
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<ExportHistoryEntry[]>([]);
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const createExportMutation = useCreateExport();
  const downloadExportMutation = useDownloadExport();

  const isBusy = createExportMutation.isPending || downloadExportMutation.isPending;

  const handleExport = async (format: 'csv' | 'json') => {
    setError(null);
    try {
      const exportMeta = await createExportMutation.mutateAsync({ threadId, format });
      const file = await downloadExportMutation.mutateAsync({ exportId: exportMeta.id });
      triggerFileDownload(file.blob, file.filename);
      setHistory((current) => [{ ...exportMeta, downloadedAt: new Date().toISOString() }, ...current].slice(0, 5));
      setIsMenuOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate export.');
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle className="flex items-center gap-2 text-xl">
            <Download className="h-5 w-5 text-primary" /> Export analytics
          </CardTitle>
          <CardDescription>Generate CSV or JSON to hand off to research, edit suites, or notebooks.</CardDescription>
        </div>
        <div className="relative">
          <Button variant="default" onClick={() => setIsMenuOpen((open) => !open)} disabled={isBusy}>
            {isBusy ? (
              <span className="flex items-center gap-2">
                <Spinner /> Preparing…
              </span>
            ) : (
              'Generate export'
            )}
          </Button>
          {isMenuOpen ? (
            <div className="absolute right-0 z-20 mt-2 w-48 divide-y divide-border overflow-hidden rounded-lg border border-border bg-popover shadow-lg">
              {FORMATS.map((option) => (
                <button
                  key={option.format}
                  type="button"
                  className="flex w-full items-start gap-2 px-3 py-2 text-left text-sm hover:bg-muted/70"
                  onClick={() => handleExport(option.format)}
                >
                  <option.icon className="mt-0.5 h-4 w-4" />
                  <span>
                    <span className="block font-medium text-foreground">{option.label}</span>
                    <span className="block text-xs text-muted-foreground">{option.description}</span>
                  </span>
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? <Alert variant="error" title="Export failed">{error}</Alert> : null}
        <div className="space-y-2 text-sm">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Recent exports</p>
          {history.length ? (
            <ul className="space-y-2">
              {history.map((item) => (
                <li key={item.id} className="flex items-center justify-between rounded-md border border-border px-3 py-2">
                  <div>
                    <p className="font-medium text-foreground">{item.filename}</p>
                    <p className="text-xs text-muted-foreground">{new Date(item.created_at).toLocaleString()}</p>
                  </div>
                  <BadgeForFormat format={item.format} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="rounded-md border border-dashed border-border p-4 text-xs text-muted-foreground">No exports yet. Generate one above to seed the history.</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function BadgeForFormat({ format }: { format: 'csv' | 'json' }) {
  return (
    <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-medium uppercase tracking-wide text-primary">
      {format.toUpperCase()}
    </span>
  );
}
