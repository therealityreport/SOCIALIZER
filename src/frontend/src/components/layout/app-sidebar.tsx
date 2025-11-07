import { Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Users, Shield, ContactRound, Tv, Globe2, PlusCircle, Instagram } from 'lucide-react';

import { Button } from '../ui/button';
import { cn } from '../../lib/utils';

export const appNavigation = [
  { label: 'Dashboard', to: '/', icon: LayoutDashboard },
  { label: 'Threads', to: '/threads', icon: Users },
  { label: 'Shows', to: '/shows', icon: Tv },
  { label: 'Communities', to: '/communities', icon: Globe2 },
  { label: 'Cast roster', to: '/cast-roster', icon: ContactRound },
  { label: 'Add Thread', to: '/threads/new', icon: PlusCircle },
  { label: 'Instagram ingest', to: '/instagram/ingest', icon: Instagram },
  { label: 'Admin', to: '/admin', icon: Shield }
];

type AppSidebarProps = {
  isOpen: boolean;
};

export function AppSidebar({ isOpen }: AppSidebarProps) {
  const location = useLocation();

  return (
    <aside
      className={cn(
        'hidden border-r border-border bg-background transition-all duration-200 md:flex',
        isOpen ? 'w-64' : 'w-20'
      )}
    >
      <div className="flex h-full w-full flex-col gap-6 px-4 py-6">
        <div className="flex items-center gap-2">
          <div className="text-2xl font-bold text-primary">{isOpen ? 'SOCIALIZER' : 'SZ'}</div>
        </div>
        <nav className="flex flex-1 flex-col gap-2">
          {appNavigation.map((item) => {
            const isActive =
              location.pathname === item.to || (item.to !== '/' && location.pathname.startsWith(`${item.to}/`));
            const Icon = item.icon;
            return (
              <Button
                key={item.to}
                variant={isActive ? 'default' : 'ghost'}
                className={cn(
                  'w-full justify-start gap-3',
                  !isOpen && 'justify-center px-0',
                  isActive && 'bg-primary text-primary-foreground'
                )}
                asChild
              >
                <Link to={item.to}>
                  <Icon className="h-4 w-4" />
                  {isOpen ? <span>{item.label}</span> : null}
                </Link>
              </Button>
            );
          })}
        </nav>
      </div>
    </aside>
  );
}
