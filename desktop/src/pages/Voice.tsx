import { AudioInputPanel } from '../components/AudioInputPanel';
import { AudioOutputPanel } from '../components/AudioOutputPanel';
import { VoicePanel } from '../components/VoicePanel';
import { VoiceProfilePanel } from '../components/VoiceProfilePanel';

export function VoicePage() {
  return (
    <>
      <section className="hero">
        <p className="eyebrow">GAIA Voice</p>
        <h1>Synthetic voice identity and speech interface</h1>
        <p>Playback is a generated tone or text. GAIA does not impersonate a real person.</p>
      </section>
      <section className="grid">
        <VoicePanel />
        <VoiceProfilePanel />
        <AudioInputPanel />
        <AudioOutputPanel />
      </section>
    </>
  );
}
