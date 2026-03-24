import { motion } from 'framer-motion';
import { Terminal } from 'lucide-react';

const CodeBlock = ({ code, language }: { code: string, language: string }) => (
  <div className="relative mt-4 mb-8 group rounded-xl bg-slate-900 border border-slate-700 overflow-hidden shadow-xl shadow-black/20">
    <div className="flex items-center px-4 py-2 bg-slate-800/80 border-b border-slate-700/50">
      <div className="flex gap-2">
        <div className="w-3 h-3 rounded-full bg-red-500/80" />
        <div className="w-3 h-3 rounded-full bg-amber-500/80" />
        <div className="w-3 h-3 rounded-full bg-green-500/80" />
      </div>
      <span className="ml-4 text-xs font-mono text-slate-400 capitalize">{language}</span>
    </div>
    <div className="p-5 overflow-x-auto">
      <pre className="text-sm font-mono text-slate-300 leading-relaxed">
        <code>{code}</code>
      </pre>
    </div>
  </div>
);

const GettingStarted = () => {
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
        className="mb-8 p-3 inline-block bg-brand-500/10 text-brand-500 rounded-xl"
      >
        <Terminal size={32} />
      </motion.div>
      
      <h1 className="text-4xl md:text-5xl font-bold mb-6 tracking-tight text-slate-900 dark:text-white">
        Getting Started
      </h1>
      
      <div className="prose prose-slate dark:prose-invert max-w-none text-slate-600 dark:text-slate-300">
        <p className="text-lg leading-relaxed mb-12">
          MahoRAGa is an agentic Knowledge Graph system. Deploying the local server allows any MCP-compatible Claude/Agent client to natively manipulate your project memory space using the standard stdio protocol.
        </p>

        <h2 className="text-2xl font-bold mt-12 mb-4 text-slate-900 dark:text-white flex items-center gap-3">
          <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-slate-100 dark:bg-slate-800 text-sm">1</span>
          Requirements
        </h2>
        <ul className="list-none space-y-4 mb-12 pl-11">
          <li className="flex items-start gap-2">
            <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-brand-500 shrink-0" />
            <span>Python 3.11 or higher installed on your system.</span>
          </li>
          <li className="flex items-start gap-2">
            <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-brand-500 shrink-0" />
            <span>Basic familiarity with MCP (Model Context Protocol).</span>
          </li>
        </ul>

        <h2 className="text-2xl font-bold mt-12 mb-4 text-slate-900 dark:text-white flex items-center gap-3">
          <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-slate-100 dark:bg-slate-800 text-sm">2</span>
          Quick Start (Mac/Linux)
        </h2>
        <p className="mb-4 pl-11">Use the provided shell configuration script to automatically set up your entire virtual environment and dependencies.</p>
        
        <div className="pl-11">
          <CodeBlock 
            language="bash"
            code={`# Ensure the script is executable
chmod +x setup.sh

# Run the setup script
./setup.sh`}
          />
        </div>

        <h2 className="text-2xl font-bold mt-12 mb-4 text-slate-900 dark:text-white flex items-center gap-3">
          <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-slate-100 dark:bg-slate-800 text-sm">3</span>
          Quick Start (Windows)
        </h2>
        <p className="mb-4 pl-11">If you are using a Windows native environment, use the `.bat` provided instead.</p>
        
        <div className="pl-11">
          <CodeBlock 
            language="cmd"
            code={`cd path\\to\\MahoRAGa
setup.bat`}
          />
        </div>

        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mt-16 p-8 glass rounded-2xl border border-brand-500/20 bg-gradient-to-br from-brand-500/5 to-purple-500/5"
        >
          <h3 className="font-bold text-xl text-slate-900 dark:text-white mb-3">Connecting to Claude Desktop (Single Client)</h3>
          <p className="text-slate-600 dark:text-slate-300 leading-relaxed mb-6">
            By default, MahoRAGa uses <code>stdio</code> transport. This is perfect for a single client, as Kùzu database uses file-level locking.
          </p>
          <CodeBlock 
            language="json"
            code={`{
  "mcpServers": {
    "mahoraga": {
      "command": "/path/to/MahoRAGa/.venv/bin/mahoraga-kg"
    }
  }
}`}
          />
        </motion.div>

        <h2 className="text-2xl font-bold mt-16 mb-4 text-slate-900 dark:text-white flex items-center gap-3">
          <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-brand-500/20 text-brand-600 dark:text-brand-400 text-sm">4</span>
          Advanced: Multiple Clients (SSE Shared Server)
        </h2>
        <p className="mb-4 pl-11">
          If you want to access the exact same MahoRAGa database from <strong>multiple clients at the same time</strong> (e.g. Claude Desktop AND Cursor), you must run MahoRAGa as a shared HTTP server.
        </p>
        <div className="pl-11">
          <CodeBlock 
            language="bash"
            code={`# Start the shared server manually in a terminal
mahoraga-kg --transport sse --port 8000`}
          />
          <p className="text-slate-600 dark:text-slate-300 mt-4 mb-4">Then, configure your MCP clients to connect to the SSE endpoint instead of launching their own process:</p>
          <CodeBlock 
            language="json"
            code={`{
  "mcpServers": {
    "mahoraga-remote": {
      "command": "curl",
      "args": [],
      "type": "sse",
      "url": "http://localhost:8000/sse"
    }
  }
}`}
          />
        </div>
      </div>
    </motion.div>
  );
};

export default GettingStarted;
