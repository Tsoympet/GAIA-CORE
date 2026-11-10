import { useEffect, useState } from 'react';
import {
  appendOrganismEvidence,
  approveOrganismMemory,
  getOrganismStatus,
  listOrganismTimeline,
  proposeOrganismCandidate,
  recordOrganismMemory,
  searchOrganismMemories,
  validateOrganismMemory,
  type OrganismMemory,
  type OrganismStatus,
  type RetrievalHit,
} from '../api/organism';

function shortId(value: string): string {
  return value.length > 12 ? `${value.slice(0, 8)}…` : value;
}

function memoryLabel(memory: OrganismMemory): string {
  return memory.content?.trim() || '(content removed)';
}

export function OrganismPage() {
  const [status, setStatus] = useState<OrganismStatus | null>(null);
  const [hits, setHits] = useState<RetrievalHit[]>([]);
  const [timeline, setTimeline] = useState<OrganismMemory[]>([]);
  const [selected, setSelected] = useState<OrganismMemory | null>(null);
  const [ownerId, setOwnerId] = useState('local');
  const [query, setQuery] = useState('hydrostatic');
  const [mode, setMode] = useState<'hybrid' | 'bm25'>('hybrid');
  const [observation, setObservation] = useState('');
  const [candidate, setCandidate] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [ranker, setRanker] = useState('hybrid');

  const storeReady = status?.status === 'available' || status?.status === 'degraded';

  async function refresh() {
    try {
      const nextStatus = await getOrganismStatus();
      setStatus(nextStatus);
      setError(null);
      if (nextStatus.status === 'unavailable') {
        setHits([]);
        setTimeline([]);
        setSelected(null);
        return;
      }
      const [search, events] = await Promise.all([
        searchOrganismMemories(query.trim(), { ownerId, mode }),
        listOrganismTimeline(ownerId),
      ]);
      setHits(search.hits);
      setRanker(search.ranker);
      setTimeline(events.entries);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load organism');
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function runSearch() {
    setBusy(true);
    try {
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  async function recordObservation() {
    if (!observation.trim()) {
      setError('Write an observation before recording evidence.');
      return;
    }
    setBusy(true);
    try {
      const evidence = await appendOrganismEvidence(observation.trim());
      const recorded = await recordOrganismMemory(evidence.evidence.evidence_id, ownerId);
      setSelected(recorded.memory);
      setObservation('');
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Record failed');
    } finally {
      setBusy(false);
    }
  }

  async function proposeSelected() {
    if (!selected) {
      setError('Select a recorded memory to cite.');
      return;
    }
    if (!candidate.trim()) {
      setError('Write a candidate that cites the selected memory.');
      return;
    }
    setBusy(true);
    try {
      const proposed = await proposeOrganismCandidate(candidate.trim(), [selected.memory_id], ownerId);
      setSelected(proposed.memory);
      setCandidate('');
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Candidate refused');
    } finally {
      setBusy(false);
    }
  }

  async function validateSelected(passed: boolean) {
    if (!selected) {
      return;
    }
    setBusy(true);
    try {
      const result = await validateOrganismMemory(selected.memory_id, passed);
      setSelected(result.memory);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Validation failed');
    } finally {
      setBusy(false);
    }
  }

  async function approveSelected() {
    if (!selected) {
      return;
    }
    setBusy(true);
    try {
      const result = await approveOrganismMemory(selected.memory_id);
      setSelected(result.memory);
      if (result.policy_effect !== 'none') {
        setError('Approval returned an unexpected policy effect.');
      }
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Approval failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="kernelPage" aria-label="Memory Organism">
      <header className="kernelHeader">
        <div>
          <p className="eyebrow">Memory Organism</p>
          <h1>Local evidence and promotion</h1>
          <p>
            Durable memories stay on this machine. Hybrid search is not a neural embedding, and approval
            cannot change security policy.
          </p>
        </div>
        <div className="kernelSignals">
          <span>{status?.status || 'loading'}</span>
          <span>{status?.durable ? 'durable' : 'not configured'}</span>
          <span>{status?.retrieval?.neural_embeddings ? 'embeddings' : 'no embeddings'}</span>
          <span>
            {status?.evidence?.cryptographic_immutability ? 'immutable claimed' : 'not immutable'}
          </span>
        </div>
      </header>

      {error ? <p className="kernelError">{error}</p> : null}

      {status?.status === 'unavailable' ? (
        <p className="kernelError" role="status">
          {status.reason || 'Memory Organism is not configured for this runtime.'}
        </p>
      ) : null}

      <div className="kernelMetrics">
        <article>
          <h3>Memories</h3>
          <strong>{status?.memory_count ?? 0}</strong>
        </article>
        <article>
          <h3>Evidence</h3>
          <strong>{status?.evidence?.record_count ?? 0}</strong>
        </article>
        <article>
          <h3>Schema</h3>
          <strong>{status?.schema_version ?? '—'}</strong>
        </article>
        <article>
          <h3>Ranker</h3>
          <strong>{ranker}</strong>
        </article>
      </div>

      <div className="kernelWorkbench">
        <section className="kernelPanel">
          <div className="panelHeader">
            <h2>Record observation</h2>
            <span>{ownerId}</span>
          </div>
          <label className="fieldLabel" htmlFor="organism-owner">
            Owner
          </label>
          <input
            id="organism-owner"
            value={ownerId}
            onChange={(event) => setOwnerId(event.target.value)}
            disabled={!storeReady || busy}
          />
          <textarea
            value={observation}
            onChange={(event) => setObservation(event.target.value)}
            rows={4}
            aria-label="Observation to store as evidence"
            placeholder="Observed hydrostatic stability after the compartment change"
            disabled={!storeReady || busy}
          />
          <div className="kernelActions">
            <button type="button" onClick={() => void recordObservation()} disabled={!storeReady || busy}>
              Append evidence and record
            </button>
          </div>
        </section>

        <section className="kernelPanel">
          <div className="panelHeader">
            <h2>Search</h2>
            <button type="button" onClick={() => void runSearch()} disabled={!storeReady || busy}>
              Search
            </button>
          </div>
          <label className="fieldLabel" htmlFor="organism-query">
            Query
          </label>
          <input
            id="organism-query"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            disabled={!storeReady || busy}
          />
          <label className="fieldLabel" htmlFor="organism-mode">
            Ranker
          </label>
          <select
            id="organism-mode"
            value={mode}
            onChange={(event) => setMode(event.target.value as 'hybrid' | 'bm25')}
            disabled={!storeReady || busy}
          >
            <option value="hybrid">hybrid</option>
            <option value="bm25">bm25</option>
          </select>
          {hits.length === 0 ? (
            <p className="muted">No retained memories match. Default search hides identity and preference.</p>
          ) : (
            <ul className="goalList">
              {hits.map((hit) => (
                <li key={hit.memory.memory_id}>
                  <button
                    type="button"
                    className={selected?.memory_id === hit.memory.memory_id ? 'active' : ''}
                    onClick={() => setSelected(hit.memory)}
                    title={hit.memory.memory_id}
                  >
                    <strong>
                      {hit.memory.category} · {hit.effective_status}
                    </strong>
                    <span>{memoryLabel(hit.memory)}</span>
                    <span className="muted">
                      score {hit.score.toFixed(3)} · {hit.ranker} · uncalibrated
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="kernelPanel">
          <div className="panelHeader">
            <h2>Selected memory</h2>
            <span>{selected?.status || 'none'}</span>
          </div>
          {selected ? (
            <>
              <p>{memoryLabel(selected)}</p>
              <p className="muted">
                {selected.category} · owner {selected.owner_id} · approved knowledge{' '}
                {selected.approved_knowledge ? 'yes' : 'no'} · policy {selected.policy_effect} ·{' '}
                <span title={selected.memory_id}>{shortId(selected.memory_id)}</span>
              </p>
              <label className="fieldLabel" htmlFor="organism-candidate">
                Candidate abstraction
              </label>
              <textarea
                id="organism-candidate"
                value={candidate}
                onChange={(event) => setCandidate(event.target.value)}
                rows={3}
                placeholder="The compartment change improved hydrostatic stability"
                disabled={!storeReady || busy}
              />
              <div className="kernelActions">
                <button type="button" onClick={() => void proposeSelected()} disabled={!storeReady || busy}>
                  Propose candidate
                </button>
                <button
                  type="button"
                  onClick={() => void validateSelected(true)}
                  disabled={!storeReady || busy || selected.status !== 'candidate'}
                >
                  Validate
                </button>
                <button
                  type="button"
                  onClick={() => void approveSelected()}
                  disabled={!storeReady || busy || selected.status !== 'validated'}
                >
                  Approve
                </button>
              </div>
            </>
          ) : (
            <p className="muted">Select a search hit or record an observation. Approval cannot change policy.</p>
          )}
        </section>

        <section className="kernelPanel">
          <div className="panelHeader">
            <h2>Timeline</h2>
            <span>{timeline.length}</span>
          </div>
          {timeline.length === 0 ? (
            <p className="muted">No recorded timeline entries for this owner. Timeline order uses event_at, not search.</p>
          ) : (
            <ul className="goalList">
              {timeline.map((entry) => (
                <li key={entry.memory_id}>
                  <div className="goalListStatic">
                    <strong>{entry.event_at || entry.created_at}</strong>
                    <span>{memoryLabel(entry)}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="kernelPanel">
          <div className="panelHeader">
            <h2>Store</h2>
            <span>{status?.encrypted_at_rest ? 'sealed' : 'plaintext fields'}</span>
          </div>
          <p className="muted">{status?.db_path || 'No organism path is configured.'}</p>
          <p className="muted">Indexed terms are hashed. Deletion removes those derived rows.</p>
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
              A configured organism reports its limits here. An unconfigured runtime has no memories to inspect.
            </p>
          )}
        </section>
      </div>
    </section>
  );
}
