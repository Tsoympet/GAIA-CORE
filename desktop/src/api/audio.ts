export async function getAudioStatus(): Promise<unknown> {
  const response = await fetch('/audio/status');
  if (!response.ok) {
    throw new Error((await response.text()) || `HTTP ${response.status}`);
  }
  return response.json();
}
