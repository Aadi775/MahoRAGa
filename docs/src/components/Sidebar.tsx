import { Link, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { BookOpen, Layers, Code2, ChevronRight, X } from 'lucide-react';
import { useState } from 'react';

const Sidebar = () => {
  const location = useLocation();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const navItems = [
    { section: 'Getting Started', items: [
      { path: '/docs/getting-started', label: 'Installation', icon: BookOpen }
    ]},
    { section: 'Core Concepts', items: [
      { path: '/docs/architecture', label: 'Architecture & Engine', icon: Layers }
    ]},
    { section: 'Reference', items: [
      { path: '/docs/api-reference', label: 'API Tool Reference', icon: Code2 }
    ]}
  ];

  const isDocsPage = location.pathname.startsWith('/docs');

  // Desktop sidebar
  const desktopSidebar = (
    <aside className="hidden md:block fixed left-0 top-16 h-[calc(100vh-4rem)] w-64 border-r border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-950/50 backdrop-blur-xl overflow-y-auto">
      <nav className="p-6 space-y-8">
        {navItems.map((group, idx) => (
          <div key={idx}>
            <h4 className="font-semibold text-xs tracking-wider text-slate-500 uppercase mb-3">
              {group.section}
            </h4>
            <ul className="space-y-1">
              {group.items.map((item) => {
                const isActive = location.pathname === item.path;
                const Icon = item.icon;
                
                return (
                  <li key={item.path}>
                    <Link
                      to={item.path}
                      className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors relative group ${
                        isActive 
                          ? 'text-brand-600 dark:text-brand-400' 
                          : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/50'
                      }`}
                    >
                      {isActive && (
                        <motion.div
                          layoutId="sidebar-active"
                          className="absolute inset-0 bg-brand-50 dark:bg-brand-900/20 rounded-lg -z-10"
                          transition={{ type: "spring", bounce: 0.1, duration: 0.5 }}
                        />
                      )}
                      {isActive && (
                        <motion.div
                          layoutId="sidebar-active-pill"
                          className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-4 bg-brand-500 rounded-r-full"
                          transition={{ type: "spring", bounce: 0.1, duration: 0.5 }}
                        />
                      )}
                      
                      <Icon size={16} className={isActive ? 'text-brand-500' : 'text-slate-400 group-hover:text-slate-500'} />
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
    </aside>
  );

  // Mobile navigation toggle button (shown when sidebar is hidden)
  const mobileNavToggle = isDocsPage && (
    <button
      onClick={() => setMobileNavOpen(true)}
      className="md:hidden fixed bottom-6 left-6 z-40 flex items-center gap-2 px-4 py-3 bg-brand-600 text-white rounded-full shadow-lg shadow-brand-500/30 hover:bg-brand-500 transition-colors"
      aria-label="Open documentation navigation"
    >
      <ChevronRight size={20} className="rotate-180" />
      <span className="text-sm font-medium">Docs Menu</span>
    </button>
  );

  // Mobile navigation overlay
  const mobileNavOverlay = mobileNavOpen && (
    <div className="md:hidden fixed inset-0 z-50">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={() => setMobileNavOpen(false)}
        aria-hidden="true"
      />
      
      {/* Mobile sidebar */}
      <motion.aside
        initial={{ x: '-100%' }}
        animate={{ x: 0 }}
        exit={{ x: '-100%' }}
        transition={{ type: 'spring', bounce: 0.1, duration: 0.4 }}
        className="absolute left-0 top-0 h-full w-72 bg-white dark:bg-slate-950 border-r border-slate-200 dark:border-slate-800 shadow-xl"
        role="dialog"
        aria-label="Documentation navigation"
      >
        <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-800">
          <h2 className="font-semibold text-lg">Documentation</h2>
          <button
            onClick={() => setMobileNavOpen(false)}
            className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            aria-label="Close navigation"
          >
            <X size={20} />
          </button>
        </div>
        
        <nav className="p-4 space-y-6 overflow-y-auto h-[calc(100%-4rem)]">
          {navItems.map((group, idx) => (
            <div key={idx}>
              <h4 className="font-semibold text-xs tracking-wider text-slate-500 uppercase mb-3">
                {group.section}
              </h4>
              <ul className="space-y-1">
                {group.items.map((item) => {
                  const isActive = location.pathname === item.path;
                  const Icon = item.icon;
                  
                  return (
                    <li key={item.path}>
                      <Link
                        to={item.path}
                        onClick={() => setMobileNavOpen(false)}
                        className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                          isActive 
                            ? 'text-brand-600 dark:text-brand-400 bg-brand-50 dark:bg-brand-900/20' 
                            : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/50'
                        }`}
                      >
                        <Icon size={16} className={isActive ? 'text-brand-500' : 'text-slate-400'} />
                        {item.label}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
      </motion.aside>
    </div>
  );

  return (
    <>
      {desktopSidebar}
      {mobileNavToggle}
      {mobileNavOverlay}
    </>
  );
};

export default Sidebar;
