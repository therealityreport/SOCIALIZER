import { useEffect, useState } from 'react';
import { Link, Outlet } from 'react-router-dom';

import { useUiStore } from '../../store/ui-store';
import { AppSidebar, appNavigation } from './app-sidebar';
import { AppHeader } from './app-header';
import { AppFooter } from './app-footer';
import { Modal } from '../ui/modal';
import { Button } from '../ui/button';
import { cn } from '../../lib/utils';

export function AppShell() {
  const { isSidebarOpen, toggleSidebar } = useUiStore();
  const isMobile = useIsMobile();

  return (
    <div className="flex min-h-screen bg-muted/30">
      <AppSidebar isOpen={isSidebarOpen} />
      <div className="flex min-h-screen flex-1 flex-col">
        <AppHeader onToggleSidebar={toggleSidebar} />
        <main className="flex-1 overflow-y-auto bg-muted/20 p-6">
          <Outlet />
        </main>
        <AppFooter />
      </div>
      {isMobile ? <MobileNavigation isOpen={isSidebarOpen} onClose={toggleSidebar} /> : null}
    </div>
  );
}

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const mediaQuery = window.matchMedia('(max-width: 767px)');
    const update = (event: MediaQueryListEvent | MediaQueryList) => {
      setIsMobile(event.matches);
    };

    update(mediaQuery);
    mediaQuery.addEventListener('change', update);
    return () => mediaQuery.removeEventListener('change', update);
  }, []);

  return isMobile;
}

type MobileNavigationProps = {
  isOpen: boolean;
  onClose: () => void;
};

function MobileNavigation({ isOpen, onClose }: MobileNavigationProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Navigate" className="max-w-sm">
      <div className="flex flex-col gap-2">
        {appNavigation.map((item) => (
          <Button key={item.to} variant="ghost" className={cn('justify-start gap-2 text-base')} asChild onClick={onClose}>
            <Link to={item.to}>
              <item.icon className="mr-2 h-4 w-4" />
              {item.label}
            </Link>
          </Button>
        ))}
      </div>
    </Modal>
  );
}
