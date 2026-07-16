export function ProgressBar({ step, message, progress }: { step: string; message: string; progress: number }) {
  const emoji: Record<string, string> = { rag: "📚", candidates: "🎯", debate: "🗣️", report: "📝", done: "✅" };
  return (
    <div style={{ marginBottom: 16, padding: 16, background: "#f0f9ff", borderRadius: 10, border: "1px solid #bae6fd" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <span>{emoji[step] || "⏳"}</span>
        <span style={{ fontSize: 14, color: "#0369a1", fontWeight: 500 }}>{message}</span>
      </div>
      <div style={{ width: "100%", height: 6, background: "#e0f2fe", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ width: progress + "%", height: "100%", background: "linear-gradient(90deg, #2563eb, #06b6d4)", borderRadius: 3, transition: "width 0.5s ease" }} />
      </div>
      <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4, textAlign: "right" }}>{progress}%</div>
    </div>
  );
}