import { useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { ArrowRight, Code, Zap, Database } from 'lucide-react';

gsap.registerPlugin(ScrollTrigger);

const Home = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // 2D Canvas Knowledge Graph Particles Background
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let particles: Particle[] = [];
    let animationFrameId: number;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    window.addEventListener('resize', resize);
    resize();

    const canvasEl = canvas;

    class Particle {
      x: number;
      y: number;
      vx: number;
      vy: number;
      radius: number;

      constructor() {
        this.x = Math.random() * canvasEl.width;
        this.y = Math.random() * canvasEl.height;
        this.vx = (Math.random() - 0.5) * 0.5;
        this.vy = (Math.random() - 0.5) * 0.5;
        this.radius = Math.random() * 2 + 1;
      }

      update() {
        this.x += this.vx;
        this.y += this.vy;

        if (this.x < 0 || this.x > canvasEl.width) this.vx *= -1;
        if (this.y < 0 || this.y > canvasEl.height) this.vy *= -1;
      }

      draw() {
        if (!ctx) return;
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(59, 130, 246, 0.4)';
        ctx.fill();
      }
    }

    const initParticles = () => {
      particles = [];
      const numParticles = Math.floor(window.innerWidth * window.innerHeight / 15000);
      for (let i = 0; i < numParticles; i++) {
        particles.push(new Particle());
      }
    };

    const animate = () => {
      ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);

      for (let i = 0; i < particles.length; i++) {
        particles[i].update();
        particles[i].draw();

        for (let j = i; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const distance = Math.sqrt(dx * dx + dy * dy);

          if (distance < 120) {
            ctx.beginPath();
            ctx.strokeStyle = `rgba(59, 130, 246, ${0.15 - distance / 800})`;
            ctx.lineWidth = 1;
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.stroke();
          }
        }
      }
      animationFrameId = requestAnimationFrame(animate);
    };

    initParticles();
    animate();

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  // GSAP Scroll Animations
  useEffect(() => {
    let ctx = gsap.context(() => {
      gsap.from('.gsap-fade-up', {
        y: 50,
        opacity: 0,
        duration: 1,
        stagger: 0.2,
        ease: 'power3.out',
        scrollTrigger: {
          trigger: '#features-section',
          start: 'top 80%',
        }
      });
    }, containerRef);
    
    return () => ctx.revert();
  }, []);

  return (
    <motion.div 
      ref={containerRef}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="relative min-h-screen w-full overflow-hidden"
    >
      <canvas 
        ref={canvasRef} 
        className="absolute inset-0 pointer-events-none z-0"
      />
      
      {/* Hero Section */}
      <section className="relative z-10 min-h-[90vh] flex flex-col justify-center items-center text-center px-4">
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass mb-8 text-sm font-medium text-brand-600 dark:text-brand-400"
        >
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-brand-500"></span>
          </span>
          Next-Gen Knowledge Graph System
        </motion.div>
        
        <motion.h1 
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.2, duration: 0.8 }}
          className="text-5xl md:text-7xl font-bold tracking-tight max-w-4xl mx-auto leading-tight"
        >
          The ultimate memory architecture for <br className="hidden md:block"/>
          <span className="text-gradient">AI Agents.</span>
        </motion.h1>
        
        <motion.p 
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.3, duration: 0.8 }}
          className="mt-6 text-xl text-slate-600 dark:text-slate-400 max-w-2xl mx-auto"
        >
          MahoRAGa combines Kuzu graph databases, vector embeddings, and MCP tools to provide an unmatched semantic reasoning layer.
        </motion.p>
        
        <motion.div 
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.4, duration: 0.8 }}
          className="mt-10 flex gap-4"
        >
          <Link 
            to="/docs/getting-started"
            className="group px-8 py-3 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-medium flex items-center gap-2 transition-all shadow-lg shadow-brand-500/25 hover:shadow-brand-500/40"
          >
            Get Started
            <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
          </Link>
          <a href="https://github.com/aadi775/MahoRAGa" target="_blank" rel="noreferrer"
            className="px-8 py-3 rounded-xl glass hover:bg-slate-100 dark:hover:bg-slate-800 font-medium transition-colors"
          >
            View GitHub
          </a>
        </motion.div>
      </section>

      {/* Features Section */}
      <section id="features-section" className="relative z-10 py-24 bg-white/50 dark:bg-slate-900/50 backdrop-blur-3xl border-t border-slate-200 dark:border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              { 
                icon: Database, 
                title: 'Graph Database Driven',
                desc: 'Built purely on Kuzu, exploiting complex graph traversals to track dependencies, errors, and solution semantics seamlessly.'
              },
              {
                icon: Zap,
                title: 'Vector Semantics',
                desc: 'Integrated SentenceTransformers provide automated, seamless encoding of notes and errors to perform zero-shot clustering.'
              },
              {
                icon: Code,
                title: 'MCP Ready',
                desc: 'Exposes its entire API directly via FastMCP as tools, allowing native integration with agentic frameworks over stdio/SSE.'
              }
            ].map((Feature, idx) => (
              <div key={idx} className="gsap-fade-up glass p-8 rounded-2xl flex flex-col items-start gap-4 hover:-translate-y-2 transition-transform duration-300">
                <div className="p-3 bg-brand-100 dark:bg-brand-900/30 text-brand-600 dark:text-brand-400 rounded-xl">
                  <Feature.icon size={28} />
                </div>
                <h3 className="text-xl font-bold">{Feature.title}</h3>
                <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
                  {Feature.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </motion.div>
  );
};

export default Home;
