import { useState } from 'react';

import { Button } from '../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';

type FormState = {
  name: string;
  description: string;
  window: string;
  threshold: string;
  castMemberId: string;
  emails: string;
  enableSlack: boolean;
  enableEmail: boolean;
};

const INITIAL_STATE: FormState = {
  name: '',
  description: '',
  window: 'live',
  threshold: '-0.4',
  castMemberId: '',
  emails: '',
  enableSlack: true,
  enableEmail: false
};

type AlertRuleFormProps = {
  threadId?: number;
  defaultCastMemberId?: number;
  isSubmitting: boolean;
  onSubmit: (payload: {
    name: string;
    description?: string;
    cast_member_id?: number;
    thread_id?: number;
    condition: Record<string, unknown>;
    channels: string[];
  }) => void;
};

export function AlertRuleForm({ threadId, defaultCastMemberId, isSubmitting, onSubmit }: AlertRuleFormProps) {
  const [state, setState] = useState<FormState>({
    ...INITIAL_STATE,
    castMemberId: defaultCastMemberId ? String(defaultCastMemberId) : ''
  });

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const thresholdValue = Number.parseFloat(state.threshold);
    if (Number.isNaN(thresholdValue)) {
      alert('Threshold must be numeric.');
      return;
    }

    const condition: Record<string, unknown> = {
      metric: 'net_sentiment',
      window: state.window,
      comparison: 'lt',
      threshold: thresholdValue
    };

    if (state.emails.trim()) {
      condition.emails = state.emails.split(',').map((value) => value.trim()).filter(Boolean);
    }

    const castMemberId = state.castMemberId.trim() ? Number.parseInt(state.castMemberId, 10) : undefined;

    onSubmit({
      name: state.name.trim() || 'Sentiment Drop Alert',
      description: state.description.trim() || undefined,
      cast_member_id: Number.isFinite(castMemberId) ? castMemberId : undefined,
      thread_id: threadId,
      channels: [state.enableSlack && 'slack', state.enableEmail && 'email'].filter(Boolean) as string[],
      condition
    });

    setState((prev) => ({ ...prev, name: '', description: '', emails: '' }));
  };

  return (
    <Card className="border-dashed">
      <CardHeader>
        <CardTitle>Create sentiment alert</CardTitle>
        <CardDescription>Watch for sharp drops in cast sentiment and push notifications to Slack or email.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium text-foreground">Rule name</span>
              <input
                value={state.name}
                onChange={(event) => setState((prev) => ({ ...prev, name: event.target.value }))}
                placeholder="Live drop alert"
                className="rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium text-foreground">Cast member ID (optional)</span>
              <input
                value={state.castMemberId}
                onChange={(event) => setState((prev) => ({ ...prev, castMemberId: event.target.value }))}
                placeholder="123"
                className="rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium text-foreground">Window</span>
              <select
                value={state.window}
                onChange={(event) => setState((prev) => ({ ...prev, window: event.target.value }))}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm"
              >
                <option value="live">Live</option>
                <option value="day_of">Day Of</option>
                <option value="after">After</option>
                <option value="overall">Overall</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium text-foreground">Threshold</span>
              <input
                value={state.threshold}
                onChange={(event) => setState((prev) => ({ ...prev, threshold: event.target.value }))}
                placeholder="-0.4"
                className="rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
            </label>
          </div>

          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-foreground">Description</span>
            <textarea
              value={state.description}
              onChange={(event) => setState((prev) => ({ ...prev, description: event.target.value }))}
              rows={3}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm"
              placeholder="Notify the team when sentiment plummets mid-episode."
            />
          </label>

          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                checked={state.enableSlack}
                onChange={(event) => setState((prev) => ({ ...prev, enableSlack: event.target.checked }))}
                className="h-4 w-4"
              />
              Slack
            </label>
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                checked={state.enableEmail}
                onChange={(event) => setState((prev) => ({ ...prev, enableEmail: event.target.checked }))}
                className="h-4 w-4"
              />
              Email
            </label>
          </div>

          {state.enableEmail ? (
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium text-foreground">Email recipients</span>
              <input
                value={state.emails}
                onChange={(event) => setState((prev) => ({ ...prev, emails: event.target.value }))}
                placeholder="producer@network.com, analyst@network.com"
                className="rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
              <span className="text-xs text-muted-foreground">Separate multiple emails with commas.</span>
            </label>
          ) : null}

          <Button type="submit" disabled={isSubmitting} className="w-full sm:w-auto">
            {isSubmitting ? 'Saving rule…' : 'Create alert rule'}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
