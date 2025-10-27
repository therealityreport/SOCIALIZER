import { useEffect } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { useAuth0 } from '@auth0/auth0-react';
import { LogIn } from 'lucide-react';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Alert } from '../components/ui/alert';

export default function Login() {
  const location = useLocation();
  const { isAuthenticated, loginWithRedirect, error, isLoading } = useAuth0();

  const redirectLocation = (location.state as { from?: Location })?.from;
  const targetPath = redirectLocation?.pathname ?? '/';

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      void loginWithRedirect({ appState: { returnTo: targetPath } });
    }
  }, [isAuthenticated, isLoading, loginWithRedirect, targetPath]);

  if (isAuthenticated) {
    return <Navigate to={targetPath} replace />;
  }

  return (
    <div className="flex h-full items-center justify-center">
      <Card className="max-w-md">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-2xl">
            <LogIn className="h-6 w-6 text-primary" />
            Sign in to SOCIALIZER
          </CardTitle>
          <CardDescription>We use Auth0 to protect analytics, exports, and producer tooling.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            You will be redirected to Auth0. After signing in, you&apos;ll land back here right where you left off.
          </p>
          {error ? <Alert variant="error" title="Authentication error">{error.message}</Alert> : null}
          <Button className="w-full" onClick={() => loginWithRedirect({ appState: { returnTo: targetPath } })} disabled={isLoading}>
            Continue with Auth0
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
