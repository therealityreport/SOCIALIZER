import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';

import { X } from 'lucide-react';

import { cn } from '../../lib/utils';
import { Button } from './button';

export type ModalProps = {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  className?: string;
  children: React.ReactNode;
};

export function Modal({ isOpen, onClose, title, description, className, children }: ModalProps) {
  const dialogRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose();
      }
    }

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/60 backdrop-blur">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        className={cn('relative w-full max-w-lg rounded-xl border border-border bg-card p-6 shadow-2xl', className)}
      >
        <Button aria-label="Close modal" variant="ghost" size="icon" className="absolute right-3 top-3" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
        {title ? <h2 className="text-xl font-semibold text-foreground">{title}</h2> : null}
        {description ? <p className="mt-1 text-sm text-muted-foreground">{description}</p> : null}
        <div className="mt-4">{children}</div>
      </div>
    </div>,
    document.body
  );
}
