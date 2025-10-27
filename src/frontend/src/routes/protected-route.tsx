import type { PropsWithChildren } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { useAuth0 } from '@auth0/auth0-react';

import { Spinner } from '../components/ui/spinner';

export function ProtectedRoute({ children }: PropsWithChildren) {
  const location = useLocation();
  const { isAuthenticated, isLoading } = useAuth0();

  if (isLoading) {
    return <Spinner label="Checking permissions..." className="p-6" />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return children;
}
