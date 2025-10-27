import { Suspense } from 'react';
import { RouterProvider, createBrowserRouter } from 'react-router-dom';

import { routes } from './routes';

const router = createBrowserRouter(routes);

function App() {
  return (
    <Suspense fallback={<div className="p-6 text-muted-foreground">Loading...</div>}>
      <RouterProvider router={router} />
    </Suspense>
  );
}

export default App;
