import { useEffect, useState } from 'react';
import { getMetacognitionStatus, reviewAnswer, type ReflectionReport } from '../api/mission';
import { SurfaceFrame } from '../components/SurfaceFrame';

function Report({ report }: { report: ReflectionReport | null }) {
  if (!report) {
    return <p className="muted">No review has been stored in the local journal yet.</p>;
  }
  return (
    <div className="structuredResult">
      <p className="muted">
        Heuristic confidence {report.confidence.confidence.toFixed(2)} · uncertainty{' '}
        {report.confidence.uncertainty.toFixed(2)}. This is not a calibrated probability.
      </p>
      <p>{report.confidence.rationale}</p>
      <p>Strengths: {report.critique.strengths.join(' ') || 'none'}</p>
      <p>Risks: {report.critique.risks.join(' ') || 'none'}</p>
      <p>Suggestions: {report.critique.improvement_suggestions.join(' ') || 'none'}</p>
    </div>
  );
}

export function MetacognitionPage() {
  const [answer, setAnswer] = useState('Local plan is ready for operator review before any tool runs.');
  const [report, setReport] = useState<ReflectionReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void getMetacognitionStatus()
      .then(setReport)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Metacognition status failed');
      });
  }, []);

  async function submit() {
    setBusy(true);
    try {
      setReport(await reviewAnswer(answer.trim()));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Review failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <SurfaceFrame
      label="Metacognition"
      eyebrow="Internal review"
      title="Reflect on an answer"
      lede="The review is stored in the local journal and reloads after a restart. It does not call a tool, send a message, or change policy."
      signal={report ? 'reviewed' : 'ready'}
      error={error}
    >
      <section className="kernelWorkbench">
        <article className="kernelPanel">
          <label className="fieldLabel" htmlFor="review-answer">
            Answer
          </label>
          <textarea
            id="review-answer"
            rows={5}
            value={answer}
            onChange={(event) => setAnswer(event.target.value)}
          />
          <div className="kernelActions">
            <button type="button" onClick={() => void submit()} disabled={busy || !answer.trim()}>
              Submit review
            </button>
          </div>
        </article>
        <article className="kernelPanel">
          <div className="panelHeader">
            <h2>Latest review</h2>
            <span>heuristic</span>
          </div>
          <Report report={report} />
        </article>
      </section>
    </SurfaceFrame>
  );
}
