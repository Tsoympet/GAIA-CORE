const API_BASE = '';

export type OrganismStatus = {
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
  policy_effect?: string;
  memory_count?: number;
  categories?: Record<string, number>;
  evidence?: {
    status?: string;
    cryptographic_immutability?: boolean;
    record_count?: number;
  };
  retrieval?: {
    default_ranker?: string;
    available_rankers?: string[];
    neural_embeddings?: boolean;
    uncalibrated?: boolean;
    index?: {
      documents?: number;
      term_postings?: number;
      ngram_postings?: number;
      hashed_terms?: boolean;
    };
  };
  db_path?: string;
  continuity_checkpoints_bound?: boolean;
  limitations?: string[];
};

export type OrganismMemory = {
  memory_id: string;
  category: string;
  status: string;
  content: string | null;
  content_sha256: string;
  owner_id: string;
  project_id: string | null;
  confidence: number;
  approved_knowledge: boolean;
  policy_effect: string;
  untrusted_instruction: boolean;
  source_evidence_ids: string[];
  source_memory_ids: string[];
  event_at: string | null;
  created_at: string;
};

export type RetrievalHit = {
  memory: OrganismMemory;
  score: number;
  effective_status: string;
  ranker: string;
  components?: {
    lexical: number;
    ngram: number;
    metadata: number;
    recency: number;
    confidence: number;
    ranker: string;
  } | null;
};

export type SearchResult = {
  hits: RetrievalHit[];
  count: number;
  ranker: string;
  uncalibrated: boolean;
  neural_embeddings: boolean;
};

export type TimelineResult = {
  entries: OrganismMemory[];
  count: number;
};

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function getOrganismStatus(): Promise<OrganismStatus> {
  return parse(await fetch(`${API_BASE}/organism/status`));
}

export async function searchOrganismMemories(
  query: string,
  options: {
    ownerId?: string;
    mode?: 'hybrid' | 'bm25';
    includeIdentity?: boolean;
    includePreference?: boolean;
  } = {},
): Promise<SearchResult> {
  const params = new URLSearchParams({ q: query, mode: options.mode ?? 'hybrid' });
  if (options.ownerId) {
    params.set('owner_id', options.ownerId);
  }
  if (options.includeIdentity) {
    params.set('include_identity', 'true');
  }
  if (options.includePreference) {
    params.set('include_preference', 'true');
  }
  return parse(await fetch(`${API_BASE}/organism/memories/search?${params.toString()}`));
}

export async function listOrganismTimeline(
  ownerId: string,
): Promise<TimelineResult> {
  const params = new URLSearchParams({ owner_id: ownerId });
  return parse(await fetch(`${API_BASE}/organism/timeline?${params.toString()}`));
}

export async function appendOrganismEvidence(content: string): Promise<{ evidence: { evidence_id: string } }> {
  return parse(
    await fetch(`${API_BASE}/organism/evidence`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        source: 'user',
        origin: 'desktop',
        content,
        producer: 'operator',
      }),
    }),
  );
}

export async function recordOrganismMemory(
  evidenceId: string,
  ownerId: string,
): Promise<{ memory: OrganismMemory }> {
  return parse(
    await fetch(`${API_BASE}/organism/memories`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        evidence_id: evidenceId,
        owner_id: ownerId,
        category: 'episodic',
      }),
    }),
  );
}

export async function proposeOrganismCandidate(
  content: string,
  sourceMemoryIds: string[],
  ownerId: string,
): Promise<{ memory: OrganismMemory }> {
  return parse(
    await fetch(`${API_BASE}/organism/memories/candidates`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        content,
        category: 'semantic',
        source_memory_ids: sourceMemoryIds,
        owner_id: ownerId,
        confidence: 0.6,
      }),
    }),
  );
}

export async function validateOrganismMemory(
  memoryId: string,
  passed: boolean,
): Promise<{ memory: OrganismMemory }> {
  return parse(
    await fetch(`${API_BASE}/organism/memories/${encodeURIComponent(memoryId)}/validate`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ passed, notes: passed ? 'desktop validation' : 'desktop rejection' }),
    }),
  );
}

export async function approveOrganismMemory(
  memoryId: string,
): Promise<{ memory: OrganismMemory; policy_effect: string }> {
  return parse(
    await fetch(`${API_BASE}/organism/memories/${encodeURIComponent(memoryId)}/approve`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ approver: 'operator' }),
    }),
  );
}
