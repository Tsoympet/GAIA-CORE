import { useEffect, useState } from 'react';
import { getTools, runTool, type ToolRunResult, type ToolStatus } from '../api/mission';
import { SurfaceFrame } from '../components/SurfaceFrame';

export function ToolsPage() {
  const [tools, setTools] = useState<ToolStatus[]>([]);
  const [execution, setExecution] = useState('status_only');
  const [gated, setGated] = useState(0);
  const [echoText, setEchoText] = useState('mission-control clock check');
  const [result, setResult] = useState<ToolRunResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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

  const clock = tools.find((tool) => tool.name === 'local_clock' && tool.executable);

  async function runClock() {
    setBusy(true);
    try {
      const next = await runTool('local_clock', echoText.trim());
      setResult(next);
      setError(null);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : 'Tool run failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <SurfaceFrame
      label="Tools"
      eyebrow="Tool catalog"
      title="Permission status"
      lede="Status stays read-only. The local clock can echo a note and read UTC time. Shell, network, and file tools stay closed."
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
                  {tool.executable ? ' · safe to run' : ' · not executed'}
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
          <h2>Local clock</h2>
          <p className="muted">
            This read does not open a shell, touch a file, or use the network. Risky tools have no
            run button.
          </p>
          <label className="fieldLabel" htmlFor="tool-echo-text">
            Note to echo
          </label>
          <input
            id="tool-echo-text"
            value={echoText}
            onChange={(event) => setEchoText(event.target.value)}
          />
          <div className="kernelActions">
            <button
              id="tool-run-local-clock"
              type="button"
              onClick={() => void runClock()}
              disabled={busy || !clock}
            >
              Run local clock
            </button>
          </div>
          {result ? (
            <pre id="tool-run-result" className="structuredResult">
              {JSON.stringify(result, null, 2)}
            </pre>
          ) : (
            <p className="muted">No safe tool has been run in this view yet.</p>
          )}
        </article>
      </section>
    </SurfaceFrame>
  );
}
