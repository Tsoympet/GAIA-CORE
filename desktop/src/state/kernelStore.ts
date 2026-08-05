import { create } from 'zustand';
import type { KernelEvent, KernelGoal, KernelStatusResponse } from '../api/kernel';

type KernelState = {
  status: KernelStatusResponse | null;
  goals: KernelGoal[];
  events: KernelEvent[];
  selectedGoalId: string | null;
  taskDraft: string;
  error: string | null;
  streaming: boolean;
  setStatus: (status: KernelStatusResponse | null) => void;
  setGoals: (goals: KernelGoal[]) => void;
  setEvents: (events: KernelEvent[]) => void;
  appendEvent: (event: KernelEvent) => void;
  setSelectedGoalId: (goalId: string | null) => void;
  setTaskDraft: (task: string) => void;
  setError: (error: string | null) => void;
  setStreaming: (streaming: boolean) => void;
};

export const useKernelStore = create<KernelState>((set) => ({
  status: null,
  goals: [],
  events: [],
  selectedGoalId: null,
  taskDraft: 'Inspect Cognitive Kernel status and budgets',
  error: null,
  streaming: false,
  setStatus: (status) => set({ status }),
  setGoals: (goals) => set({ goals }),
  setEvents: (events) => set({ events }),
  appendEvent: (event) =>
    set((state) => ({
      events: [...state.events.slice(-199), event],
    })),
  setSelectedGoalId: (selectedGoalId) => set({ selectedGoalId }),
  setTaskDraft: (taskDraft) => set({ taskDraft }),
  setError: (error) => set({ error }),
  setStreaming: (streaming) => set({ streaming }),
}));
