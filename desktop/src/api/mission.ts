export type Command<T> = {
  accepted: boolean;
  detail: string;
  data: T;
};

export type AgentDescriptor = {
  name: string;
  description: string;
  capabilities: string[];
  requires_human_approval: boolean;
};

export type MemoryStatus = {
  scopes: Record<string, number>;
  indexed_documents: number;
  symbolic_facts: number;
  pending_deletion_requests: number;
  vector_index: string;
  scores_calibrated: boolean;
  score_note: string;
};

export type MemoryRecord = {
  record_id: string;
  scope: string;
  owner_id: string;
  content: string;
  created_at: string;
};

export type RecallHit = MemoryRecord & {
  score: number;
  source: 'vector' | 'symbolic';
  score_calibrated: boolean;
};

export type SymbolicFact = {
  fact_id: string;
  subject: string;
  predicate: string;
  object_value: string;
  confidence: number;
  owner_id: string | null;
  score_calibrated: boolean;
};

export type ModelDescriptor = {
  model_id: string;
  provider: string;
  capabilities: string[];
  local_first: boolean;
  enabled: boolean;
  context_window: number | null;
};

export type ProviderHealth = {
  provider?: string;
  available?: boolean;
  reachable?: boolean;
  enabled?: boolean;
  deterministic?: boolean;
  neural_weights_loaded?: boolean;
  model_id?: string;
  models?: string[];
  detail?: string;
  reason?: string;
};

export type ModelHealth = {
  local_first: boolean;
  active_provider: string;
  working_model: string;
  ollama_reachable: boolean;
  ollama_models: string[];
  local_client: ProviderHealth;
  providers: {
    local: ProviderHealth;
    ollama: ProviderHealth;
    cloud: ProviderHealth;
  };
};

export type ToolStatus = {
  name: string;
  description: string;
  execution: string;
  permission: string | null;
  available: boolean;
  requires_human_approval: boolean;
  reason: string;
  executable: boolean;
};

export type ToolRunResult = {
  name: string;
  executed: boolean;
  shell: boolean;
  network: boolean;
  files_touched: boolean;
  result: {
    utc: string;
    echo: string;
  };
};

export type WorkspaceLink = {
  link_id: string;
  workspace_id: string;
  kind: 'task' | 'memory';
  ref_id: string;
  label: string;
  created_at: string;
};

export type WorkspaceRecord = {
  workspace_id: string;
  name: string;
  description: string;
  metadata: Record<string, unknown>;
  links: WorkspaceLink[];
  created_at: string;
  updated_at: string;
};

export type SecurityStatus = {
  status: string;
  autonomy_kill_switch: boolean;
  kill_switch_reason: string | null;
  risky_actions_require_permission: boolean;
  sandbox_required: boolean;
  human_override_available: boolean;
};

export type PermissionRule = {
  permission: string;
  resource_pattern: string;
  allowed: boolean;
  reason: string;
  human_approved: boolean;
};

export type AuditEvent = {
  event_id: string;
  action: string;
  actor: string;
  outcome: string;
  reason: string;
  resource: string;
  created_at: string;
};

export type PermissionDecision = {
  allowed: boolean;
  permission: string;
  resource: string;
  actor: string;
  reason: string;
  requires_human_approval: boolean;
  kill_switch_active: boolean;
};

export type Limitation = {
  name: string;
  description: string;
  severity: string;
};

export type SelfModelSnapshot = {
  identity: string;
  statement: string;
  capabilities: string[];
  limitations: Limitation[];
};

export type ReflectionReport = {
  confidence: {
    confidence: number;
    uncertainty: number;
    rationale: string;
  };
  critique: {
    strengths: string[];
    risks: string[];
    improvement_suggestions: string[];
  };
};

async function readBody(response: Response): Promise<string> {
  const text = await response.text();
  if (!text) {
    return `HTTP ${response.status}`;
  }
  try {
    const parsed = JSON.parse(text) as { detail?: unknown };
    if (typeof parsed.detail === 'string') {
      return parsed.detail;
    }
  } catch {
    return text;
  }
  return text;
}

export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    throw new Error(await readBody(response));
  }
  return (await response.json()) as T;
}

function postJson(path: string, body: unknown): Promise<Response> {
  return fetch(path, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function getAgents(): Promise<AgentDescriptor[]> {
  const payload = await requestJson<Command<{ agents: AgentDescriptor[]; count: number }>>(
    '/agents/status',
  );
  return payload.data.agents;
}

export async function getMemoryStatus(): Promise<MemoryStatus> {
  return requestJson<MemoryStatus>('/memory/status');
}

export async function writeMemory(content: string, ownerId: string, scope: string): Promise<MemoryRecord> {
  const response = await postJson('/memory', { content, owner_id: ownerId, scope });
  if (!response.ok) {
    throw new Error(await readBody(response));
  }
  return (await response.json()) as MemoryRecord;
}

export async function recallMemory(query: string, ownerId: string): Promise<RecallHit[]> {
  const response = await postJson('/memory/recall', { query, owner_id: ownerId, limit: 8 });
  if (!response.ok) {
    throw new Error(await readBody(response));
  }
  return (await response.json()) as RecallHit[];
}

export async function reviewMemory(ownerId: string): Promise<MemoryRecord[]> {
  return requestJson<MemoryRecord[]>(`/memory/review?owner_id=${encodeURIComponent(ownerId)}`);
}

export async function listFacts(ownerId: string): Promise<SymbolicFact[]> {
  return requestJson<SymbolicFact[]>(`/memory/facts?owner_id=${encodeURIComponent(ownerId)}`);
}

export async function addFact(
  ownerId: string,
  subject: string,
  predicate: string,
  objectValue: string,
): Promise<SymbolicFact> {
  const response = await postJson('/memory/facts', {
    owner_id: ownerId,
    subject,
    predicate,
    object_value: objectValue,
    confidence: 1,
  });
  if (!response.ok) {
    throw new Error(await readBody(response));
  }
  return (await response.json()) as SymbolicFact;
}

export async function getModels(): Promise<{ descriptors: ModelDescriptor[]; health: ModelHealth }> {
  const payload = await requestJson<
    Command<{ descriptors: ModelDescriptor[]; health: ModelHealth }>
  >('/models');
  return { descriptors: payload.data.descriptors, health: payload.data.health };
}

export async function getTools(): Promise<{
  execution: string;
  available: number;
  approval_gated: number;
  tools: ToolStatus[];
}> {
  const payload = await requestJson<
    Command<{
      execution: string;
      available: number;
      approval_gated: number;
      tools: ToolStatus[];
    }>
  >('/tools/status');
  return payload.data;
}

export async function runTool(name: string, text: string): Promise<ToolRunResult> {
  const response = await postJson('/tools/run', { name, text });
  if (!response.ok) {
    throw new Error(await readBody(response));
  }
  const payload = (await response.json()) as Command<ToolRunResult>;
  const result = payload.data;
  if (!result.executed || result.shell || result.network || result.files_touched) {
    throw new Error('Tool run reported a side effect');
  }
  return result;
}

export async function listWorkspaces(): Promise<WorkspaceRecord[]> {
  return requestJson<WorkspaceRecord[]>('/workspaces');
}

export async function createWorkspace(name: string, description: string): Promise<WorkspaceRecord> {
  const response = await postJson('/workspaces', { name, description, metadata: {} });
  if (!response.ok) {
    throw new Error(await readBody(response));
  }
  return (await response.json()) as WorkspaceRecord;
}

export async function attachWorkspaceLink(
  workspaceId: string,
  kind: 'task' | 'memory',
  refId: string,
  label: string,
): Promise<WorkspaceLink> {
  const response = await postJson(`/workspaces/${encodeURIComponent(workspaceId)}/links`, {
    kind,
    ref_id: refId,
    label,
  });
  if (!response.ok) {
    throw new Error(await readBody(response));
  }
  return (await response.json()) as WorkspaceLink;
}

export async function getSecurityStatus(): Promise<SecurityStatus> {
  return requestJson<SecurityStatus>('/security/status');
}

export async function getPermissionRules(): Promise<PermissionRule[]> {
  const payload = await requestJson<Command<{ rules: PermissionRule[] }>>('/security/permissions');
  return payload.data.rules;
}

export async function getAuditEvents(): Promise<AuditEvent[]> {
  const payload = await requestJson<Command<{ events: AuditEvent[] }>>('/security/audit?limit=12');
  return payload.data.events;
}

export async function setKillSwitch(enabled: boolean, reason: string): Promise<void> {
  const response = enabled
    ? await fetch(`/security/kill-switch?reason=${encodeURIComponent(reason)}`, { method: 'POST' })
    : await fetch('/security/kill-switch', { method: 'DELETE' });
  if (!response.ok) {
    throw new Error(await readBody(response));
  }
}

export async function checkPermission(
  permission: string,
  resource: string,
): Promise<PermissionDecision> {
  const response = await postJson('/security/check', {
    permission,
    resource,
    actor: 'mission-control',
  });
  if (!response.ok) {
    throw new Error(await readBody(response));
  }
  const payload = (await response.json()) as Command<PermissionDecision>;
  return payload.data;
}

export async function getSelfModel(): Promise<SelfModelSnapshot> {
  const payload = await requestJson<Command<SelfModelSnapshot>>('/self-model/status');
  return payload.data;
}

export async function reviewAnswer(answer: string): Promise<ReflectionReport> {
  const response = await postJson('/metacognition/review', {
    answer,
    signals: { coverage: answer.trim().length > 40 ? 0.7 : 0.4 },
  });
  if (!response.ok) {
    throw new Error(await readBody(response));
  }
  const payload = (await response.json()) as Command<ReflectionReport>;
  return payload.data;
}

export async function getMetacognitionStatus(): Promise<ReflectionReport | null> {
  const payload = await requestJson<Command<{ last_review: ReflectionReport | null }>>(
    '/metacognition/status',
  );
  return payload.data.last_review;
}

export type DreamStatus = {
  external_actions: boolean;
  blocks_shell: boolean;
  last_notes: string[];
  records: number;
};

export async function getDreamStatus(): Promise<DreamStatus> {
  const payload = await requestJson<Command<DreamStatus>>('/dreaming/status');
  return payload.data;
}

export async function runDream(futureGoal: string): Promise<string[]> {
  const response = await postJson('/dreaming/cycle', { future_goal: futureGoal });
  if (!response.ok) {
    throw new Error(await readBody(response));
  }
  const payload = (await response.json()) as Command<{ notes: string[]; external_actions: boolean }>;
  if (payload.data.external_actions) {
    throw new Error('Dream cycle reported an external action');
  }
  return payload.data.notes;
}

export async function getIdleStatus(): Promise<{ can_run_cycle: boolean; last_notes: string[] }> {
  const payload = await requestJson<
    Command<{ can_run_cycle: boolean; last_notes: string[]; external_actions: boolean }>
  >('/idle-cognition/status');
  return payload.data;
}
