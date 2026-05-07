import React from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

type Panel = {
  title: string;
  description: string;
  signal: string;
};

const panels: Panel[] = [
  { title: 'Chat', description: 'Operator conversation and streaming task handoff.', signal: 'online' },
  { title: 'Workspace', description: 'Project files, artifacts, and task history.', signal: 'local' },
  { title: 'Agents', description: 'Specialists, roles, queues, and delegation status.', signal: 'idle' },
  { title: 'Execution Graph', description: 'DAG planning, dependencies, retries, and traces.', signal: 'ready' },
  { title: 'Memory', description: 'Semantic, symbolic, project, user, and timeline recall.', signal: 'indexing' },
  { title: 'Models', description: 'Ollama-first routing with guarded cloud fallback.', signal: 'local-first' },
  { title: 'Security', description: 'Permissions, guards, audit log, secrets, and kill switch.', signal: 'armed' },
  { title: 'Self-Model', description: 'Capabilities, limitations, confidence, and uncertainty.', signal: 'observing' },
  { title: 'Metacognition', description: 'Review loops, contradiction checks, and risk estimates.', signal: 'reflecting' },
  { title: 'Dreaming', description: 'Idle replay, consolidation, and goal rehearsal.', signal: 'paused' },
  { title: 'Settings', description: 'Runtime, desktop, model, and policy configuration.', signal: 'editable' },
];

function App() {
  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">GAIA Mission Control</p>
        <h1>Local-first autonomous intelligence workstation</h1>
        <p>
          A Tauri + React + TypeScript shell for operating GAIA core modules with human-governed autonomy.
        </p>
      </section>
      <section className="grid" aria-label="Mission-control panels">
        {panels.map((panel) => (
          <article className="panel" key={panel.title}>
            <div className="panelHeader">
              <h2>{panel.title}</h2>
              <span>{panel.signal}</span>
            </div>
            <p>{panel.description}</p>
          </article>
        ))}
      </section>
    </main>
  );
}

createRoot(document.getElementById('root') as HTMLElement).render(<App />);
