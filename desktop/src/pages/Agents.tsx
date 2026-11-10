import { useEffect, useState } from 'react';
import { getAgents, type AgentDescriptor } from '../api/mission';
import { SurfaceFrame } from '../components/SurfaceFrame';

export function AgentsPage() {
  const [agents, setAgents] = useState<AgentDescriptor[]>([]);
  const [filter, setFilter] = useState('');
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setAgents(await getAgents());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Agent list failed');
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  const needle = filter.trim().toLowerCase();
  const visible = agents.filter((agent) => {
    if (!needle) {
      return true;
    }
    return (
      agent.name.toLowerCase().includes(needle) ||
      agent.description.toLowerCase().includes(needle) ||
      agent.capabilities.some((capability) => capability.includes(needle))
    );
  });

  return (
    <SurfaceFrame
      label="Agents"
      eyebrow="Agent registry"
      title="Registered specialists"
      lede="Live registry from this process. Listing an agent does not invoke it."
      signal={`${agents.length} agents`}
      error={error}
    >
      <section className="kernelWorkbench">
        <article className="kernelPanel">
          <label className="fieldLabel" htmlFor="agent-filter">
            Filter
          </label>
          <input
            id="agent-filter"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="memory, security, voice"
          />
          <div className="kernelActions">
            <button type="button" onClick={() => void refresh()}>
              Refresh list
            </button>
          </div>
        </article>
        <article className="kernelPanel">
          <div className="panelHeader">
            <h2>Agents</h2>
            <span>{visible.length} shown</span>
          </div>
          <ul className="goalList">
            {visible.map((agent) => (
              <li key={agent.name}>
                <strong>{agent.name}</strong>
                <span>{agent.description}</span>
                <span className="muted">
                  {agent.capabilities.join(', ') || 'no capabilities'}
                  {agent.requires_human_approval ? ' · approval required' : ''}
                </span>
              </li>
            ))}
          </ul>
        </article>
      </section>
    </SurfaceFrame>
  );
}
