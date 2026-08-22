import { useState, useEffect } from "react";
import { useRouter } from "next/router";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { API_BASE, st, Candidate, DebateMessage, parseJSONField } from "../../lib/types";
import { ChatBubble } from "../../components/ChatBubble";
import { RoundDivider } from "../../components/RoundDivider";

export default function SessionPage() {
  const router = useRouter();
  const { id } = router.query;
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    const savedUsername = localStorage.getItem("username");
    if (!token || !savedUsername) { router.replace("/login"); return; }
    if (!id) return;
    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/session/status?session_id=${id}`, {
          headers: { Authorization: "Bearer " + token },
        });
        if (res.status === 401) { localStorage.removeItem("token"); localStorage.removeItem("username"); router.replace("/login"); return; }
        if (!res.ok) { setError("会话不存在"); return; }
        const d = await res.json();
        setData(d);
        setError("");
      } catch {}
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, [id]);

  const queryText = data?.original_query || (typeof id === "string" ? id : "");
  const parsedCandidates = parseJSONField<Candidate[]>(data?.candidates_json, []);
  const candidates = Array.isArray(parsedCandidates) ? parsedCandidates : [];
  const parsedDebateMsgs = parseJSONField<DebateMessage[]>(data?.debate_json, []);
  const debateMsgs = Array.isArray(parsedDebateMsgs) ? parsedDebateMsgs : [];
  const parsedEliminated = parseJSONField<string[]>(data?.eliminated_json, []);
  const persistedEliminated = Array.isArray(parsedEliminated) ? parsedEliminated : [];
  const finalCandidate = parseJSONField<Candidate | null>(data?.final_candidate_json, null);
  const eliminated = Array.from(new Set([
    ...persistedEliminated,
    ...candidates
      .filter(candidate => debateMsgs.some(message =>
        message.type === "elimination" && message.content?.includes(`淘汰 ${candidate.name}`)
      ))
      .map(candidate => candidate.name),
  ]));
  const report = data?.final_report || "";
  const isComplete = data?.status === "completed";

  return (
    <div style={{ minHeight: "100vh", background: "#f8fafc", fontFamily: "system-ui, sans-serif" }}>
      <header style={{ background: "#fff", borderBottom: "1px solid #e2e8f0", position: "sticky", top: 0, zIndex: 10 }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "12px 24px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 24 }}>⚽</span>
            <span style={{ fontSize: 18, fontWeight: 700, color: "#0f172a" }}>Scout Agent</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button onClick={() => router.push("/history")} style={{ ...st.btn, ...st.sb, fontSize: 13 }}>📋 历史</button>
            <button onClick={() => router.push("/")} style={{ ...st.btn, ...st.pb, fontSize: 13 }}>🔍 新查询</button>
          </div>
        </div>
      </header>
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "24px" }}>
        {error ? (
          <div style={{ ...st.card, textAlign: "center", padding: 40 }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>❌</div>
            <div style={{ fontSize: 16, color: "#dc2626" }}>{error}</div>
          </div>
        ) : !data ? (
          <div style={{ ...st.card, textAlign: "center", padding: 60 }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>⏳</div>
            <div style={{ fontSize: 16, color: "#64748b" }}>正在加载会话数据...</div>
          </div>
        ) : (
          <div style={{ ...st.card }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 16, color: "#0f172a" }}>📡 会话状态</h3>
                <div style={{ fontSize: 13, color: "#64748b", marginTop: 4, maxWidth: 600, overflow: "hidden", textOverflow: "ellipsis" }}>
                  查询: {queryText}
                </div>
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                {isComplete
                  ? <span style={{ padding: "4px 10px", background: "#f0fdf4", borderRadius: 6, fontSize: 12, color: "#16a34a", fontWeight: 600, border: "1px solid #bbf7d0" }}>✅ 已完成</span>
                  : <span style={{ padding: "4px 10px", background: "#fffbeb", borderRadius: 6, fontSize: 12, color: "#92400e", fontWeight: 600, border: "1px solid #fde68a" }}>⏳ 处理中</span>
                }
                <span style={{ fontSize: 12, color: "#94a3b8" }}>{data.updated_at ? new Date(data.updated_at).toLocaleString("zh-CN") : ""}</span>
              </div>
            </div>

            {candidates.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <h4 style={{ margin: "0 0 10px", fontSize: 14, color: "#0f172a" }}>🎯 候选球员（{candidates.length}人）</h4>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 10 }}>
                  {candidates.map((c) => {
                    const isFinal = finalCandidate?.name === c.name;
                    const isEliminated = eliminated.includes(c.name) && !isFinal;
                    return (
                    <div key={c.name} style={{ padding: 12, borderRadius: 8, border: "1.5px solid " + (isFinal ? "#86efac" : isEliminated ? "#fecaca" : "#e2e8f0"), background: isFinal ? "#f0fdf4" : isEliminated ? "#fef2f2" : "#fff", opacity: isEliminated ? 0.58 : 1 }}>
                      <div style={{ fontSize: 14, fontWeight: 600, color: "#0f172a", marginBottom: 2 }}>{c.name}</div>
                      <div style={{ fontSize: 12, color: "#64748b" }}>{c.position} | {c.team}</div>
                      {isFinal && <div style={{ fontSize: 11, color: "#16a34a", fontWeight: 700, marginTop: 4 }}>🏆 最终推荐</div>}
                      {isEliminated && <div style={{ fontSize: 11, color: "#dc2626", fontWeight: 700, marginTop: 4 }}>❌ 已淘汰</div>}
                    </div>
                    );
                  })}
                </div>
              </div>
            )}

            {debateMsgs.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <h4 style={{ margin: "0 0 10px", fontSize: 14, color: "#0f172a" }}>🗣️ 辩论过程</h4>
                <div style={{ background: "#f8fafc", padding: 12, borderRadius: 8, maxHeight: 450, overflowY: "auto", border: "1px solid #e2e8f0" }}>
                  {(() => {
                    const els: React.JSX.Element[] = [];
                    let lastRound = 0;
                    debateMsgs.forEach((msg: any, i: number) => {
                      if (msg.round !== lastRound) { lastRound = msg.round; els.push(<RoundDivider key={"r" + msg.round} round={msg.round} />); }
                      els.push(<ChatBubble key={i} msg={{ ...msg, msg_id: msg.msg_id || ("h" + i) }} />);
                    });
                    return els;
                  })()}
                </div>
              </div>
            )}

            {isComplete && finalCandidate && (
              <div style={{ marginBottom: 16, padding: 16, background: "#f0fdf4", borderRadius: 8, border: "1px solid #86efac" }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: "#16a34a", marginBottom: 4 }}>🏆 最终推荐球员</div>
                <div style={{ fontSize: 15, fontWeight: 600, color: "#0f172a" }}>{finalCandidate.name}</div>
                <div style={{ fontSize: 13, color: "#475569" }}>{finalCandidate.position} | {finalCandidate.team}</div>
              </div>
            )}

            {isComplete && report && (
              <div>
                <h4 style={{ margin: "0 0 8px", fontSize: 14, color: "#0f172a" }}>📝 最终报告</h4>
                <div style={{ background: "#f8fafc", padding: 16, borderRadius: 8, lineHeight: 1.7, maxHeight: 500, overflowY: "auto", border: "1px solid #e2e8f0" }}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
                </div>
              </div>
            )}

            {!isComplete && candidates.length === 0 && (
              <div style={{ textAlign: "center", padding: 40, color: "#94a3b8", fontSize: 14 }}>
                <div style={{ fontSize: 32, marginBottom: 8 }}>⏳</div>
                分析进行中，数据将持续更新...
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
