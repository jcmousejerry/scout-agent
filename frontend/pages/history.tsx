import { useState, useEffect } from "react";
import { useRouter } from "next/router";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { API_BASE, st, Candidate, DebateMessage, HistoryItem, parseJSONField } from "../lib/types";
import { ChatBubble } from "../components/ChatBubble";
import { RoundDivider } from "../components/RoundDivider";

function CandidateOutcomeSummary({ item }: { item: HistoryItem }) {
  const parsedCandidates = parseJSONField<Candidate[]>(item.candidates_json, []);
  const candidates = Array.isArray(parsedCandidates) ? parsedCandidates : [];
  const finalCandidate = parseJSONField<Candidate | null>(item.final_candidate_json, null);
  const parsedEliminated = parseJSONField<string[]>(item.eliminated_json, []);
  const debateMessages = parseJSONField<DebateMessage[]>(item.debate_json, []);
  const eliminated = new Set(Array.isArray(parsedEliminated) ? parsedEliminated : []);

  // Backfill legacy history rows: completed sessions have exactly one winner,
  // so every other candidate was eliminated even if eliminated_json was absent.
  if (finalCandidate?.name) {
    candidates.forEach(candidate => {
      if (candidate.name !== finalCandidate.name) eliminated.add(candidate.name);
    });
  }
  if (Array.isArray(debateMessages)) {
    candidates.forEach(candidate => {
      if (debateMessages.some(message =>
        message.type === "elimination" && message.content?.includes(`淘汰 ${candidate.name}`)
      )) eliminated.add(candidate.name);
    });
  }

  if (candidates.length === 0) return null;

  return (
    <div style={{ marginBottom: 18 }}>
      <h4 style={{ margin: "0 0 10px", fontSize: 14, color: "#0f172a" }}>🎯 候选球员与最终结果</h4>
      {finalCandidate && (
        <div style={{ marginBottom: 10, padding: "9px 12px", background: "#f0fdf4", border: "1px solid #86efac", borderRadius: 8, color: "#166534", fontSize: 13, fontWeight: 700 }}>
          🏆 最终推荐：{finalCandidate.name}（{finalCandidate.position}，{finalCandidate.team}）
        </div>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))", gap: 8 }}>
        {candidates.map(candidate => {
          const isFinal = finalCandidate?.name === candidate.name;
          const isEliminated = eliminated.has(candidate.name) && !isFinal;
          return (
            <div key={candidate.name} style={{
              padding: "10px 12px", borderRadius: 8,
              background: isFinal ? "#f0fdf4" : isEliminated ? "#fef2f2" : "#f8fafc",
              border: `1.5px solid ${isFinal ? "#86efac" : isEliminated ? "#fecaca" : "#e2e8f0"}`,
              opacity: isEliminated ? 0.65 : 1,
            }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#0f172a" }}>{candidate.name}</div>
              <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>{candidate.position} | {candidate.team}</div>
              {isFinal && <div style={{ fontSize: 12, color: "#16a34a", fontWeight: 700, marginTop: 5 }}>🏆 最终推荐</div>}
              {isEliminated && <div style={{ fontSize: 12, color: "#dc2626", fontWeight: 700, marginTop: 5 }}>❌ 已淘汰</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function HistoryPage() {
  const router = useRouter();
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [viewing, setViewing] = useState<HistoryItem | null>(null);
  const [username, setUsername] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    const savedUsername = localStorage.getItem("username");
    if (!token || !savedUsername) { router.replace("/login"); return; }
    setUsername(savedUsername);
    fetch(API_BASE + "/history", { headers: { Authorization: "Bearer " + token } })
      .then(r => {
        if (r.status === 401) { localStorage.removeItem("token"); localStorage.removeItem("username"); router.replace("/login"); return null; }
        return r.json();
      })
      .then(d => { if (d?.history) setHistory(d.history); })
      .catch(() => {});
  }, []);

  return (
    <div style={{ minHeight: "100vh", background: "#f8fafc", fontFamily: "system-ui, sans-serif" }}>
      <header style={{ background: "#fff", borderBottom: "1px solid #e2e8f0", position: "sticky", top: 0, zIndex: 10 }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "12px 24px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 24 }}>⚽</span>
            <span style={{ fontSize: 18, fontWeight: 700, color: "#0f172a" }}>Scout Agent</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button onClick={() => router.push("/")} style={{ ...st.btn, ...st.sb, fontSize: 13 }}>🔍 新查询</button>
            <span style={{ fontSize: 14, color: "#64748b" }}>{username}</span>
          </div>
        </div>
      </header>
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "24px" }}>
        {!viewing ? (
          <div style={{ ...st.card }}>
            <h3 style={{ margin: "0 0 16px", fontSize: 16, color: "#0f172a" }}>📋 历史查询记录</h3>
            {history.length === 0 && <p style={{ color: "#94a3b8", fontSize: 14 }}>暂无历史记录</p>}
            {history.map((item) => (
              <div key={item.id} onClick={() => setViewing(item)} style={{ padding: "12px 16px", borderBottom: "1px solid #f1f5f9", cursor: "pointer", borderRadius: 8 }}
                onMouseOver={e => e.currentTarget.style.background = "#f8fafc"} onMouseOut={e => e.currentTarget.style.background = "transparent"}>
                <div style={{ fontSize: 14, fontWeight: 500, color: "#0f172a", marginBottom: 4 }}>{item.query.slice(0, 60)}{item.query.length > 60 ? "..." : ""}</div>
                <div style={{ fontSize: 12, color: "#94a3b8" }}>{new Date(item.created_at).toLocaleString("zh-CN")} · {item.retrieved_count} 条检索</div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ ...st.card }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h3 style={{ margin: 0, fontSize: 16, color: "#0f172a" }}>📄 历史报告详情</h3>
              <button onClick={() => setViewing(null)} style={{ ...st.btn, ...st.sb, fontSize: 12, padding: "4px 12px" }}>返回</button>
            </div>
            <div style={{ fontSize: 13, color: "#64748b", marginBottom: 12 }}>查询: {viewing.query}</div>
            <div style={{ fontSize: 13, color: "#64748b", marginBottom: 16 }}>时间: {new Date(viewing.created_at).toLocaleString("zh-CN")}</div>
            <CandidateOutcomeSummary item={viewing} />
            {viewing.debate_json && (() => {
              const parsed = parseJSONField<DebateMessage[]>(viewing.debate_json, []);
              const msgs = Array.isArray(parsed) ? parsed : [];
              if (!msgs.length) return null;
              return (
                <div style={{ marginBottom: 16 }}>
                  <h4 style={{ margin: "0 0 8px", fontSize: 14, color: "#0f172a" }}>🗣️ 辩论过程（{msgs.length} 条消息）</h4>
                  <div style={{ background: "#f8fafc", padding: 12, borderRadius: 8, maxHeight: 400, overflowY: "auto", border: "1px solid #e2e8f0" }}>
                    {(() => { const els: React.JSX.Element[] = []; let lastRound = 0; msgs.forEach((msg, i) => { if (msg.round !== lastRound) { lastRound = msg.round; els.push(<RoundDivider key={"r" + msg.round} round={msg.round} />); } els.push(<ChatBubble key={i} msg={{ ...msg, msg_id: msg.msg_id || ("h" + i) }} />); }); return els; })()}
                  </div>
                </div>
              );
            })()}
            <h4 style={{ margin: "0 0 8px", fontSize: 14, color: "#0f172a" }}>📝 最终报告</h4>
            <div style={{ background: "#f8fafc", padding: 16, borderRadius: 8, lineHeight: 1.7, overflowX: "auto" }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{viewing.report}</ReactMarkdown>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
