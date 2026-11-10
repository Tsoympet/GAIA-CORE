import { useEffect, useState } from 'react';
import { listGoals, type KernelGoal } from '../api/kernel';
import {
  attachWorkspaceLink,
  createWorkspace,
  listWorkspaces,
  reviewMemory,
  type WorkspaceRecord,
} from '../api/mission';
import { SurfaceFrame } from '../components/SurfaceFrame';

type KnownRef = {
  kind: 'task' | 'memory';
  id: string;
  label: string;
};

export function WorkspacesPage() {
  const [workspaces, setWorkspaces] = useState<WorkspaceRecord[]>([]);
  const [known, setKnown] = useState<KnownRef[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [name, setName] = useState('Bench workspace');
  const [description, setDescription] = useState('Local notes for this machine');
  const [kind, setKind] = useState<'task' | 'memory'>('memory');
  const [memoryOwner, setMemoryOwner] = useState('local');
  const [refId, setRefId] = useState('');
  const [label, setLabel] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh(preferId?: string) {
    try {
      const next = await listWorkspaces();
      setWorkspaces(next);
      setSelectedId((current) => {
        if (preferId && next.some((workspace) => workspace.workspace_id === preferId)) {
          return preferId;
        }
        if (current && next.some((workspace) => workspace.workspace_id === current)) {
          return current;
        }
        return next[0]?.workspace_id ?? '';
      });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Workspace list failed');
    }
  }

  async function loadKnown(owner: string) {
    const notes = await reviewMemory(owner.trim() || 'local');
    let goals: KernelGoal[] = [];
    try {
      goals = (await listGoals()).goals;
    } catch {
      goals = [];
    }
    setKnown([
      ...notes.map((note) => ({
        kind: 'memory' as const,
        id: note.record_id,
        label: note.content,
      })),
      ...goals.map((goal) => ({
        kind: 'task' as const,
        id: goal.id,
        label: goal.objective,
      })),
    ]);
  }

  useEffect(() => {
    void refresh();
    void loadKnown(memoryOwner).catch((err: unknown) => {
      setError(err instanceof Error ? err.message : 'Could not load references');
    });
  }, []);

  async function submit() {
    setBusy(true);
    try {
      const created = await createWorkspace(name.trim(), description.trim());
      await refresh(created.workspace_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Workspace create failed');
    } finally {
      setBusy(false);
    }
  }

  async function attach() {
    if (!selectedId) {
      setError('Create a workspace before attaching a reference');
      return;
    }
    setBusy(true);
    try {
      await attachWorkspaceLink(selectedId, kind, refId.trim(), label.trim());
      await refresh(selectedId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Attach failed');
    } finally {
      setBusy(false);
    }
  }

  const selected = workspaces.find((workspace) => workspace.workspace_id === selectedId);

  return (
    <SurfaceFrame
      label="Workspaces"
      eyebrow="Local project"
      title="Workspaces"
      lede="Create a local workspace and attach a task or memory that already exists. An unknown id is rejected. A link whose target was removed later is marked missing."
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
          <label className="fieldLabel" htmlFor="workspace-target">
            Workspace
          </label>
          <select
            id="workspace-target"
            value={selectedId}
            onChange={(event) => setSelectedId(event.target.value)}
          >
            {workspaces.length ? null : <option value="">No workspace yet</option>}
            {workspaces.map((workspace) => (
              <option key={workspace.workspace_id} value={workspace.workspace_id}>
                {workspace.name}
              </option>
            ))}
          </select>
          <label className="fieldLabel" htmlFor="workspace-memory-owner">
            Memory owner
          </label>
          <input
            id="workspace-memory-owner"
            value={memoryOwner}
            onChange={(event) => setMemoryOwner(event.target.value)}
          />
          <div className="kernelActions">
            <button
              type="button"
              onClick={() =>
                void loadKnown(memoryOwner).catch((err: unknown) => {
                  setError(err instanceof Error ? err.message : 'Could not load references');
                })
              }
              disabled={busy}
            >
              Load references
            </button>
          </div>
          <label className="fieldLabel" htmlFor="workspace-known-ref">
            Known reference
          </label>
          <select
            id="workspace-known-ref"
            defaultValue=""
            onChange={(event) => {
              const picked = known.find((item) => `${item.kind}:${item.id}` === event.target.value);
              if (!picked) {
                return;
              }
              setKind(picked.kind);
              setRefId(picked.id);
              setLabel(picked.label.slice(0, 80));
              setError(null);
            }}
          >
            <option value="">Choose a stored memory or task</option>
            {known.map((item) => (
              <option key={`${item.kind}:${item.id}`} value={`${item.kind}:${item.id}`}>
                {item.kind} · {item.label.slice(0, 60)}
              </option>
            ))}
          </select>
          <label className="fieldLabel" htmlFor="workspace-link-kind">
            Link kind
          </label>
          <select
            id="workspace-link-kind"
            value={kind}
            onChange={(event) => setKind(event.target.value === 'task' ? 'task' : 'memory')}
          >
            <option value="memory">memory</option>
            <option value="task">task</option>
          </select>
          <label className="fieldLabel" htmlFor="workspace-link-ref">
            Reference id
          </label>
          <input
            id="workspace-link-ref"
            value={refId}
            onChange={(event) => setRefId(event.target.value)}
          />
          <label className="fieldLabel" htmlFor="workspace-link-label">
            Label
          </label>
          <input
            id="workspace-link-label"
            value={label}
            onChange={(event) => setLabel(event.target.value)}
          />
          <div className="kernelActions">
            <button
              type="button"
              onClick={() => void attach()}
              disabled={busy || !selectedId || !refId.trim()}
            >
              Attach reference
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
                  {(workspace.links ?? []).length ? (
                    <ul className="goalList">
                      {workspace.links.map((link) => (
                        <li key={link.link_id}>
                          <strong>
                            {link.kind} · {link.label || link.ref_id}
                          </strong>
                          <span className={link.target_exists ? 'muted' : 'linkMissing'}>
                            {link.target_exists ? 'target present' : 'target missing'}
                          </span>
                          <span className="muted">{link.ref_id}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <span className="muted">No linked task or memory yet.</span>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No workspace has been created in this store yet.</p>
          )}
          {selected ? (
            <p className="muted">
              Selected {selected.name} has {(selected.links ?? []).length} linked item
              {(selected.links ?? []).length === 1 ? '' : 's'}.
            </p>
          ) : null}
        </article>
      </section>
    </SurfaceFrame>
  );
}
