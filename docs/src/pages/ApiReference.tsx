import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Code, ChevronDown } from 'lucide-react';

const TOOLS = [
  {
    name: 'add_concept',
    desc: 'Add a new semantic concept to the knowledge graph. Re-embeds content automatically.',
    params: [
      { name: 'title', type: 'str', required: true, desc: 'Short title for the concept' },
      { name: 'content', type: 'str', required: true, desc: 'Detailed explanation of the concept' },
      { name: 'tags', type: 'list[str]', required: false, desc: 'List of tags for categorization' }
    ]
  },
  {
    name: 'search',
    desc: 'Search the knowledge graph using hybrid dense/keyword vectors and return ranked metrics.',
    params: [
      { name: 'query', type: 'str', required: true, desc: 'Natural language search query' },
      { name: 'top_k', type: 'int', required: false, desc: 'Number of top results to return (default 5)' }
    ]
  },
  {
    name: 'add_artifact',
    desc: 'Attach a file, snippet, or documentation log to the visual knowledge graph.',
    params: [
      { name: 'artifact_type', type: 'str', required: true, desc: 'Type of artifact (datasheet/config/etc)' },
      { name: 'title', type: 'str', required: true, desc: 'Document title' },
      { name: 'content', type: 'str', required: true, desc: 'Document string content' },
      { name: 'description', type: 'str', required: false, desc: 'Document summary' },
    ]
  },
  {
    name: 'delete_session',
    desc: 'Hard-deletes a session and safely garbage-collects all orphaned DailyActivity and Error nodes.',
    params: [
      { name: 'session_id', type: 'str', required: true, desc: 'UUID of the session to destroy' }
    ]
  }
];

const ApiReference = () => {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.5 }}
      className="max-w-4xl mx-auto px-6 lg:px-12 py-16"
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="mb-8 p-3 inline-block bg-emerald-500/10 text-emerald-500 rounded-xl"
      >
        <Code size={32} />
      </motion.div>
      
      <h1 className="text-4xl md:text-5xl font-bold mb-6 tracking-tight text-slate-900 dark:text-white">
        API Reference
      </h1>
      
      <p className="text-lg leading-relaxed text-slate-600 dark:text-slate-300 mb-12">
        MahoRAGa surfaces standard tools over the MCP (Model Context Protocol). Below is a reference of the most critical tools exposed to the agent.
      </p>

      <div className="space-y-4">
        {TOOLS.map((tool, idx) => {
          const isOpen = openIndex === idx;
          return (
            <motion.div 
              key={idx}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: idx * 0.1 }}
              className="glass border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden"
            >
              <button
                onClick={() => setOpenIndex(isOpen ? null : idx)}
                className="w-full flex items-center justify-between p-6 bg-white/50 dark:bg-slate-900/50 hover:bg-slate-50 dark:hover:bg-slate-800/80 transition-colors"
              >
                <div className="flex items-center gap-4">
                  <span className="font-mono font-bold text-lg text-brand-600 dark:text-brand-400">
                    {tool.name}
                  </span>
                </div>
                <motion.div
                  animate={{ rotate: isOpen ? 180 : 0 }}
                  transition={{ type: 'spring', bounce: 0.4 }}
                  className="text-slate-400"
                >
                  <ChevronDown size={20} />
                </motion.div>
              </button>

              <AnimatePresence>
                {isOpen && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.3, ease: 'easeInOut' }}
                  >
                    <div className="p-6 border-t border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50">
                      <p className="text-slate-600 dark:text-slate-300 leading-relaxed mb-6">
                        {tool.desc}
                      </p>
                      
                      <h4 className="font-semibold text-sm tracking-widest text-slate-500 uppercase mb-4">
                        Parameters
                      </h4>
                      <div className="space-y-3">
                        {tool.params.map((param, pIdx) => (
                          <div key={pIdx} className="flex flex-col sm:flex-row sm:items-baseline gap-2 sm:gap-4 p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                            <div className="flex items-center gap-2 min-w-[140px]">
                              <span className="font-mono text-sm font-semibold text-slate-800 dark:text-slate-200">
                                {param.name}
                              </span>
                              {param.required ? (
                                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-red-100 text-red-600 dark:bg-red-500/20 dark:text-red-400 uppercase tracking-wider">
                                  Req
                                </span>
                              ) : (
                                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 uppercase tracking-wider">
                                  Opt
                                </span>
                              )}
                            </div>
                            <code className="text-xs text-brand-500 dark:text-brand-400 min-w-[80px]">
                              {param.type}
                            </code>
                            <span className="text-sm text-slate-600 dark:text-slate-400">
                              {param.desc}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          );
        })}
      </div>
    </motion.div>
  );
};

export default ApiReference;
