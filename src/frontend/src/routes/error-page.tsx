import { isRouteErrorResponse, useRouteError } from 'react-router-dom';

import { Button } from '../components/ui/button';

export default function ErrorPage() {
  const error = useRouteError();

  let message = 'Unexpected error occurred.';
  if (isRouteErrorResponse(error)) {
    message = `${error.status} ${error.statusText}`;
  } else if (error instanceof Error) {
    message = error.message;
  }

  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
      <h1 className="text-3xl font-bold">Something went wrong</h1>
      <p className="max-w-sm text-muted-foreground">{message}</p>
      <Button onClick={() => window.location.assign('/')}>Go back home</Button>
    </div>
  );
}
