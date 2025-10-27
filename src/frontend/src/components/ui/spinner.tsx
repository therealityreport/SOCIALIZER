import { cn } from '../../lib/utils';

type SpinnerProps = {
  label?: string;
  className?: string;
};

export function Spinner({ label, className }: SpinnerProps) {
  return (
    <div className={cn('flex items-center gap-2 text-sm text-muted-foreground', className)}>
      <span className="inline-flex h-4 w-4 animate-spin rounded-full border-2 border-muted-foreground/40 border-t-transparent" />
      {label ? <span>{label}</span> : null}
    </div>
  );
}
