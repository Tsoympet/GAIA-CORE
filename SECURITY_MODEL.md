# GAIA Security Model

GAIA is secure-by-default and local-first. The foundation implements policy evaluation, permission records, an audit trail, and an autonomy kill switch. The long-term security model is capability-based: agents, tools, model providers, plugins, and scheduled tasks must declare what they need before execution.

## Principles

- Human override is always available.
- Risky operations require explicit approval before execution.
- Local execution is preferred; cloud fallback is disabled unless configured.
- Dreaming and idle cognition are internal-only modes and must never execute external actions.
- Self-modification is proposal-only until reviewed and approved.
- All security decisions should be inspectable in runtime memory and audit logs.

## Risky Operations

The policy model treats the following operations as approval-gated:

- shell execution
- file deletion or destructive overwrite
- package installation
- Git push or remote repository mutation
- GitHub operations
- network calls
- API key usage
- external communication
- self-modification
- scheduled autonomous actions

## Implemented Foundation

- `SecurityPolicy.evaluate_objective()` blocks known unsafe objectives before orchestration.
- `PermissionManager` records granted/denied permission decisions.
- Guard modules define command, file, network, self-modification, and autonomy boundaries.
- `/security/kill-switch` exposes a server-side autonomy stop control.

## Roadmap

1. Replace keyword blocking with signed policy files and declarative risk classes.
2. Add append-only audit logs with integrity checks.
3. Add approval workflow APIs for pending actions.
4. Add sandbox adapters for Python, shell, Docker, browser, and file tools.
5. Add rollback points for repo/file-changing actions.
