import { useEffect, useState } from 'react';

import { Modal } from '../ui/modal';
import { Alert } from '../ui/alert';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Spinner } from '../ui/spinner';

type AddCastMemberDialogProps = {
  isOpen: boolean;
  initialName: string;
  defaultShow: string;
  isSubmitting: boolean;
  errorMessage?: string | null;
  onClose: () => void;
  onSubmit: (payload: { full_name: string; display_name: string; show: string }) => Promise<void> | void;
};

export function AddCastMemberDialog({
  isOpen,
  initialName,
  defaultShow,
  isSubmitting,
  errorMessage,
  onClose,
  onSubmit
}: AddCastMemberDialogProps) {
  const [fullName, setFullName] = useState(initialName);
  const [displayName, setDisplayName] = useState(initialName);
  const [show, setShow] = useState(defaultShow);

  useEffect(() => {
    if (isOpen) {
      setFullName(initialName);
      setDisplayName(initialName);
      setShow(defaultShow);
    }
  }, [defaultShow, initialName, isOpen]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!fullName.trim()) {
      return;
    }
    await onSubmit({
      full_name: fullName.trim(),
      display_name: displayName.trim() || fullName.trim(),
      show: show.trim() || defaultShow
    });
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Add cast member"
      description="New cast members are immediately eligible for sentiment tracking."
    >
      <form className="space-y-4" onSubmit={handleSubmit}>
        {errorMessage ? <Alert variant="error">{errorMessage}</Alert> : null}
        <div className="grid gap-3">
          <div className="space-y-1">
            <label className="text-sm font-medium text-foreground">Full name</label>
            <Input value={fullName} onChange={(event) => setFullName(event.target.value)} required />
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium text-foreground">Display name</label>
            <Input value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium text-foreground">Show</label>
            <Input value={show} onChange={(event) => setShow(event.target.value)} required />
          </div>
        </div>
        <div className="flex justify-end gap-3">
          <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button type="submit" disabled={!fullName.trim() || isSubmitting}>
            {isSubmitting ? (
              <span className="flex items-center gap-2">
                <Spinner className="h-4 w-4" />
                Saving...
              </span>
            ) : (
              'Add member'
            )}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
