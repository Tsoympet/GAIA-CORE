import { useEffect, useState } from 'react';
import { getModels, type ModelDescriptor, type ModelHealth, type ProviderHealth } from '../api/mission';
import { SurfaceFrame } from '../components/SurfaceFrame';

function providerLine(health: ProviderHealth | undefined, fallback: string): string {
  if (!health) {
    return fallback;
  }
  const reachable = health.reachable === true || health.available === true;
  const detail = health.detail || health.reason || '';
  return `${reachable ? 'reachable' : 'unreachable'}${detail ? ` · ${detail}` : ''}`;
}

export function ModelsPage() {
  const [health, setHealth] = useState<ModelHealth | null>(null);
  const [models, setModels] = useState<ModelDescriptor[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      const payload = await getModels();
      setHealth(payload.health);
      setModels(payload.descriptors);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Model health failed');
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  const local = health?.providers.local;
  const ollama = health?.providers.ollama;
  const cloud = health?.providers.cloud;

  return (
    <SurfaceFrame
      label="Models"
      eyebrow="Model router"
      title="Local client and Ollama"
      lede="Health stays available when Ollama is absent. The deterministic client does not download weights, and cloud calls stay disabled."
      signal={health ? health.active_provider : 'checking'}
      error={error}
    >
      <section className="kernelMetrics" aria-label="Provider health">
        <article>
          <h3>Local client</h3>
          <strong>{local?.available ? 'ready' : 'down'}</strong>
          <p className="muted">{local?.model_id || 'gaia-deterministic-local'}</p>
        </article>
        <article>
          <h3>Ollama</h3>
          <strong>{health?.ollama_reachable ? 'reachable' : 'unreachable'}</strong>
          <p className="muted">{providerLine(ollama, 'daemon not required')}</p>
        </article>
        <article>
          <h3>Cloud</h3>
          <strong>{cloud?.enabled ? 'enabled' : 'disabled'}</strong>
          <p className="muted">{cloud?.reason || 'no paid calls'}</p>
        </article>
        <article>
          <h3>Working model</h3>
          <strong className="longMetric">{health?.working_model || 'local'}</strong>
          <p className="muted">
            {local?.neural_weights_loaded ? 'weights loaded' : 'no weights loaded'}
          </p>
        </article>
      </section>
      <section className="kernelWorkbench">
        <article className="kernelPanel">
          <div className="panelHeader">
            <h2>Catalog</h2>
            <span>{models.length}</span>
          </div>
          <ul className="goalList">
            {models.map((model) => (
              <li key={model.model_id}>
                <strong>{model.model_id}</strong>
                <span>
                  {model.provider} · {model.enabled ? 'enabled' : 'disabled'} ·{' '}
                  {model.local_first ? 'local-first' : 'remote'}
                </span>
                <span className="muted">{model.capabilities.join(', ')}</span>
              </li>
            ))}
          </ul>
          <div className="kernelActions">
            <button type="button" onClick={() => void refresh()}>
              Refresh health
            </button>
          </div>
        </article>
        <article className="kernelPanel">
          <h2>What this page will not do</h2>
          <p className="muted">
            It does not download weights, start a paid cloud model, or treat an unreachable Ollama
            daemon as a failed runtime. Chat still answers from the deterministic local client
            unless Ollama lists a ready model.
          </p>
          {health?.ollama_models?.length ? (
            <p>Ollama models: {health.ollama_models.join(', ')}</p>
          ) : (
            <p className="muted">No ready Ollama model is listed.</p>
          )}
        </article>
      </section>
    </SurfaceFrame>
  );
}
