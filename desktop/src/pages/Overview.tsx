import { useEffect, useState } from 'react';

type Card = {
  title: string;
  path: string;
  view?: string;
  signal: string;
  detail: string;
};

type ChatReply = {
  message: string;
  provider: string;
  model_id: string;
  local_fallback: boolean;
  deterministic: boolean;
};

type RecallHit = {
  record_id: string;
  content: string;
  score: number;
};

async function readJson(path: string): Promise<unknown> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`${path} returned HTTP ${response.status}`);
  }
  return response.json();
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {};
}

function summarize(path: string, payload: unknown): { signal: string; detail: string } {
  const body = asRecord(payload);
  const data = asRecord(body.data);
  if (path === '/health') {
    return { signal: String(body.status || 'offline'), detail: `runtime ${String(body.runtime_id || '')}` };
  }
  if (path === '/runtime/status') {
    const agents = Array.isArray(body.agents) ? body.agents.length : 0;
    return {
      signal: String(body.state || 'ready'),
      detail: `${agents} agents · continuity ${String(body.continuity || 'unknown')} · organism ${String(body.memory_organism || 'unknown')}`,
    };
  }
  if (path === '/agents/status') {
    return { signal: `${String(data.count ?? 0)} agents`, detail: 'Live registry' };
  }
  if (path === '/models') {
    const health = asRecord(data.health);
    const providers = asRecord(health.providers);
    const cloud = asRecord(providers.cloud);
    const ollama = asRecord(providers.ollama);
    const ollamaUp = ollama.reachable === true || ollama.available === true;
    return {
      signal: String(health.active_provider || 'local'),
      detail: `local deterministic · ollama ${ollamaUp ? 'reachable' : 'unreachable'} · cloud ${cloud.enabled === false ? 'disabled' : 'enabled'}`,
    };
  }
  if (path === '/tools/status') {
    return {
      signal: `${String(data.available ?? 0)} available`,
      detail: `${String(data.approval_gated ?? 0)} approval-gated · status only`,
    };
  }
  if (path === '/workspaces/status') {
    return { signal: 'sqlite', detail: String(body.detail || 'workspace store') };
  }
  if (path === '/memory/status') {
    const scopes = asRecord(body.scopes);
    const total = Object.values(scopes).reduce<number>(
      (sum, value) => sum + (typeof value === 'number' ? value : 0),
      0,
    );
    const scoreNote = body.scores_calibrated === false ? 'Vector scores are uncalibrated' : 'Scoped memory is in process';
    return { signal: `${total} records`, detail: scoreNote };
  }
  if (path === '/security/status') {
    return {
      signal: body.autonomy_kill_switch ? 'kill switch on' : 'kill switch off',
      detail: body.risky_actions_require_permission ? 'Risky actions need approval' : 'Review policy',
    };
  }
  if (path === '/self-model/status') {
    const limitations = Array.isArray(data.limitations) ? data.limitations.length : 0;
    return { signal: 'simulated', detail: `${limitations} known limitations` };
  }
  if (path === '/metacognition/status') {
    return { signal: data.last_review ? 'reviewed' : 'ready', detail: 'Reflection stays internal' };
  }
  if (path === '/dreaming/status') {
    return {
      signal: data.blocks_shell ? 'no external actions' : 'check guard',
      detail: `${Array.isArray(data.last_notes) ? data.last_notes.length : 0} dream notes`,
    };
  }
  if (path === '/idle-cognition/status') {
    return {
      signal: data.can_run_cycle ? 'can run' : 'paused',
      detail: 'Idle cycles do not leave the process',
    };
  }
  if (path === '/kernel/continuity') {
    return { signal: String(body.status || 'unavailable'), detail: String(body.reason || body.capability || 'journal') };
  }
  if (path === '/organism/status') {
    return { signal: String(body.status || 'unavailable'), detail: String(body.reason || 'memory organism') };
  }
  if (path === '/voice/status') {
    return {
      signal: body.synthetic_identity ? 'synthetic' : 'check identity',
      detail: 'No real-person cloning',
    };
  }
  return { signal: 'ready', detail: path };
}

const SOURCES: Array<{ title: string; path: string; view?: string }> = [
  { title: 'Runtime', path: '/runtime/status' },
  { title: 'Agents', path: '/agents/status', view: 'agents' },
  { title: 'Models', path: '/models', view: 'models' },
  { title: 'Tools', path: '/tools/status', view: 'tools' },
  { title: 'Workspaces', path: '/workspaces/status', view: 'workspaces' },
  { title: 'Memory', path: '/memory/status', view: 'memory' },
  { title: 'Security', path: '/security/status', view: 'security' },
  { title: 'Self-Model', path: '/self-model/status', view: 'self-model' },
  { title: 'Metacognition', path: '/metacognition/status', view: 'metacognition' },
  { title: 'Dreaming', path: '/dreaming/status', view: 'dreaming' },
  { title: 'Idle Cognition', path: '/idle-cognition/status', view: 'dreaming' },
  { title: 'Continuity', path: '/kernel/continuity', view: 'continuity' },
  { title: 'Organism', path: '/organism/status', view: 'organism' },
  { title: 'Voice', path: '/voice/status', view: 'voice' },
];

export function OverviewPage({
  onOpenVoice,
  onOpenSurface,
}: {
  onOpenVoice: () => void;
  onOpenSurface: (view: string) => void;
}) {
  const [cards, setCards] = useState<Card[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [chatText, setChatText] = useState('Plan a local-first assistant checklist');
  const [chatReply, setChatReply] = useState<ChatReply | null>(null);
  const [memoryText, setMemoryText] = useState('Hydrostatic bearing prefers local notes');
  const [recallQuery, setRecallQuery] = useState('hydrostatic');
  const [hits, setHits] = useState<RecallHit[]>([]);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const loaded = await Promise.all(
      SOURCES.map(async (source) => {
        try {
          const payload = await readJson(source.path);
          const summary = summarize(source.path, payload);
          return { title: source.title, path: source.path, view: source.view, ...summary };
        } catch (err) {
          return {
            title: source.title,
            path: source.path,
            view: source.view,
            signal: 'offline',
            detail: err instanceof Error ? err.message : 'unavailable',
          };
        }
      }),
    );
    setCards(loaded);
    setError(loaded.every((card) => card.signal === 'offline') ? 'API is not reachable on port 8000.' : null);
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function sendChat() {
    setBusy(true);
    try {
      const response = await fetch('/chat', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ message: chatText }),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      setChatReply((await response.json()) as ChatReply);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Chat failed');
    } finally {
      setBusy(false);
    }
  }

  async function rememberAndRecall() {
    setBusy(true);
    try {
      const written = await fetch('/memory', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ content: memoryText, scope: 'project', owner_id: 'local' }),
      });
      if (!written.ok) {
        throw new Error(await written.text());
      }
      const recalled = await fetch('/memory/recall', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ query: recallQuery, owner_id: 'local' }),
      });
      if (!recalled.ok) {
        throw new Error(await recalled.text());
      }
      setHits((await recalled.json()) as RecallHit[]);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Memory recall failed');
    } finally {
      setBusy(false);
    }
  }

  async function runDream() {
    setBusy(true);
    try {
      const response = await fetch('/dreaming/cycle', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ future_goal: 'rehearse a local backup' }),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Dream cycle failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <section className="hero">
        <p className="eyebrow">GAIA Mission Control</p>
        <h1>Local-first autonomous intelligence workstation</h1>
        <p>
          Live status from the local runtime. Cloud model calls stay disabled, and voice output stays synthetic.
        </p>
      </section>
      {error ? <p className="kernelError">{error}</p> : null}
      <section className="grid" aria-label="Live mission-control panels">
        {cards.map((card) => {
          const content = (
            <>
              <div className="panelHeader">
                <h2>{card.title}</h2>
                <span>{card.signal}</span>
              </div>
              <p>{card.detail}</p>
            </>
          );
          if (!card.view) {
            return (
              <article className="panel" key={card.path}>
                {content}
              </article>
            );
          }
          return (
            <button
              type="button"
              className="panel panelButton"
              key={card.path}
              onClick={() => onOpenSurface(card.view || '')}
            >
              {content}
            </button>
          );
        })}
      </section>
      <section className="kernelWorkbench overviewActions">
        <article className="kernelPanel">
          <div className="panelHeader">
            <h2>Chat</h2>
            <span>{chatReply ? chatReply.provider : 'local'}</span>
          </div>
          <textarea
            aria-label="Chat message"
            rows={4}
            value={chatText}
            onChange={(event) => setChatText(event.target.value)}
          />
          <div className="kernelActions">
            <button type="button" onClick={() => void sendChat()} disabled={busy}>
              Ask local model
            </button>
          </div>
          {chatReply ? (
            <div className="structuredResult">
              <p className="muted">
                {chatReply.model_id} · {chatReply.deterministic ? 'deterministic' : 'model'} ·{' '}
                {chatReply.local_fallback ? 'local fallback' : 'selected provider'}
              </p>
              <pre>{chatReply.message}</pre>
            </div>
          ) : null}
        </article>
        <article className="kernelPanel">
          <div className="panelHeader">
            <h2>Memory</h2>
            <span>{hits.length} hits</span>
          </div>
          <label className="fieldLabel" htmlFor="memory-note">
            Note
          </label>
          <textarea
            id="memory-note"
            rows={3}
            value={memoryText}
            onChange={(event) => setMemoryText(event.target.value)}
          />
          <label className="fieldLabel" htmlFor="memory-query">
            Recall query
          </label>
          <input
            id="memory-query"
            value={recallQuery}
            onChange={(event) => setRecallQuery(event.target.value)}
          />
          <div className="kernelActions">
            <button type="button" onClick={() => void rememberAndRecall()} disabled={busy}>
              Write and recall
            </button>
            <button type="button" onClick={() => void runDream()} disabled={busy}>
              Run dream cycle
            </button>
            <button type="button" onClick={onOpenVoice}>
              Open voice
            </button>
          </div>
          {hits.length ? (
            <ul className="goalList">
              {hits.map((hit) => (
                <li key={hit.record_id}>
                  <strong>{hit.score.toFixed(2)}</strong>
                  <span>{hit.content}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Write a note to recall it from scoped memory.</p>
          )}
        </article>
      </section>
    </>
  );
}
