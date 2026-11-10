export type VoiceStatus = {
  enabled: boolean;
  profile_id: string;
  synthetic_identity: boolean;
  text_fallback: boolean;
};

export type VoiceSynthesisRequest = { text: string; provider?: string };

export type VoiceSynthesisResult = {
  text: string;
  provider: string;
  status: string;
  synthetic: boolean;
  audio_base64?: string | null;
  mime_type?: string;
};

async function read<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error((await response.text()) || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function getVoiceStatus(): Promise<VoiceStatus> {
  return read(await fetch('/voice/status'));
}

export async function synthesizeVoice(body: VoiceSynthesisRequest): Promise<VoiceSynthesisResult> {
  return read(
    await fetch('/voice/synthesize', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    }),
  );
}
