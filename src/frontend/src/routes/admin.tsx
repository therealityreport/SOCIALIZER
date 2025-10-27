import { ShieldCheck, Trash2 } from 'lucide-react';
import { useState } from 'react';

import { useMutation, useQueryClient } from '@tanstack/react-query';

import { AlertHistory } from '../components/alerts/alert-history';
import { AlertRuleForm } from '../components/alerts/alert-rule-form';
import { AlertRuleList } from '../components/alerts/alert-rule-list';
import { AlertRule, AlertEvent } from '../lib/api/types';
import { useAlertHistory, useAlertRuleMutations, useAlertRules } from '../hooks/useAlerts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Alert } from '../components/ui/alert';
import { Button } from '../components/ui/button';
import { Spinner } from '../components/ui/spinner';
import { useThreadList } from '../hooks/useThreads';
import { deleteThread } from '../lib/api/threads';

export default function Admin() {
  const [threadFilter, setThreadFilter] = useState<string>('');
  const threadId = threadFilter.trim() ? Number.parseInt(threadFilter, 10) : undefined;

  const queryClient = useQueryClient();
  const rulesQuery = useAlertRules(threadId);
  const historyQuery = useAlertHistory(threadId, 15);
  const { createMutation, deleteMutation, updateMutation } = useAlertRuleMutations(threadId);
  const threadsQuery = useThreadList();
  const deleteThreadMutation = useMutation({
    mutationFn: async (id: number) => deleteThread(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['threads'] });
    }
  });

  const handleCreate = (payload: {
    name: string;
    description?: string;
    cast_member_id?: number;
    thread_id?: number;
    channels: string[];
    condition: Record<string, unknown>;
  }) => {
    createMutation.mutate({ ...payload, rule_type: 'sentiment_drop', is_active: true });
  };

  const handleToggle = (rule: AlertRule) => {
    updateMutation.mutate({ ruleId: rule.id, payload: { is_active: !rule.is_active } });
  };

  const handleDelete = (rule: AlertRule) => {
    if (window.confirm(`Delete alert rule "${rule.name}"?`)) {
      deleteMutation.mutate(rule.id);
    }
  };

  const isMutating =
    createMutation.isPending || deleteMutation.isPending || updateMutation.isPending || deleteThreadMutation.isPending;

  const handleDeleteThread = (id: number, title: string) => {
    if (window.confirm(`Delete Reddit thread "${title}"? This cannot be undone.`)) {
      deleteThreadMutation.mutate(id);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-2xl text-foreground">
            <ShieldCheck className="h-6 w-6 text-primary" /> Alerting &amp; Integrity Control Center
          </CardTitle>
          <CardDescription>Fine-tune escalation thresholds and keep tabs on the moderation signal queue.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <label className="flex flex-col gap-1 text-sm text-foreground">
            <span>Filter by thread ID (optional)</span>
            <input
              value={threadFilter}
              onChange={(event) => setThreadFilter(event.target.value)}
              className="max-w-xs rounded-md border border-border bg-background px-3 py-2 text-sm"
              placeholder="123"
            />
            <span className="text-xs text-muted-foreground">Leave blank to manage global/default rules.</span>
          </label>

          {createMutation.error ? (
            <Alert variant="error">{(createMutation.error as Error).message}</Alert>
          ) : null}

          <AlertRuleForm
            threadId={threadId}
            isSubmitting={createMutation.isPending}
            onSubmit={handleCreate}
          />

          {rulesQuery.error ? (
            <Alert variant="error">Failed to load rules: {(rulesQuery.error as Error).message}</Alert>
          ) : null}

          <AlertRuleList
            rules={rulesQuery.data ?? []}
            onToggleActive={handleToggle}
            onDelete={handleDelete}
            isMutating={isMutating}
          />
        </CardContent>
      </Card>

      <AlertHistory events={(historyQuery.data as AlertEvent[]) ?? []} />

      <Card>
        <CardHeader>
          <CardTitle>Thread management</CardTitle>
          <CardDescription>Prune imported Reddit threads as needed.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {threadsQuery.isLoading ? <Spinner label="Loading threads..." /> : null}
          {threadsQuery.isError ? (
            <Alert variant="error">{(threadsQuery.error as Error).message}</Alert>
          ) : null}
          {!threadsQuery.isLoading && !threadsQuery.isError ? (
            <div className="space-y-3">
              {(threadsQuery.data ?? [])
                .filter((thread) => !thread.reddit_id.startsWith('test'))
                .map((thread) => (
                <div
                  key={thread.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border px-4 py-3 text-sm"
                >
                  <div>
                    <p className="font-semibold text-foreground">{thread.title}</p>
                    <p className="text-xs text-muted-foreground">
                      #{thread.id} · r/{thread.subreddit ?? 'unknown'} · {new Date(thread.created_at).toLocaleString()}
                    </p>
                  </div>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => handleDeleteThread(thread.id, thread.title)}
                    disabled={deleteThreadMutation.isPending}
                    className="gap-2"
                  >
                    <Trash2 className="h-4 w-4" /> Delete thread
                  </Button>
                </div>
              ))}
              {!((threadsQuery.data ?? []).filter((thread) => !thread.reddit_id.startsWith('test')).length) ? (
                <Alert variant="info">No threads have been imported yet.</Alert>
              ) : null}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
