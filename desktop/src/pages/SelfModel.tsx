import { useEffect, useState } from 'react';
import { getSelfModel, type SelfModelSnapshot } from '../api/mission';
import { SurfaceFrame } from '../components/SurfaceFrame';

export function SelfModelPage() {
  const [snapshot, setSnapshot] = useState<SelfModelSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setSnapshot(await getSelfModel());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Self-model failed');
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <SurfaceFrame
      label="Self-model"
      eyebrow="Simulated introspection"
      title="Known limits"
      lede={snapshot?.statement || 'This is an engineering snapshot, not a consciousness claim.'}
      signal="simulated"
      error={error}
    >
      <section className="kernelWorkbench">
        <article className="kernelPanel">
          <div className="panelHeader">
            <h2>Limitations</h2>
            <span>{snapshot?.limitations.length ?? 0}</span>
          </div>
          <ul className="goalList">
            {(snapshot?.limitations || []).map((limitation) => (
              <li key={limitation.name}>
                <strong>
                  {limitation.name} · {limitation.severity}
                </strong>
                <span>{limitation.description}</span>
              </li>
            ))}
          </ul>
          <div className="kernelActions">
            <button type="button" onClick={() => void refresh()}>
              Review self-model
            </button>
          </div>
        </article>
        <article className="kernelPanel">
          <div className="panelHeader">
            <h2>Capabilities named</h2>
            <span>{snapshot?.capabilities.length ?? 0}</span>
          </div>
          <ul className="goalList">
            {(snapshot?.capabilities || []).map((capability) => (
              <li key={capability}>
                <strong>{capability}</strong>
              </li>
            ))}
          </ul>
          <p className="muted">
            Names come from the live capability catalog. A listed capability is not evidence that a
            weight file or a cloud model is loaded.
          </p>
        </article>
      </section>
    </SurfaceFrame>
  );
}
