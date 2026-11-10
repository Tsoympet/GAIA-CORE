import { useEffect, useState } from 'react';
import { getVoiceStatus, type VoiceStatus } from '../api/voice';

export function VoiceProfilePanel() {
  const [status, setStatus] = useState<VoiceStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void getVoiceStatus()
      .then(setStatus)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Profile status failed'));
  }, []);

  return (
    <section className="panel">
      <div className="panelHeader">
        <h2>Voice profile</h2>
        <span>{status?.synthetic_identity ? 'synthetic identity' : 'unknown'}</span>
      </div>
      <p>Profile id {status?.profile_id || 'loading'}.</p>
      <p>Local speech {status?.text_fallback ? 'falls back to text' : 'has no text fallback'}.</p>
      {error ? <p className="kernelError">{error}</p> : null}
    </section>
  );
}
