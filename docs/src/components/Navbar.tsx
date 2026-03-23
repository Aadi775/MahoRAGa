import { Link, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Database, Globe, Menu } from 'lucide-react';

const Navbar = () => {
  const location = useLocation();

  return (
    <motion.nav 
      initial={{ y: -100 }}
      animate={{ y: 0 }}
      className="fixed top-0 w-full z-50 glass border-b shadow-sm dark:shadow-none"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          <Link to="/" className="flex items-center gap-2 group">
            <motion.div
              whileHover={{ rotate: 180 }}
              transition={{ duration: 0.3 }}
              className="bg-brand-500 text-white p-1.5 rounded-lg shadow-lg shadow-brand-500/30"
            >
              <Database size={24} />
            </motion.div>
            <span className="font-display font-bold text-xl tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-slate-900 to-slate-600 dark:from-white dark:to-slate-300">
              MahoRAGa
            </span>
          </Link>

          <div className="hidden md:flex space-x-8 items-center">
            {[
              { path: '/docs/getting-started', label: 'Docs' },
              { path: '/docs/architecture', label: 'Architecture' },
              { path: '/docs/api-reference', label: 'API' },
            ].map((link) => (
              <Link 
                key={link.path} 
                to={link.path}
                className="relative px-1 py-2 text-sm font-medium text-slate-600 hover:text-brand-600 dark:text-slate-300 dark:hover:text-white transition-colors"
              >
                {link.label}
                {location.pathname === link.path && (
                  <motion.div 
                    layoutId="navbar-underline"
                    className="absolute bottom-0 left-0 w-full h-0.5 bg-brand-500 rounded-full"
                    transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                  />
                )}
              </Link>
            ))}
            
            <div className="w-px h-6 bg-slate-200 dark:bg-slate-700 mx-2" />
            
            <a 
              href="https://github.com/aadi775/MahoRAGa" 
              target="_blank" 
              rel="noreferrer"
              className="text-slate-400 hover:text-slate-900 dark:hover:text-white transition-colors"
            >
              <Globe size={20} />
            </a>
          </div>

          <div className="md:hidden flex items-center">
            <button className="text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white">
              <Menu size={24} />
            </button>
          </div>
        </div>
      </div>
    </motion.nav>
  );
};

export default Navbar;
