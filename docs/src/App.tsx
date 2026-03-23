import { Routes, Route, useLocation } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import Home from './pages/Home';
import GettingStarted from './pages/GettingStarted';
import Architecture from './pages/Architecture';
import ApiReference from './pages/ApiReference';

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
            <Routes location={location} key={location.pathname}>
              <Route path="/" element={<Home />} />
              <Route path="/docs/getting-started" element={<GettingStarted />} />
              <Route path="/docs/architecture" element={<Architecture />} />
              <Route path="/docs/api-reference" element={<ApiReference />} />
            </Routes>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}

export default App;
