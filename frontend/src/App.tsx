import { lazy, Suspense, useEffect } from 'react';
import { Link, Route, Routes, useLocation } from 'react-router-dom';
import { Skeleton } from './components/bits';
import { Header } from './components/Header';
import { simulator } from './sim/simulator';
import { DashboardProvider } from './state/DashboardContext';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const IncidentPage = lazy(() => import('./pages/IncidentPage'));
const RespondPage = lazy(() => import('./pages/RespondPage'));
const ProfilesPage = lazy(() => import('./pages/ProfilesPage'));

function Fallback() {
  return (
    <div className="mx-auto max-w-7xl space-y-4 p-6">
      <Skeleton className="h-10 w-64" />
      <Skeleton className="h-64" />
    </div>
  );
}

export default function App() {
  const { pathname } = useLocation();
  const isResponder = pathname.startsWith('/respond/');

  // The simulator streams on operator pages only — never on a responder's phone.
  useEffect(() => {
    simulator.setActive(!isResponder);
  }, [isResponder]);

  if (isResponder) {
    return (
      <Suspense fallback={<Fallback />}>
        <Routes>
          <Route path="/respond/:incidentId" element={<RespondPage />} />
        </Routes>
      </Suspense>
    );
  }

  return (
    <DashboardProvider enabled>
      <Header />
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <Suspense fallback={<Fallback />}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/incidents/:id" element={<IncidentPage />} />
            <Route path="/profiles" element={<ProfilesPage />} />
            <Route
              path="*"
              element={
                <div className="py-20 text-center">
                  <p className="text-lg font-semibold">Page not found</p>
                  <Link to="/" className="text-sky-600 hover:underline">
                    Back to the dashboard
                  </Link>
                </div>
              }
            />
          </Routes>
        </Suspense>
      </main>
      <footer className="mx-auto max-w-7xl px-4 pb-8 text-xs text-slate-400 sm:px-6">
        ColdChain Guard · serverless on AWS (Lambda, Step Functions, DynamoDB, S3, API Gateway, SES, CloudFront) · Ranges are
        configurable examples, not medical advice.
      </footer>
    </DashboardProvider>
  );
}
