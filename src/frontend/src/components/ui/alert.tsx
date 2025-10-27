import { cva, type VariantProps } from 'class-variance-authority';
import { XCircle, CheckCircle2, Info, AlertTriangle } from 'lucide-react';

import { cn } from '../../lib/utils';

const alertVariants = cva('flex w-full items-start gap-3 rounded-lg border p-4 text-sm', {
  variants: {
    variant: {
      info: 'border-sky-200 bg-sky-100/40 text-sky-900 dark:border-sky-900/40 dark:bg-sky-900/20 dark:text-sky-100',
      success: 'border-emerald-200 bg-emerald-100/40 text-emerald-900 dark:border-emerald-900/40 dark:bg-emerald-900/20 dark:text-emerald-100',
      warning: 'border-amber-200 bg-amber-100/40 text-amber-900 dark:border-amber-900/40 dark:bg-amber-900/20 dark:text-amber-100',
      error: 'border-rose-200 bg-rose-100/40 text-rose-900 dark:border-rose-900/40 dark:bg-rose-900/20 dark:text-rose-100'
    }
  },
  defaultVariants: {
    variant: 'info'
  }
});

const iconMap = {
  info: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  error: XCircle
};

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof alertVariants> {
  title?: string;
}

export function Alert({ className, variant, title, children, ...props }: AlertProps) {
  const Icon = iconMap[variant ?? 'info'];

  return (
    <div className={cn(alertVariants({ variant }), className)} role="alert" {...props}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="flex flex-col gap-1">
        {title ? <p className="font-medium leading-none">{title}</p> : null}
        {children ? <p className="text-sm leading-relaxed">{children}</p> : null}
      </div>
    </div>
  );
}
