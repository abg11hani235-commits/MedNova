export function BriefSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading">
      <div className="skel" style={{ width: "40%", height: 28 }} />
      <div className="card"><div className="skel" /><div className="skel" style={{ width: "85%" }} /><div className="skel" style={{ height: 120 }} /></div>
      <p className="muted">Preparing the brief…</p>
    </div>
  );
}

export function EmptyState({ title, text }: { title: string; text: string }) {
  return (
    <div className="card">
      <b>{title}</b>
      <p className="muted">{text}</p>
    </div>
  );
}

export function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="card" role="alert">
      <span className="sev urgent">Something went wrong</span>
      <p>The data could not be loaded.</p>
      <button className="btn" onClick={onRetry}>Retry</button>
    </div>
  );
}
