export default function HomePage() {
  return (
    <div className="min-h-[calc(100vh-45px)] bg-clinsight-bg">
      <header className="flex h-14 items-center gap-4 border-b border-clinsight-border bg-white px-6">
        <div className="flex items-center gap-2 text-lg font-bold text-clinsight-navy">
          <i
            aria-hidden="true"
            className="relative h-6 w-6 rounded-[7px] bg-clinsight-teal inline-block"
          >
            <span className="absolute inset-[5px] rounded-full border-[3px] border-white" />
          </i>
          <span>Clinsight</span>
        </div>
      </header>
      <div className="p-8">
        <div className="max-w-xl rounded-xl border border-clinsight-border bg-white p-6 shadow-sm">
          <h1 className="text-xl font-bold text-clinsight-navy">Clinsight</h1>
          <p className="mt-2 text-sm text-clinsight-muted">
            Clinical decision-support workspace skeleton initialized.
          </p>
        </div>
      </div>
    </div>
  );
}
