import { useEffect, useState } from 'react';
import { getAudioStatus } from '../api/audio';

type AudioStatus = {
  microphone_enabled: boolean;
  speaker_enabled: boolean;
  text_fallback: boolean;
  synthetic_tone: boolean;
  capture: string;
  playback: string;
  detail: string;
};

export function AudioOutputPanel() {
  const [status, setStatus] = useState<AudioStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void getAudioStatus()
      .then((payload) => setStatus(payload as AudioStatus))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Audio status failed'));
  }, []);

  return (
    <section className="panel">
      <div className="panelHeader">
        <h2>Audio output</h2>
        <span>{status?.playback || '…'}</span>
      </div>
      <p>{status?.detail || 'Loading audio status.'}</p>
      <p className="muted">
        Microphone {status?.microphone_enabled ? 'enabled' : 'unavailable'} · capture {status?.capture || '…'} · text
        fallback {status?.text_fallback ? 'on' : 'off'} · synthetic tone {status?.synthetic_tone ? 'on' : 'off'}
      </p>
      {error ? <p className="kernelError">{error}</p> : null}
    </section>
  );
}
