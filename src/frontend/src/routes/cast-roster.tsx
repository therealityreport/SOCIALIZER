import { useEffect, useMemo, useState } from 'react';

import { PlusCircle, Trash2 } from 'lucide-react';

import { useCastRoster, useCastRosterMutations } from '../hooks/useCastRoster';
import type { CastMember } from '../lib/api/types';
import { Alert } from '../components/ui/alert';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Spinner } from '../components/ui/spinner';

type DraftState = {
  full_name: string;
  display_name: string;
  show: string;
  aliases: string;
};

const defaultDraft: DraftState = {
  full_name: '',
  display_name: '',
  show: 'RHOSLC',
  aliases: ''
};

export default function CastRosterPage() {
  const { data: roster, isLoading, isError, error } = useCastRoster();
  const { createMutation, updateMutation, deleteMutation } = useCastRosterMutations();
  const [draft, setDraft] = useState(defaultDraft);
  const [selectedShow, setSelectedShow] = useState<string>('all');

  const showOptions = useMemo(() => {
    if (!roster) {
      return ['all'];
    }
    const unique = new Set<string>();
    roster.forEach((member) => {
      unique.add(normalizeShow(member.show));
    });
    return ['all', ...Array.from(unique).sort()];
  }, [roster]);

  useEffect(() => {
    if (selectedShow !== 'all') {
      setDraft((state) => ({ ...state, show: selectedShow }));
    }
  }, [selectedShow]);

  const filteredRoster = useMemo(() => {
    if (!roster) {
      return [];
    }
    const normalizedFilter = selectedShow === 'all' ? null : selectedShow;
    return roster.filter((member) => {
      const show = normalizeShow(member.show);
      return !normalizedFilter || show === normalizedFilter;
    });
  }, [roster, selectedShow]);

  const sortedRoster = useMemo(() => {
    return [...filteredRoster].sort((a, b) => a.full_name.localeCompare(b.full_name));
  }, [filteredRoster]);

  const handleCreate = async () => {
    if (!draft.full_name.trim()) {
      return;
    }
    const aliases = draft.aliases.split(',').map((item) => item.trim()).filter(Boolean);
    await createMutation.mutateAsync({
      full_name: draft.full_name.trim(),
      display_name: draft.display_name.trim() || draft.full_name.trim(),
      show: draft.show.trim() || 'RHOSLC',
      aliases
    });
    setDraft(defaultDraft);
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Cast roster</CardTitle>
          <CardDescription>Manage cast members and maintain the alias list used for entity linking.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-4">
          <Input
            placeholder="Full name"
            value={draft.full_name}
            onChange={(event) => setDraft((state) => ({ ...state, full_name: event.target.value }))}
          />
          <Input
            placeholder="Display name"
            value={draft.display_name}
            onChange={(event) => setDraft((state) => ({ ...state, display_name: event.target.value }))}
          />
          <Input
            placeholder="Show"
            value={draft.show}
            onChange={(event) => setDraft((state) => ({ ...state, show: event.target.value }))}
          />
          <div className="flex items-center gap-2">
            <Input
              placeholder="Aliases (comma separated)"
              value={draft.aliases}
              onChange={(event) => setDraft((state) => ({ ...state, aliases: event.target.value }))}
            />
            <Button
              onClick={handleCreate}
              disabled={!draft.full_name.trim() || createMutation.isPending}
              title="Add cast member"
            >
              {createMutation.isPending ? <Spinner className="h-4 w-4" /> : <PlusCircle className="h-4 w-4" />}
            </Button>
          </div>
        </CardContent>
        {createMutation.isError ? (
          <div className="px-6 pb-4">
            <Alert variant="error">{createMutation.error instanceof Error ? createMutation.error.message : 'Failed to create cast member.'}</Alert>
          </div>
        ) : null}
      </Card>

      {isLoading ? <Spinner label="Loading cast roster..." /> : null}
      {isError ? <Alert variant="error">{error?.message ?? 'Unable to fetch cast roster.'}</Alert> : null}

      {!isLoading && !isError ? (
        <div className="space-y-4">
          <div className="flex items-center justify-end gap-2">
            <label htmlFor="roster-show-filter" className="text-xs uppercase tracking-wide text-muted-foreground">
              Filter by show
            </label>
            <select
              id="roster-show-filter"
              value={selectedShow}
              onChange={(event) => setSelectedShow(event.target.value)}
              className="rounded-md border border-border bg-background px-3 py-1 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            >
              {showOptions.map((option) => (
                <option key={option} value={option}>
                  {option === 'all' ? 'All shows' : option}
                </option>
              ))}
            </select>
          </div>
          {sortedRoster.map((member) => (
            <CastMemberCard
              key={member.id}
              member={member}
              onUpdate={async (payload) => updateMutation.mutateAsync({ castId: member.id, payload })}
              onDelete={() => deleteMutation.mutateAsync(member.id)}
              isUpdating={updateMutation.isPending}
              updateError={updateMutation.isError ? (updateMutation.error instanceof Error ? updateMutation.error.message : 'Failed to update cast member.') : null}
              isDeleting={deleteMutation.isPending}
              deleteError={deleteMutation.isError ? (deleteMutation.error instanceof Error ? deleteMutation.error.message : 'Failed to delete cast member.') : null}
            />
          ))}
          {!sortedRoster.length ? <Alert variant="info">No cast members configured yet.</Alert> : null}
        </div>
      ) : null}
    </div>
  );
}

type CastMemberCardProps = {
  member: CastMember;
  onUpdate: (payload: { aliases?: string[]; is_active?: boolean }) => Promise<unknown>;
  onDelete: () => Promise<unknown>;
  isUpdating: boolean;
  updateError: string | null;
  isDeleting: boolean;
  deleteError: string | null;
};

function CastMemberCard({ member, onUpdate, onDelete, isUpdating, updateError, isDeleting, deleteError }: CastMemberCardProps) {
  const [aliasInput, setAliasInput] = useState('');
  const displayShow = normalizeShow(member.show);

  const handleAddAlias = async () => {
    const value = aliasInput.trim();
    if (!value || member.aliases.includes(value)) {
      return;
    }
    await onUpdate({ aliases: [...member.aliases, value] });
    setAliasInput('');
  };

  const handleRemoveAlias = async (alias: string) => {
    const nextAliases = member.aliases.filter((item) => item !== alias);
    await onUpdate({ aliases: nextAliases });
  };

  return (
    <Card>
      <CardHeader className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <CardTitle className="text-xl text-foreground">{member.full_name}</CardTitle>
          <CardDescription>
            {displayShow} ·{member.is_active ? ' Active' : ' Inactive'} · Slug: {member.slug}
          </CardDescription>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onUpdate({ is_active: !member.is_active })}
            disabled={isUpdating}
          >
            {member.is_active ? 'Deactivate' : 'Activate'}
          </Button>
          <Button variant="destructive" size="sm" onClick={onDelete} disabled={isDeleting} title="Delete cast member">
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {updateError ? <Alert variant="error">{updateError}</Alert> : null}
        {deleteError ? <Alert variant="error">{deleteError}</Alert> : null}
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Aliases</p>
          <div className="flex flex-wrap gap-2">
            {member.aliases.map((alias) => (
              <Badge key={alias} variant="outline" className="flex items-center gap-2">
                <span>{alias}</span>
                <button
                  type="button"
                  className="text-xs text-muted-foreground hover:text-destructive"
                  onClick={() => handleRemoveAlias(alias)}
                  disabled={isUpdating}
                >
                  ×
                </button>
              </Badge>
            ))}
            {!member.aliases.length ? <span className="text-xs text-muted-foreground">No aliases</span> : null}
          </div>
        </div>

        <div className="flex flex-col gap-2 md:flex-row md:items-center">
          <Input
            placeholder="Add alias"
            value={aliasInput}
            onChange={(event) => setAliasInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault();
                handleAddAlias();
              }
            }}
          />
          <Button onClick={handleAddAlias} disabled={!aliasInput.trim() || isUpdating} variant="secondary">
            Add alias
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function normalizeShow(show: string) {
  if (show === 'The Real Housewives of Salt Lake City') {
    return 'RHOSLC';
  }
  return show;
}
