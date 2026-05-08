import { create } from 'zustand';
type AudioState = { microphoneEnabled: boolean; speakerEnabled: boolean; setMicrophoneEnabled: (enabled: boolean) => void; setSpeakerEnabled: (enabled: boolean) => void };
export const useAudioStore = create<AudioState>((set) => ({ microphoneEnabled: false, speakerEnabled: false, setMicrophoneEnabled: (microphoneEnabled) => set({ microphoneEnabled }), setSpeakerEnabled: (speakerEnabled) => set({ speakerEnabled }) }));
