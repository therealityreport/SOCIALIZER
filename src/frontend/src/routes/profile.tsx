import { useAuth0 } from '@auth0/auth0-react';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Spinner } from '../components/ui/spinner';

export default function Profile() {
  const { user, isLoading } = useAuth0();

  if (isLoading) {
    return <Spinner label="Loading profile..." className="p-6" />;
  }

  if (!user) {
    return <p className="text-sm text-muted-foreground">No profile data available.</p>;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Profile</CardTitle>
        <CardDescription>Your Auth0 identity details.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-muted-foreground">
        <div>
          <p className="text-xs uppercase tracking-wide">Name</p>
          <p className="text-foreground">{user.name ?? '—'}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide">Email</p>
          <p className="text-foreground">{user.email ?? '—'}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide">Sub</p>
          <p className="text-foreground break-all">{user.sub ?? '—'}</p>
        </div>
      </CardContent>
    </Card>
  );
}
