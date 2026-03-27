import { Routes, Route, useLocation } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import { lazy, Suspense } from 'react';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';

// Code splitting with React.lazy for route-level code splitting
const Home = lazy(() => import('./pages/Home'));
const GettingStarted = lazy(() => import('./pages/GettingStarted'));
const Architecture = lazy(() => import('./pages/Architecture'));
const ApiReference = lazy(() => import('./pages/ApiReference'));

// Loading fallback component
const PageLoader = () => (
  <div className="flex-1 flex items-center justify-center min-h-[50vh]">
    <div className="flex flex-col items-center gap-3">
      <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      <span className="text-sm text-slate-500 dark:text-slate-400">Loading...</span>
    </div>
  </div>
);

function NotFound() {
  return (
    <div className="flex flex-1 items-center justify-center p-8">
      <div className="text-center">
        <h1 className="text-6xl font-bold text-brand-400 mb-4">404</h1>
        <p className="text-xl text-slate-300 mb-6">Page not found</p>
        <a href="/" className="text-brand-400 hover:text-brand-300 underline">← Back to Home</a>
      </div>
    </div>
  );
}

function App() {
  const location = useLocation();

  return (
    <div className="min-h-screen dark flex flex-col bg-slate-950 text-slate-50 relative selection:bg-brand-500/30">
      <Navbar />
      
      <div className="flex flex-1 pt-16">
        {/* Only show sidebar on non-home pages if we want, or keep it everywhere. Let's keep it conditionally for docs */}
        {location.pathname !== '/' && <Sidebar />}
        
        <main className={`flex-1 w-full flex flex-col ${location.pathname !== '/' ? 'md:ml-64' : ''}`}>
          <AnimatePresence mode="wait">
            <Suspense fallback={<PageLoader />}>
              <Routes location={location} key={location.pathname}>
                <Route path="/" element={<Home />} />
                <Route path="/docs/getting-started" element={<GettingStarted />} />
                <Route path="/docs/architecture" element={<Architecture />} />
                <Route path="/docs/api-reference" element={<ApiReference />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </Suspense>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}

export default App;
