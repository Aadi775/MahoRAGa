import { motion } from 'framer-motion';
import { Layers, Database, Cpu, Search } from 'lucide-react';

const Architecture = () => {
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
        className="mb-8 p-3 inline-block bg-purple-500/10 text-purple-500 rounded-xl"
      >
        <Layers size={32} />
      </motion.div>
      
      <h1 className="text-4xl md:text-5xl font-bold mb-6 tracking-tight text-slate-900 dark:text-white">
        Architecture
      </h1>
      
      <p className="text-lg leading-relaxed text-slate-600 dark:text-slate-300 mb-12">
        MahoRAGa is designed to be a completely self-contained, heavily optimized graph intelligence server exposing standard MCP tools.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-16">
        {[
          { icon: Database, color: 'text-blue-500', bg: 'bg-blue-500/10', title: 'Kuzu Graph Engine', desc: 'At the heart is Kuzu graph DB. It utilizes structured nodes (Sessions, Concepts, Errors) and edges (REFERENCES, OCCURRED_IN) for complex logic.' },
          { icon: Cpu, color: 'text-green-500', bg: 'bg-green-500/10', title: 'FastMCP Server', desc: 'Interfaces via FastMCP, allowing any Anthropic/MCP-compliant LLM to discover and execute queries over standard IO securely.' },
          { icon: Search, color: 'text-amber-500', bg: 'bg-amber-500/10', title: 'Dense Vectors', desc: 'SentenceTransformers embed chunks of data, permitting mathematical O(N) cosine similarity matching for fuzzy lookups.' },
          { icon: Layers, color: 'text-purple-500', bg: 'bg-purple-500/10', title: 'Cascade Integrity', desc: 'Strict referential integrity ensures massive trees of dependent sessions and artifacts can be safely pruned to prevent memory bloat.' }
        ].map((item, i) => (
          <motion.div 
            key={i}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.1 }}
            className="p-6 glass rounded-2xl border border-slate-200 dark:border-slate-800"
          >
            <div className={`mb-4 w-12 h-12 rounded-xl flex items-center justify-center ${item.bg} ${item.color}`}>
              <item.icon size={24} />
            </div>
            <h3 className="text-xl font-bold mb-2 text-slate-900 dark:text-white">{item.title}</h3>
            <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed">{item.desc}</p>
          </motion.div>
        ))}
      </div>

      <div className="prose prose-slate dark:prose-invert max-w-none">
        <h2>Data Model</h2>
        <p>
          The graph schema revolves around several core entities linked functionally:
        </p>
        <ul>
          <li><strong>Project:</strong> A logical container for sessions.</li>
          <li><strong>Session:</strong> A specific coding task or interaction block. Generates errors, solutions, and logs.</li>
          <li><strong>Error / Solution:</strong> Tracked problems that the Agent encountered locally.</li>
          <li><strong>Concept:</strong> Semantic knowledge nodes. Cross-linked globally across completely disparate Projects.</li>
          <li><strong>Artifact:</strong> Physical files or logs. Linked to Sessions via <code>USES_ARTIFACT</code>, and errors via <code>ATTACHED_TO</code>.</li>
        </ul>
      </div>
    </motion.div>
  );
};

export default Architecture;
