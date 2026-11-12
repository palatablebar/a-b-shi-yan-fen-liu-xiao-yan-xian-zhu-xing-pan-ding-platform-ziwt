import type { ReactNode } from 'react';
import { createBrowserRouter } from 'react-router-dom';
import { AuthGate } from '../components/layout/AuthGate';
import { NotebookShell } from '../components/layout/NotebookShell';
import { DecisionsPage } from '../pages/Decisions';
import { ExperimentDetailPage } from '../pages/ExperimentDetail';
import { ExperimentsPage } from '../pages/Experiments';
import { LoginPage } from '../pages/Login';
import { RunsPage } from '../pages/Runs';
import { SegmentsPage } from '../pages/Segments';

const withShell = (element: ReactNode) => (
  <AuthGate>
    <NotebookShell>{element}</NotebookShell>
  </AuthGate>
);

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/', element: withShell(<ExperimentsPage />) },
  { path: '/experiments', element: withShell(<ExperimentsPage />) },
  { path: '/experiments/:experimentId', element: withShell(<ExperimentDetailPage />) },
  { path: '/experiments/:experimentId/segments', element: withShell(<SegmentsPage />) },
  { path: '/runs', element: withShell(<RunsPage />) },
  { path: '/segments', element: withShell(<SegmentsPage />) },
  { path: '/decisions', element: withShell(<DecisionsPage />) },
  { path: '*', element: withShell(<ExperimentsPage />) },
]);
