export async function getAudioStatus() { const r = await fetch('/audio/status'); return r.json(); }
