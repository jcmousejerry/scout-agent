export function RoundDivider({ round }: { round: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", margin: "20px 0 16px" }}>
      <div style={{ padding: "4px 16px", background: "#f1f5f9", borderRadius: 20, fontSize: 12, fontWeight: 600, color: "#64748b", border: "1px solid #e2e8f0" }}>
        — 第 {round} 轮专家讨论 —
      </div>
    </div>
  );
}