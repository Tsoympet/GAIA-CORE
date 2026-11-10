import { useEffect, useState } from 'react';
import { createWorkspace, listWorkspaces, type WorkspaceRecord } from '../api/mission';
import { SurfaceFrame } from '../components/SurfaceFrame';

export function WorkspacesPage() {
  const [workspaces, setWorkspaces] = useState<WorkspaceRecord[]>([]);
  const [name, setName] = useState('Bench workspace');
  const [description, setDescription] = useState('Local notes for this machine');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      setWorkspaces(await listWorkspaces());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Workspace list failed');
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function submit() {
    setBusy(true);
    try {
      await createWorkspace(name.trim(), description.trim());
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Workspace create failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <SurfaceFrame
      label="Workspaces"
      eyebrow="Local SQLite"
      title="Workspaces"
      lede="Create and list workspace records stored on this machine. This is metadata, not a project graph."
      signal={`${workspaces.length} stored`}
      error={error}
    >
      <section className="kernelWorkbench">
        <article className="kernelPanel">
          <label className="fieldLabel" htmlFor="workspace-name">
            Name
          </label>
          <input id="workspace-name" value={name} onChange={(event) => setName(event.target.value)} />
          <label className="fieldLabel" htmlFor="workspace-description">
            Description
          </label>
          <textarea
            id="workspace-description"
            rows={3}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
          <div className="kernelActions">
            <button type="button" onClick={() => void submit()} disabled={busy || !name.trim()}>
              Create workspace
            </button>
            <button type="button" onClick={() => void refresh()} disabled={busy}>
              Refresh list
            </button>
          </div>
        </article>
        <article className="kernelPanel">
          <div className="panelHeader">
            <h2>Stored workspaces</h2>
            <span>sqlite</span>
          </div>
          {workspaces.length ? (
            <ul className="goalList">
              {workspaces.map((workspace) => (
                <li key={workspace.workspace_id}>
                  <strong>{workspace.name}</strong>
                  <span>{workspace.description || 'No description'}</span>
                  <span className="muted">{workspace.workspace_id}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No workspace has been created in this store yet.</p>
          )}
        </article>
      </section>
    </SurfaceFrame>
  );
}
