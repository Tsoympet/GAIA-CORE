import { useEffect, useState } from 'react';
import {
  checkPermission,
  getAuditEvents,
  getPermissionRules,
  getSecurityStatus,
  setKillSwitch,
  type AuditEvent,
  type PermissionDecision,
  type PermissionRule,
  type SecurityStatus,
} from '../api/mission';
import { SurfaceFrame } from '../components/SurfaceFrame';

const PERMISSIONS = [
  'shell.command',
  'file.read',
  'file.write',
  'network.access',
  'secret.read',
  'self.modify',
];

export function SecurityPage() {
  const [status, setStatus] = useState<SecurityStatus | null>(null);
  const [rules, setRules] = useState<PermissionRule[]>([]);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [reason, setReason] = useState('operator pause from mission control');
  const [permission, setPermission] = useState('shell.command');
  const [resource, setResource] = useState('ls');
  const [decision, setDecision] = useState<PermissionDecision | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const [nextStatus, nextRules, nextEvents] = await Promise.all([
      getSecurityStatus(),
      getPermissionRules(),
      getAuditEvents(),
    ]);
    setStatus(nextStatus);
    setRules(nextRules);
    setEvents(nextEvents);
  }

  useEffect(() => {
    void refresh().catch((err: unknown) => {
      setError(err instanceof Error ? err.message : 'Security status failed');
    });
  }, []);

  async function toggle(enabled: boolean) {
    setBusy(true);
    try {
      await setKillSwitch(enabled, reason.trim() || 'operator pause');
      await refresh();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Kill switch failed');
    } finally {
      setBusy(false);
    }
  }

  async function reviewPermission() {
    setBusy(true);
    try {
      setDecision(await checkPermission(permission, resource.trim() || '*'));
      await refresh();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Permission check failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <SurfaceFrame
      label="Security"
      eyebrow="Permissions"
      title="Kill switch and audit"
      lede="The kill switch is the same one the runtime checks. Reviewing a permission does not grant it. Risky tools stay approval-gated."
      signal={status?.autonomy_kill_switch ? 'kill switch on' : 'kill switch off'}
      error={error}
    >
      <section className="kernelWorkbench">
        <article className="kernelPanel">
          <label className="fieldLabel" htmlFor="kill-reason">
            Kill switch reason
          </label>
          <input id="kill-reason" value={reason} onChange={(event) => setReason(event.target.value)} />
          <div className="kernelActions">
            <button type="button" onClick={() => void toggle(true)} disabled={busy}>
              Enable kill switch
            </button>
            <button type="button" onClick={() => void toggle(false)} disabled={busy}>
              Reset kill switch
            </button>
          </div>
          <p className="muted">
            {status?.kill_switch_reason
              ? `Current reason: ${status.kill_switch_reason}`
              : 'No kill-switch reason is stored.'}
          </p>
          <label className="fieldLabel" htmlFor="permission-name">
            Permission check
          </label>
          <select
            id="permission-name"
            value={permission}
            onChange={(event) => setPermission(event.target.value)}
          >
            {PERMISSIONS.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          <label className="fieldLabel" htmlFor="permission-resource">
            Resource
          </label>
          <input
            id="permission-resource"
            value={resource}
            onChange={(event) => setResource(event.target.value)}
          />
          <div className="kernelActions">
            <button type="button" onClick={() => void reviewPermission()} disabled={busy}>
              Review permission
            </button>
          </div>
          {decision ? (
            <p>
              {decision.permission} on {decision.resource} is {decision.allowed ? 'allowed' : 'denied'}.{' '}
              {decision.reason}
              {decision.requires_human_approval ? ' Human approval is still required.' : ''}
            </p>
          ) : (
            <p className="muted">A check writes an audit event and does not change the rule.</p>
          )}
        </article>
        <article className="kernelPanel">
          <div className="panelHeader">
            <h2>Rules</h2>
            <span>{rules.length}</span>
          </div>
          <ul className="goalList">
            {rules.map((rule) => (
              <li key={`${rule.permission}-${rule.resource_pattern}-${rule.reason}`}>
                <strong>
                  {rule.permission} · {rule.allowed ? 'allow' : 'deny'}
                </strong>
                <span>
                  {rule.resource_pattern} · {rule.reason}
                </span>
              </li>
            ))}
          </ul>
          <h2>Recent audit</h2>
          <ul className="goalList">
            {events.map((event) => (
              <li key={event.event_id}>
                <strong>
                  {event.outcome} · {event.action}
                </strong>
                <span>
                  {event.actor} · {event.resource} · {event.reason}
                </span>
              </li>
            ))}
          </ul>
        </article>
      </section>
    </SurfaceFrame>
  );
}
