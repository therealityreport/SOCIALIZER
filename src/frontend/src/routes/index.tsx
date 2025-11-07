import type { RouteObject } from 'react-router-dom';

import { AppShell } from '../components/layout/app-shell';
import Admin from './admin';
import CastDetail from './cast-detail';
import Dashboard from './dashboard';
import ErrorPage from './error-page';
import Login from './login';
import NotFound from './not-found';
import Profile from './profile';
import ThreadDetail from './thread-detail';
import ThreadIndex from './threads';
import CastRosterPage from './cast-roster';
import { ProtectedRoute } from './protected-route';
import TrackThreadPage from './thread-new';
import ShowsPage from './shows';
import CommunitiesPage from './communities';
import InstagramIngestPage from '../pages/instagram/ingest';

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <AppShell />,
    errorElement: <ErrorPage />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'threads', element: <ThreadIndex /> },
      { path: 'threads/new', element: <TrackThreadPage /> },
      { path: 'threads/:threadId', element: <ThreadDetail /> },
      { path: 'threads/:threadId/cast/:castSlug', element: <CastDetail /> },
      { path: 'shows', element: <ShowsPage /> },
      { path: 'communities', element: <CommunitiesPage /> },
      { path: 'cast-roster', element: <CastRosterPage /> },
      { path: 'instagram/ingest', element: <InstagramIngestPage /> },
      { path: 'admin', element: <Admin /> },
      {
        path: 'profile',
        element: (
          <ProtectedRoute>
            <Profile />
          </ProtectedRoute>
        )
      },
      { path: 'login', element: <Login /> },
      { path: '*', element: <NotFound /> }
    ]
  }
];
