import { useEffect, useState } from 'react';
import { getTools, type ToolStatus } from '../api/mission';
import { SurfaceFrame } from '../components/SurfaceFrame';

export function ToolsPage() {
  const [tools, setTools] = useState<ToolStatus[]>([]);
  const [execution, setExecution] = useState('status_only');
  const [gated, setGated] = useState(0);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      const payload = await getTools();
      setTools(payload.tools);
      setExecution(payload.execution);
      setGated(payload.approval_gated);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tool status failed');
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <SurfaceFrame
      label="Tools"
      eyebrow="Tool catalog"
      title="Permission status"
      lede="This page reviews availability. It does not execute a tool, open a shell, or touch the network."
      signal={execution}
      error={error}
    >
      <section className="kernelWorkbench">
        <article className="kernelPanel">
          <div className="panelHeader">
            <h2>Tools</h2>
            <span>{gated} approval-gated</span>
          </div>
          <ul className="goalList">
            {tools.map((tool) => (
              <li key={tool.name}>
                <strong>
                  {tool.name} · {tool.available ? 'available' : 'not available'}
                </strong>
                <span>{tool.description}</span>
                <span className="muted">
                  {tool.execution}
                  {tool.permission ? ` · ${tool.permission}` : ''}
                  {tool.requires_human_approval ? ' · human approval required' : ''}
                  {` · ${tool.reason}`}
                </span>
              </li>
            ))}
          </ul>
          <div className="kernelActions">
            <button type="button" onClick={() => void refresh()}>
              Refresh status
            </button>
          </div>
        </article>
        <article className="kernelPanel">
          <h2>Risky tools stay closed</h2>
          <p className="muted">
            Shell, network, and file writes remain approval-gated. A status refresh only re-reads
            the permission manager. It does not grant a permission.
          </p>
        </article>
      </section>
    </SurfaceFrame>
  );
}
