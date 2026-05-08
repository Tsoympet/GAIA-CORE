export type VoiceStatus = { enabled: boolean; profile_id: string; synthetic_identity: boolean; text_fallback: boolean };
export type VoiceSynthesisRequest = { text: string; provider?: string };
export async function getVoiceStatus(): Promise<VoiceStatus> { const r = await fetch('/voice/status'); return r.json(); }
export async function synthesizeVoice(body: VoiceSynthesisRequest) { const r = await fetch('/voice/synthesize', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }); return r.json(); }
