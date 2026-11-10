import { useEffect, useState } from 'react';
import { getVoiceStatus, synthesizeVoice, type VoiceStatus } from '../api/voice';

export function VoicePanel() {
  const [status, setStatus] = useState<VoiceStatus | null>(null);
  const [text, setText] = useState('GAIA is using a synthetic voice, not a real person.');
  const [reply, setReply] = useState('');
  const [provider, setProvider] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void getVoiceStatus()
      .then((next) => {
        setStatus(next);
        setError(null);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Voice status failed'));
  }, []);

  async function speak(nextProvider: string) {
    setError(null);
    try {
      const result = await synthesizeVoice({ text, provider: nextProvider });
      setReply(result.text);
      setProvider(`${result.provider} · ${result.status}`);
      if (result.audio_base64) {
        const audio = new Audio(`data:${result.mime_type || 'audio/wav'};base64,${result.audio_base64}`);
        try {
          await audio.play();
        } catch {
          setProvider(`${result.provider} · ${result.status} · tone ready`);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Synthesis failed');
    }
  }

  return (
    <section className="panel">
      <div className="panelHeader">
        <h2>Speech</h2>
        <span>{status?.synthetic_identity ? 'synthetic' : 'checking'}</span>
      </div>
      <p>Profile {status?.profile_id || '…'}. Text fallback stays available. This does not clone a real voice.</p>
      <textarea aria-label="Speech text" rows={3} value={text} onChange={(event) => setText(event.target.value)} />
      <div className="kernelActions">
        <button type="button" onClick={() => void speak('local-placeholder')}>
          Text fallback
        </button>
        <button type="button" onClick={() => void speak('synthetic-tone')}>
          Play synthetic tone
        </button>
      </div>
      {provider ? <p className="muted">{provider}</p> : null}
      {reply ? <pre className="structuredResult">{reply}</pre> : null}
      {error ? <p className="kernelError">{error}</p> : null}
    </section>
  );
}
