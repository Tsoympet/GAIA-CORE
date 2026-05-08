import { create } from 'zustand';
type VoiceState = { text: string; setText: (text: string) => void; provider: string; setProvider: (provider: string) => void };
export const useVoiceStore = create<VoiceState>((set) => ({ text: 'Hello from GAIA synthetic voice.', provider: 'local-placeholder', setText: (text) => set({ text }), setProvider: (provider) => set({ provider }) }));
