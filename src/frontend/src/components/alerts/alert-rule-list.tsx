import { Fragment } from 'react';

import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import type { AlertRule } from '../../lib/api/types';

type AlertRuleListProps = {
  rules: AlertRule[];
  onToggleActive: (rule: AlertRule) => void;
  onDelete: (rule: AlertRule) => void;
  isMutating: boolean;
};

export function AlertRuleList({ rules, onToggleActive, onDelete, isMutating }: AlertRuleListProps) {
  if (!rules.length) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Existing rules</CardTitle>
          <CardDescription>No alert rules configured yet.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Existing rules</CardTitle>
        <CardDescription>Toggle, update, or remove alert rules at any time.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {rules.map((rule) => (
          <Fragment key={rule.id}>
            <div className="flex flex-col gap-3 rounded-lg border border-border p-4 md:flex-row md:items-center md:justify-between">
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-lg font-semibold text-foreground">{rule.name}</span>
                  <Badge variant={rule.is_active ? 'positive' : 'neutral'}>{rule.is_active ? 'Active' : 'Paused'}</Badge>
                </div>
                {rule.description ? <p className="text-sm text-muted-foreground">{rule.description}</p> : null}
                <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <span>Window: {String(rule.condition.window ?? '—')}</span>
                  <span>Threshold: {String(rule.condition.threshold ?? '—')}</span>
                  <span>Channels: {(rule.channels ?? []).join(', ') || 'None'}</span>
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={isMutating}
                  onClick={() => onToggleActive(rule)}
                >
                  {rule.is_active ? 'Pause' : 'Activate'}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={isMutating}
                  onClick={() => onDelete(rule)}
                  className="text-destructive"
                >
                  Delete
                </Button>
              </div>
            </div>
          </Fragment>
        ))}
      </CardContent>
    </Card>
  );
}
