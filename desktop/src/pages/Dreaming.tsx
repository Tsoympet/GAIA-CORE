import { useEffect, useState } from 'react';
import { getDreamStatus, getIdleStatus, runDream } from '../api/mission';
import { SurfaceFrame } from '../components/SurfaceFrame';

export function DreamingPage() {
  const [goal, setGoal] = useState('rehearse a local backup');
  const [notes, setNotes] = useState<string[]>([]);
  const [blocksShell, setBlocksShell] = useState(true);
  const [idleReady, setIdleReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const [dream, idle] = await Promise.all([getDreamStatus(), getIdleStatus()]);
    setBlocksShell(dream.blocks_shell);
    setIdleReady(idle.can_run_cycle);
    if (dream.last_notes.length) {
      setNotes(dream.last_notes);
    }
  }

  useEffect(() => {
    void refresh().catch((err: unknown) => {
      setError(err instanceof Error ? err.message : 'Dream status failed');
    });
  }, []);

  async function cycle() {
    setBusy(true);
    try {
      setNotes(await runDream(goal.trim()));
      await refresh();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Dream cycle failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <SurfaceFrame
      label="Dreaming"
      eyebrow="Idle cognition"
      title="Internal notes only"
      lede="A dream cycle stores internal notes in the local journal. It does not run shell commands, browse, or edit project files."
      signal={blocksShell ? 'no external actions' : 'guard check'}
      error={error}
    >
      <section className="kernelWorkbench">
        <article className="kernelPanel">
          <label className="fieldLabel" htmlFor="dream-goal">
            Future goal
          </label>
          <textarea
            id="dream-goal"
            rows={3}
            value={goal}
            onChange={(event) => setGoal(event.target.value)}
          />
          <div className="kernelActions">
            <button type="button" onClick={() => void cycle()} disabled={busy || !goal.trim()}>
              Run dream cycle
            </button>
          </div>
          <p className="muted">Idle scheduler {idleReady ? 'can run a cycle' : 'is paused'}.</p>
        </article>
        <article className="kernelPanel">
          <div className="panelHeader">
            <h2>Notes</h2>
            <span>{notes.length}</span>
          </div>
          {notes.length ? (
            <ul className="goalList">
              {notes.map((note, index) => (
                <li key={`${index}-${note.slice(0, 32)}`}>
                  <span>{note}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No dream notes have been stored in this process yet.</p>
          )}
        </article>
      </section>
    </SurfaceFrame>
  );
}
