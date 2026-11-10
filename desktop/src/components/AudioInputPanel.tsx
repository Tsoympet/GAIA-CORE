import { useState } from 'react';

type Transcript = {
  text: string;
  provider: string;
  status: string;
};

export function AudioInputPanel() {
  const [text, setText] = useState('Operator typed this because no microphone daemon is attached.');
  const [result, setResult] = useState<Transcript | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    try {
      const response = await fetch('/voice/transcribe', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      setResult((await response.json()) as Transcript);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Transcription failed');
    }
  }

  return (
    <section className="panel">
      <div className="panelHeader">
        <h2>Audio input</h2>
        <span>no microphone</span>
      </div>
      <p>Capture is unavailable. Submit typed text as the local transcript.</p>
      <textarea aria-label="Transcript text" rows={3} value={text} onChange={(event) => setText(event.target.value)} />
      <div className="kernelActions">
        <button type="button" onClick={() => void submit()}>
          Submit transcript
        </button>
      </div>
      {result ? (
        <p className="muted">
          {result.status} via {result.provider}: {result.text}
        </p>
      ) : null}
      {error ? <p className="kernelError">{error}</p> : null}
    </section>
  );
}
