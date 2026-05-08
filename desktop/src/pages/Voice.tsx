import { VoicePanel } from '../components/VoicePanel';
import { VoiceProfilePanel } from '../components/VoiceProfilePanel';
import { AudioInputPanel } from '../components/AudioInputPanel';
import { AudioOutputPanel } from '../components/AudioOutputPanel';
export function Voice() { return <main className="shell"><section className="hero"><p className="eyebrow">GAIA Voice</p><h1>Synthetic voice identity and speech interface</h1></section><VoicePanel /><VoiceProfilePanel /><AudioInputPanel /><AudioOutputPanel /></main>; }
