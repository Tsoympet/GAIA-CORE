import { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { AgentsPage } from './pages/Agents';
import { ContinuityPage } from './pages/Continuity';
import { DreamingPage } from './pages/Dreaming';
import { KernelPage } from './pages/Kernel';
import { MemoryPage } from './pages/Memory';
import { MetacognitionPage } from './pages/Metacognition';
import { ModelsPage } from './pages/Models';
import { OrganismPage } from './pages/Organism';
import { OverviewPage } from './pages/Overview';
import { SecurityPage } from './pages/Security';
import { SelfModelPage } from './pages/SelfModel';
import { ToolsPage } from './pages/Tools';
import { VoicePage } from './pages/Voice';
import { WorkspacesPage } from './pages/Workspaces';
import './styles.css';

const VIEWS = [
  'home',
  'kernel',
  'continuity',
  'organism',
  'voice',
  'agents',
  'memory',
  'models',
  'tools',
  'workspaces',
  'security',
  'self-model',
  'metacognition',
  'dreaming',
] as const;

type View = (typeof VIEWS)[number];

function isView(value: string): value is View {
  return (VIEWS as readonly string[]).includes(value);
}

const PRIMARY: Array<{ id: View; label: string }> = [
  { id: 'home', label: 'Overview' },
  { id: 'kernel', label: 'Cognitive Kernel' },
  { id: 'continuity', label: 'Continuity' },
  { id: 'organism', label: 'Organism' },
  { id: 'voice', label: 'Voice' },
];

const FOUNDATION: Array<{ id: View; label: string }> = [
  { id: 'agents', label: 'Agents' },
  { id: 'memory', label: 'Memory' },
  { id: 'models', label: 'Models' },
  { id: 'tools', label: 'Tools' },
  { id: 'workspaces', label: 'Workspaces' },
  { id: 'security', label: 'Security' },
  { id: 'self-model', label: 'Self-Model' },
  { id: 'metacognition', label: 'Metacognition' },
  { id: 'dreaming', label: 'Dreaming' },
];

function App() {
  const [view, setView] = useState<View>('home');

  function openSurface(next: string) {
    if (isView(next)) {
      setView(next);
    }
  }

  return (
    <main className="shell">
      <nav className="topNav" aria-label="Mission control navigation">
        {PRIMARY.map((item) => (
          <button
            key={item.id}
            type="button"
            className={view === item.id ? 'active' : ''}
            onClick={() => setView(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>
      <nav className="topNav secondaryNav" aria-label="Foundation surfaces">
        {FOUNDATION.map((item) => (
          <button
            key={item.id}
            type="button"
            className={view === item.id ? 'active' : ''}
            onClick={() => setView(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>
      {view === 'home' ? (
        <OverviewPage onOpenVoice={() => setView('voice')} onOpenSurface={openSurface} />
      ) : null}
      {view === 'kernel' ? <KernelPage /> : null}
      {view === 'continuity' ? <ContinuityPage /> : null}
      {view === 'organism' ? <OrganismPage /> : null}
      {view === 'voice' ? <VoicePage /> : null}
      {view === 'agents' ? <AgentsPage /> : null}
      {view === 'memory' ? <MemoryPage /> : null}
      {view === 'models' ? <ModelsPage /> : null}
      {view === 'tools' ? <ToolsPage /> : null}
      {view === 'workspaces' ? <WorkspacesPage /> : null}
      {view === 'security' ? <SecurityPage /> : null}
      {view === 'self-model' ? <SelfModelPage /> : null}
      {view === 'metacognition' ? <MetacognitionPage /> : null}
      {view === 'dreaming' ? <DreamingPage /> : null}
    </main>
  );
}

createRoot(document.getElementById('root') as HTMLElement).render(<App />);
