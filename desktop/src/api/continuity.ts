const API_BASE = '';

export type ContinuityStatus = {
  capability: string;
  status: 'available' | 'degraded' | 'unavailable' | string;
  durable: boolean;
  reason?: string;
  backend?: string;
  schema_version?: number;
  local_first?: boolean;
  network?: string;
  encrypted_at_rest?: boolean;
  cryptographic_immutability?: boolean;
  checkpoint_count?: number;
  published_head?: string | null;
  integrity?: string;
  db_path?: string;
  limitations?: string[];
  approvals_reusable?: boolean;
};

export type CheckpointSummary = {
  checkpoint_id: string;
  parent_checkpoint_id: string | null;
  reason: string;
  publication: string;
  created_at: string;
  payload_sha256: string;
};

export type ContinuityTask = {
  task_id: string;
  goal_id: string;
  state: string;
  objective: string;
  updated_at: string;
};

export type VerifyResult = {
  checkpoint_id: string;
  verified: boolean;
  chain_ok: boolean;
  cryptographic_immutability: boolean;
};

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function getContinuityStatus(): Promise<ContinuityStatus> {
  return parse(await fetch(`${API_BASE}/kernel/continuity`));
}

export async function listContinuityCheckpoints(): Promise<{
  checkpoints: CheckpointSummary[];
  count: number;
  integrity_ok: boolean;
}> {
  return parse(await fetch(`${API_BASE}/kernel/continuity/checkpoints`));
}

export async function listContinuityTasks(): Promise<{ tasks: ContinuityTask[]; count: number }> {
  return parse(await fetch(`${API_BASE}/kernel/continuity/tasks`));
}

export async function publishContinuityCheckpoint(): Promise<{ checkpoint: CheckpointSummary }> {
  return parse(
    await fetch(`${API_BASE}/kernel/continuity/checkpoints`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
    }),
  );
}

export async function verifyContinuityCheckpoint(checkpointId: string): Promise<VerifyResult> {
  return parse(
    await fetch(`${API_BASE}/kernel/continuity/checkpoints/${encodeURIComponent(checkpointId)}/verify`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
    }),
  );
}
