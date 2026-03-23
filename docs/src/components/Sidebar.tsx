import { Link, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { BookOpen, Layers, Code2 } from 'lucide-react';

const Sidebar = () => {
  const location = useLocation();

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

  return (
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
};

export default Sidebar;
