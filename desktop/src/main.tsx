import { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ContinuityPage } from './pages/Continuity';
import { KernelPage } from './pages/Kernel';
import { OrganismPage } from './pages/Organism';
import { OverviewPage } from './pages/Overview';
import { VoicePage } from './pages/Voice';
import './styles.css';

type View = 'home' | 'kernel' | 'continuity' | 'organism' | 'voice';

function App() {
  const [view, setView] = useState<View>('home');

  return (
    <main className="shell">
      <nav className="topNav" aria-label="Mission control navigation">
        <button type="button" className={view === 'home' ? 'active' : ''} onClick={() => setView('home')}>
          Overview
        </button>
        <button type="button" className={view === 'kernel' ? 'active' : ''} onClick={() => setView('kernel')}>
          Cognitive Kernel
        </button>
        <button type="button" className={view === 'continuity' ? 'active' : ''} onClick={() => setView('continuity')}>
          Continuity
        </button>
        <button type="button" className={view === 'organism' ? 'active' : ''} onClick={() => setView('organism')}>
          Organism
        </button>
        <button type="button" className={view === 'voice' ? 'active' : ''} onClick={() => setView('voice')}>
          Voice
        </button>
      </nav>
      {view === 'home' ? <OverviewPage onOpenVoice={() => setView('voice')} /> : null}
      {view === 'kernel' ? <KernelPage /> : null}
      {view === 'continuity' ? <ContinuityPage /> : null}
      {view === 'organism' ? <OrganismPage /> : null}
      {view === 'voice' ? <VoicePage /> : null}
    </main>
  );
}

createRoot(document.getElementById('root') as HTMLElement).render(<App />);
