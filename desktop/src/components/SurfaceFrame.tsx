import type { ReactNode } from 'react';

export function SurfaceFrame({
  label,
  eyebrow,
  title,
  lede,
  signal,
  error,
  children,
}: {
  label: string;
  eyebrow: string;
  title: string;
  lede: string;
  signal?: string;
  error: string | null;
  children: ReactNode;
}) {
  return (
    <section className="kernelPage" aria-label={label}>
      <header className="kernelHeader">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
          <p>{lede}</p>
        </div>
        {signal ? (
          <div className="kernelSignals">
            <span>{signal}</span>
          </div>
        ) : null}
      </header>
      {error ? <p className="kernelError">{error}</p> : null}
      {children}
    </section>
  );
}
