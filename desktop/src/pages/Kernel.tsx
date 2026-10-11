import { useEffect, useMemo } from 'react';
import {
  backupKernel,
  cancelGoal,
  deleteGoal,
  getGoal,
  getKernelStatus,
  listEvents,
  listGoals,
  openKernelEventStream,
  resumeGoal,
  submitKernelTask,
  type KernelEvent,
} from '../api/kernel';
import { useKernelStore } from '../state/kernelStore';

function eventKey(event: KernelEvent): string {
  return event.id || event.event_id || `${event.name}-${event.timestamp || event.created_at || ''}`;
}

export function KernelPage() {
  const {
    status,
    goals,
    events,
    selectedGoalId,
    taskDraft,
    error,
    streaming,
    setStatus,
    setGoals,
    setEvents,
    appendEvent,
    setSelectedGoalId,
    setTaskDraft,
    setError,
    setStreaming,
  } = useKernelStore();

  const selectedGoal = useMemo(
    () => goals.find((goal) => goal.id === selectedGoalId) || null,
    [goals, selectedGoalId],
  );

  async function refresh() {
    try {
      const [nextStatus, nextGoals, nextEvents] = await Promise.all([
        getKernelStatus(),
        listGoals(),
        listEvents(),
      ]);
      setStatus(nextStatus);
      setGoals(nextGoals.goals);
      setEvents(nextEvents.events);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load kernel state');
    }
  }

  useEffect(() => {
    void refresh();
    const source = openKernelEventStream((payload) => {
      if ('events' in payload && Array.isArray(payload.events)) {
        setEvents(payload.events);
        return;
      }
      appendEvent(payload as KernelEvent);
    });
    setStreaming(true);
    source.onerror = () => setStreaming(false);
    return () => {
      source.close();
      setStreaming(false);
    };
  }, [appendEvent, setEvents, setStreaming]);

  async function runTask() {
    try {
      await submitKernelTask(taskDraft.trim());
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Task failed');
    }
  }

  async function onSelectGoal(goalId: string) {
    setSelectedGoalId(goalId);
    try {
      const detail = await getGoal(goalId);
      setEvents(detail.events);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load goal');
    }
  }

  return (
    <section className="kernelPage" aria-label="Cognitive Kernel mission control">
      <header className="kernelHeader">
        <div>
          <p className="eyebrow">Cognitive Kernel</p>
          <h1>Goal control plane</h1>
          <p>Live goals, budgets, verification, and durable event streaming.</p>
        </div>
        <div className="kernelSignals">
          <span>{status?.kernel.status || 'offline'}</span>
          <span>{streaming ? 'streaming' : 'stream idle'}</span>
          <span>{status?.persistence.durable ? 'durable' : 'memory'}</span>
        </div>
      </header>

      {error ? <p className="kernelError">{error}</p> : null}

      <div className="kernelMetrics">
        <article>
          <h3>Goals</h3>
          <strong>{status?.kernel.goals_tracked ?? goals.length}</strong>
        </article>
        <article>
          <h3>Verified</h3>
          <strong>{status?.kernel.verified_runs ?? 0}</strong>
        </article>
        <article>
          <h3>Interrupts</h3>
          <strong>{status?.pending_interrupts ?? 0}</strong>
        </article>
        <article>
          <h3>Events</h3>
          <strong>{status?.persistence.event_count ?? events.length}</strong>
        </article>
      </div>

      <div className="kernelWorkbench">
        <section className="kernelPanel">
          <div className="panelHeader">
            <h2>Submit goal</h2>
            <button type="button" onClick={() => void refresh()}>
              Refresh
            </button>
          </div>
          <textarea
            value={taskDraft}
            onChange={(event) => setTaskDraft(event.target.value)}
            rows={4}
            aria-label="Kernel task objective"
          />
          <div className="kernelActions">
            <button type="button" onClick={() => void runTask()}>
              Run through kernel
            </button>
            <button type="button" onClick={() => void backupKernel().then(refresh).catch((err: Error) => setError(err.message))}>
              Backup
            </button>
          </div>
        </section>

        <section className="kernelPanel">
          <div className="panelHeader">
            <h2>Goals</h2>
            <span>{goals.length}</span>
          </div>
          <ul className="goalList">
            {goals.map((goal) => (
              <li key={goal.id}>
                <button type="button" className={goal.id === selectedGoalId ? 'active' : ''} onClick={() => void onSelectGoal(goal.id)}>
                  <strong>{goal.status}</strong>
                  <span>{goal.objective}</span>
                </button>
                <div className="goalActions">
                  {goal.status === 'interrupted' ? (
                    <button type="button" onClick={() => void resumeGoal(goal.id).then(refresh).catch((err: Error) => setError(err.message))}>
                      Resume
                    </button>
                  ) : null}
                  {goal.status === 'active' || goal.status === 'pending' ? (
                    <button type="button" onClick={() => void cancelGoal(goal.id).then(refresh).catch((err: Error) => setError(err.message))}>
                      Cancel
                    </button>
                  ) : null}
                  <button type="button" onClick={() => void deleteGoal(goal.id).then(refresh).catch((err: Error) => setError(err.message))}>
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section className="kernelPanel">
          <div className="panelHeader">
            <h2>Selected goal</h2>
            <span>{selectedGoal?.status || 'none'}</span>
          </div>
          {selectedGoal ? (
            <>
              <p>{selectedGoal.objective}</p>
              <p className="muted">Session {selectedGoal.session_id}</p>
              {selectedGoal.error ? <p className="kernelError">{selectedGoal.error}</p> : null}
            </>
          ) : (
            <p className="muted">Select a goal to inspect context and budgets.</p>
          )}
        </section>

        <section className="kernelPanel kernelEvents">
          <div className="panelHeader">
            <h2>Event stream</h2>
            <span>{events.length}</span>
          </div>
          <ol>
            {[...events].reverse().map((event) => (
              <li key={eventKey(event)}>
                <strong>{event.name}</strong>
                <span>{event.goal_id || event.trace_id || '—'}</span>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </section>
  );
}
