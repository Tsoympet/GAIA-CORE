const API_BASE = '';

export type KernelStatusResponse = {
  status: string;
  kernel: {
    kernel_id: string;
    status: string;
    goals_tracked: number;
    verified_runs: number;
    failed_verifications: number;
    budget_violations: number;
    interrupt_count: number;
  };
  active_contexts: number;
  pending_interrupts: number;
  persistence: {
    backend: string;
    db_path: string;
    schema_version: number;
    goal_count: number;
    event_count: number;
    durable: boolean;
  };
};

export type KernelGoal = {
  id: string;
  objective: string;
  session_id: string;
  status: string;
  capabilities: string[];
  error?: string | null;
  created_at: string;
  updated_at: string;
};

export type KernelEvent = {
  id?: string;
  event_id?: string;
  goal_id?: string | null;
  session_id?: string | null;
  trace_id?: string | null;
  name: string;
  payload?: Record<string, unknown>;
  created_at?: string;
  timestamp?: string;
};

export type GoalDetail = {
  goal: KernelGoal;
  context: { items?: Array<{ key: string; value: unknown }> };
  budget: Record<string, unknown> | null;
  events: KernelEvent[];
};

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function getKernelStatus(): Promise<KernelStatusResponse> {
  return parse(await fetch(`${API_BASE}/kernel/status`));
}

export async function listGoals(status?: string): Promise<{ goals: KernelGoal[]; count: number }> {
  const query = status ? `?status=${encodeURIComponent(status)}` : '';
  return parse(await fetch(`${API_BASE}/kernel/goals${query}`));
}

export async function getGoal(goalId: string): Promise<GoalDetail> {
  return parse(await fetch(`${API_BASE}/kernel/goals/${goalId}`));
}

export async function listEvents(goalId?: string): Promise<{ events: KernelEvent[]; count: number }> {
  const query = goalId ? `?goal_id=${encodeURIComponent(goalId)}` : '';
  return parse(await fetch(`${API_BASE}/kernel/events${query}`));
}

export async function submitKernelTask(task: string): Promise<{ result: { goal: KernelGoal } }> {
  return parse(
    await fetch(`${API_BASE}/kernel/tasks`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ task, capabilities: ['reasoning'] }),
    }),
  );
}

export async function resumeGoal(goalId: string): Promise<unknown> {
  return parse(
    await fetch(`${API_BASE}/kernel/goals/${goalId}/resume`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({}),
    }),
  );
}

export async function cancelGoal(goalId: string, reason = 'desktop cancel'): Promise<unknown> {
  return parse(
    await fetch(`${API_BASE}/kernel/goals/${goalId}/cancel`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ reason }),
    }),
  );
}

export async function deleteGoal(goalId: string): Promise<unknown> {
  return parse(await fetch(`${API_BASE}/kernel/goals/${goalId}`, { method: 'DELETE' }));
}

export async function backupKernel(destination = '.gaia/backups/kernel-desktop'): Promise<unknown> {
  return parse(
    await fetch(`${API_BASE}/kernel/backup`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ destination }),
    }),
  );
}

export function openKernelEventStream(onEvent: (payload: KernelEvent | { events: KernelEvent[] }) => void): EventSource {
  const source = new EventSource(`${API_BASE}/kernel/events/stream`);
  source.addEventListener('snapshot', (event) => {
    const data = JSON.parse((event as MessageEvent).data) as { events: KernelEvent[] };
    onEvent(data);
  });
  source.addEventListener('kernel', (event) => {
    const data = JSON.parse((event as MessageEvent).data) as KernelEvent;
    onEvent(data);
  });
  return source;
}
