import { Menu } from 'lucide-react';

import { Button } from '../ui/button';
import { ThemeToggle } from '../ui/theme-toggle';

type AppHeaderProps = {
  onToggleSidebar: () => void;
};

export function AppHeader({ onToggleSidebar }: AppHeaderProps) {
  return (
    <header className="flex items-center justify-between border-b border-border bg-background/80 px-6 py-4 backdrop-blur">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Live Thread Sentiment Radar</h1>
        <p className="text-sm text-muted-foreground">Monitor Bravo fandom sentiment across Reddit threads.</p>
      </div>
      <div className="flex items-center gap-3">
        <ThemeToggle />
        <Button variant="outline" size="icon" className="md:hidden" onClick={onToggleSidebar} aria-label="Toggle navigation">
          <Menu className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}
