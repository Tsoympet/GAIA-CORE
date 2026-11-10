import { useEffect, useState } from 'react';
import {
  addFact,
  getMemoryStatus,
  listFacts,
  recallMemory,
  reviewMemory,
  writeMemory,
  type MemoryRecord,
  type MemoryStatus,
  type RecallHit,
  type SymbolicFact,
} from '../api/mission';
import { SurfaceFrame } from '../components/SurfaceFrame';

export function MemoryPage() {
  const [status, setStatus] = useState<MemoryStatus | null>(null);
  const [ownerId, setOwnerId] = useState('local');
  const [note, setNote] = useState('Hydrostatic bearing prefers local notes');
  const [query, setQuery] = useState('hydrostatic bearing');
  const [hits, setHits] = useState<RecallHit[]>([]);
  const [records, setRecords] = useState<MemoryRecord[]>([]);
  const [facts, setFacts] = useState<SymbolicFact[]>([]);
  const [subject, setSubject] = useState('bearing');
  const [predicate, setPredicate] = useState('prefers');
  const [objectValue, setObjectValue] = useState('local-notes');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh(owner = ownerId) {
    const [nextStatus, nextRecords, nextFacts] = await Promise.all([
      getMemoryStatus(),
      reviewMemory(owner),
      listFacts(owner),
    ]);
    setStatus(nextStatus);
    setRecords(nextRecords);
    setFacts(nextFacts);
  }

  useEffect(() => {
    void refresh().catch((err: unknown) => {
      setError(err instanceof Error ? err.message : 'Memory status failed');
    });
  }, []);

  async function writeAndRecall() {
    setBusy(true);
    try {
      await writeMemory(note.trim(), ownerId.trim() || 'local', 'project');
      setHits(await recallMemory(query.trim(), ownerId.trim() || 'local'));
      await refresh(ownerId.trim() || 'local');
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Memory recall failed');
    } finally {
      setBusy(false);
    }
  }

  async function recallOnly() {
    setBusy(true);
    try {
      const owner = ownerId.trim() || 'local';
      setHits(await recallMemory(query.trim(), owner));
      await refresh(owner);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Memory recall failed');
    } finally {
      setBusy(false);
    }
  }

  async function saveFact() {
    setBusy(true);
    try {
      await addFact(ownerId.trim() || 'local', subject.trim(), predicate.trim(), objectValue.trim());
      await refresh(ownerId.trim() || 'local');
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Symbolic fact failed');
    } finally {
      setBusy(false);
    }
  }

  const scoreNote =
    status?.score_note ||
    'Cosine scores from the in-process hashed n-gram index are uncalibrated.';

  return (
    <SurfaceFrame
      label="Memory"
      eyebrow="Scoped memory"
      title="Vector recall"
      lede={scoreNote}
      signal={status?.scores_calibrated ? 'calibrated' : 'uncalibrated scores'}
      error={error}
    >
      <section className="kernelMetrics" aria-label="Memory counts">
        <article>
          <h3>Indexed notes</h3>
          <strong>{status?.indexed_documents ?? 0}</strong>
        </article>
        <article>
          <h3>Symbolic facts</h3>
          <strong>{status?.symbolic_facts ?? 0}</strong>
        </article>
        <article>
          <h3>Index</h3>
          <strong className="longMetric">{status?.vector_index || 'local'}</strong>
        </article>
      </section>
      <section className="kernelWorkbench">
        <article className="kernelPanel">
          <label className="fieldLabel" htmlFor="memory-owner">
            Owner
          </label>
          <input id="memory-owner" value={ownerId} onChange={(event) => setOwnerId(event.target.value)} />
          <label className="fieldLabel" htmlFor="memory-note-page">
            Note
          </label>
          <textarea
            id="memory-note-page"
            rows={3}
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />
          <label className="fieldLabel" htmlFor="memory-query-page">
            Recall query
          </label>
          <input
            id="memory-query-page"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <div className="kernelActions">
            <button type="button" onClick={() => void writeAndRecall()} disabled={busy || !note.trim()}>
              Write and recall
            </button>
            <button type="button" onClick={() => void recallOnly()} disabled={busy || !query.trim()}>
              Recall
            </button>
          </div>
          {hits.length ? (
            <ul className="goalList">
              {hits.map((hit) => (
                <li key={`${hit.source}-${hit.record_id}`}>
                  <strong>
                    {hit.source} · {hit.score.toFixed(2)} · uncalibrated
                  </strong>
                  <span>{hit.content}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">
              Recall is limited to this owner. A symbolic fact stored without an owner stays hidden
              from every owner.
            </p>
          )}
        </article>
        <article className="kernelPanel">
          <div className="panelHeader">
            <h2>Review</h2>
            <span>{records.length} notes</span>
          </div>
          {records.length ? (
            <ul className="goalList">
              {records.map((record) => (
                <li key={record.record_id}>
                  <strong>{record.scope}</strong>
                  <span>{record.content}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No retained notes for this owner yet.</p>
          )}
          <h2>Symbolic fact</h2>
          <label className="fieldLabel" htmlFor="fact-subject">
            Subject
          </label>
          <input id="fact-subject" value={subject} onChange={(event) => setSubject(event.target.value)} />
          <label className="fieldLabel" htmlFor="fact-predicate">
            Predicate
          </label>
          <input
            id="fact-predicate"
            value={predicate}
            onChange={(event) => setPredicate(event.target.value)}
          />
          <label className="fieldLabel" htmlFor="fact-object">
            Object
          </label>
          <input
            id="fact-object"
            value={objectValue}
            onChange={(event) => setObjectValue(event.target.value)}
          />
          <div className="kernelActions">
            <button
              type="button"
              onClick={() => void saveFact()}
              disabled={busy || !subject.trim() || !predicate.trim() || !objectValue.trim()}
            >
              Add symbolic fact
            </button>
          </div>
          <ul className="goalList">
            {facts.map((fact) => (
              <li key={fact.fact_id}>
                <strong>
                  {fact.subject} {fact.predicate} {fact.object_value}
                </strong>
                <span className="muted">
                  confidence {fact.confidence.toFixed(2)} is uncalibrated
                </span>
              </li>
            ))}
          </ul>
        </article>
      </section>
    </SurfaceFrame>
  );
}
