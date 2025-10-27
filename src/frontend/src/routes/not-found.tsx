import { Button } from '../components/ui/button';

export default function NotFound() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
      <p className="text-6xl font-bold text-primary">404</p>
      <p className="text-lg text-muted-foreground">We could not find the page you were looking for.</p>
      <Button onClick={() => window.location.assign('/')}>Return to dashboard</Button>
    </div>
  );
}
