import { useEffect, useState } from 'react';
import {
  getContinuitySnapshots,
  getContinuityStatus,
  listContinuityCheckpoints,
  listContinuityTasks,
  openContinuityEventStream,
  publishContinuityCheckpoint,
  verifyContinuityCheckpoint,
  type CheckpointSummary,
  type ContinuityEvent,
  type ContinuityStatus,
  type ContinuityTask,
  type EnvironmentReport,
  type VerifyResult,
} from '../api/continuity';

function shortId(value: string): string {
  return value.length > 12 ? `${value.slice(0, 8)}…` : value;
}

export function ContinuityPage() {
  const [status, setStatus] = useState<ContinuityStatus | null>(null);
  const [checkpoints, setCheckpoints] = useState<CheckpointSummary[]>([]);
  const [tasks, setTasks] = useState<ContinuityTask[]>([]);
  const [integrityOk, setIntegrityOk] = useState<boolean | null>(null);
  const [verify, setVerify] = useState<VerifyResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [events, setEvents] = useState<ContinuityEvent[]>([]);
  const [environment, setEnvironment] = useState<EnvironmentReport | null>(null);

  const journalReady = status?.status === 'available' || status?.status === 'degraded';

  async function refresh() {
    try {
      const nextStatus = await getContinuityStatus();
      setStatus(nextStatus);
      setError(null);
      if (nextStatus.status === 'unavailable') {
        setCheckpoints([]);
        setTasks([]);
        setIntegrityOk(null);
        setVerify(null);
        setEvents([]);
        setEnvironment(null);
        return;
      }
      const [nextCheckpoints, nextTasks, nextEnvironment] = await Promise.all([
        listContinuityCheckpoints(),
        listContinuityTasks(),
        getContinuitySnapshots(),
      ]);
      setCheckpoints(nextCheckpoints.checkpoints);
      setIntegrityOk(nextCheckpoints.integrity_ok);
      setTasks(nextTasks.tasks);
      setEnvironment(nextEnvironment);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load continuity');
    }
  }

  useEffect(() => {
    void refresh();
    const source = openContinuityEventStream((payload) => {
      if ('events' in payload && Array.isArray(payload.events)) {
        setEvents(payload.events);
        return;
      }
      setEvents((current) => [...current, payload as ContinuityEvent].slice(-50));
      void refresh();
    });
    setStreaming(true);
    source.onerror = () => setStreaming(false);
    return () => {
      source.close();
      setStreaming(false);
    };
  }, []);

  async function publish() {
    setBusy(true);
    try {
      await publishContinuityCheckpoint();
      setVerify(null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Publish failed');
    } finally {
      setBusy(false);
    }
  }

  async function verifyCheckpoint(checkpointId: string) {
    setBusy(true);
    try {
      const result = await verifyContinuityCheckpoint(checkpointId);
      setVerify(result);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verify failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="kernelPage" aria-label="Cognitive continuity journal">
      <header className="kernelHeader">
        <div>
          <p className="eyebrow">Cognitive Continuity</p>
          <h1>Local journal</h1>
          <p>Hash-linked checkpoints and task state. The chain is not cryptographic immutability.</p>
        </div>
        <div className="kernelSignals">
          <span>{status?.status || 'loading'}</span>
          <span>{status?.durable ? 'durable' : 'not configured'}</span>
          <span>{streaming ? 'streaming' : 'stream idle'}</span>
          <span>{integrityOk === null ? 'no chain' : integrityOk ? 'chain ok' : 'chain degraded'}</span>
        </div>
      </header>

      {error ? <p className="kernelError">{error}</p> : null}

      {status?.status === 'unavailable' ? (
        <p className="kernelError" role="status">
          {status.reason || 'Continuity store is not configured for this runtime.'}
        </p>
      ) : null}

      <div className="kernelMetrics">
        <article>
          <h3>Checkpoints</h3>
          <strong>{status?.checkpoint_count ?? checkpoints.length}</strong>
        </article>
        <article>
          <h3>Tasks</h3>
          <strong>{tasks.length}</strong>
        </article>
        <article>
          <h3>Schema</h3>
          <strong>{status?.schema_version ?? '—'}</strong>
        </article>
        <article>
          <h3>Integrity</h3>
          <strong>{status?.integrity || (integrityOk === null ? 'none' : integrityOk ? 'verified' : 'degraded')}</strong>
        </article>
      </div>

      <div className="kernelWorkbench">
        <section className="kernelPanel">
          <div className="panelHeader">
            <h2>Checkpoints</h2>
            <button type="button" onClick={() => void publish()} disabled={!journalReady || busy}>
              Publish snapshot
            </button>
          </div>
          {checkpoints.length === 0 ? (
            <p className="muted">No published checkpoints.</p>
          ) : (
            <ul className="goalList">
              {checkpoints.map((checkpoint) => (
                <li key={checkpoint.checkpoint_id}>
                  <button
                    type="button"
                    className={verify?.checkpoint_id === checkpoint.checkpoint_id ? 'active' : ''}
                    onClick={() => void verifyCheckpoint(checkpoint.checkpoint_id)}
                    disabled={busy}
                    title={checkpoint.checkpoint_id}
                  >
                    <strong>{checkpoint.publication}</strong>
                    <span>
                      {checkpoint.reason} · {shortId(checkpoint.checkpoint_id)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {verify ? (
            <p className="muted">
              {shortId(verify.checkpoint_id)} verified {verify.verified ? 'yes' : 'no'}, chain{' '}
              {verify.chain_ok ? 'ok' : 'degraded'}. Cryptographic immutability{' '}
              {verify.cryptographic_immutability ? 'claimed' : 'not claimed'}.
            </p>
          ) : null}
        </section>

        <section className="kernelPanel">
          <div className="panelHeader">
            <h2>Task runs</h2>
            <button type="button" onClick={() => void refresh()}>
              Refresh
            </button>
          </div>
          {tasks.length === 0 ? (
            <p className="muted">No persisted task runs.</p>
          ) : (
            <ul className="goalList">
              {tasks.map((task) => (
                <li key={task.task_id}>
                  <div className="goalListStatic">
                    <strong>{task.state}</strong>
                    <span>{task.objective}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="kernelPanel">
          <div className="panelHeader">
            <h2>Journal</h2>
            <span>{status?.encrypted_at_rest ? 'sealed' : 'plaintext fields'}</span>
          </div>
          <p className="muted">
            {status?.db_path || 'No journal path is configured.'} Approvals stay process-local and are not reusable
            after recovery.
          </p>
          {status?.published_head ? (
            <p className="muted">
              Head <span title={status.published_head}>{shortId(status.published_head)}</span>
            </p>
          ) : null}
        </section>

        <section className="kernelPanel kernelEvents">
          <div className="panelHeader">
            <h2>Live events</h2>
            <span>{events.length}</span>
          </div>
          {events.length === 0 ? (
            <p className="muted">
              No live continuity events in this process. The stream is not a second durable ledger.
            </p>
          ) : (
            <ol>
              {[...events].reverse().map((event) => (
                <li key={event.event_id || `${event.name}-${event.created_at || event.timestamp || ''}`}>
                  <strong>{event.name}</strong>
                  <span>
                    {String(event.payload?.state || event.payload?.reason || event.domain || 'live')}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </section>

        <section className="kernelPanel">
          <div className="panelHeader">
            <h2>Environment</h2>
            <span>observation</span>
          </div>
          {environment?.repository?.available ? (
            <p className="muted">
              {environment.repository.branch || 'detached'} ·{' '}
              {environment.repository.head_commit
                ? shortId(environment.repository.head_commit)
                : 'no commit'}{' '}
              · {environment.repository.dirty ? 'dirty' : 'clean'} ·{' '}
              {environment.repository.changed_path_count} paths
            </p>
          ) : (
            <p className="muted">
              {environment?.repository?.note || 'No repository observation is recorded.'}
            </p>
          )}
          <p className="muted">
            Model {environment?.process?.model_id || 'unset'}. Resume does not modify the worktree or
            switch models.
          </p>
          {environment?.comparison.notes?.length ? (
            <p className="kernelError">{environment.comparison.notes[0]}</p>
          ) : null}
        </section>

        <section className="kernelPanel">
          <div className="panelHeader">
            <h2>Limits</h2>
            <span>partial</span>
          </div>
          {status?.limitations && status.limitations.length > 0 ? (
            <ul className="goalList">
              {status.limitations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : (
            <p className="muted">
              A configured journal reports its limits here. An unconfigured runtime has no chain to inspect.
            </p>
          )}
        </section>
      </div>
    </section>
  );
}
