import { useState, useEffect } from "react";
import { useRouter } from "next/router";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { API_BASE, st, HistoryItem } from "../lib/types";
import { ChatBubble } from "../components/ChatBubble";
import { RoundDivider } from "../components/RoundDivider";

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
            {viewing.candidates_json && (() => {
              try { const cands = JSON.parse(viewing.candidates_json); return (
                <div style={{ marginBottom: 16 }}>
                  <h4 style={{ margin: "0 0 8px", fontSize: 14, color: "#0f172a" }}>🎯 候选球员</h4>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>{cands.map((c: any, i: number) => (
                    <span key={i} style={{ padding: "4px 10px", background: "#f0fdf4", borderRadius: 6, fontSize: 13, color: "#16a34a", border: "1px solid #bbf7d0" }}>{c.name} ({c.position}, {c.team})</span>
                  ))}</div>
                </div>
              ); } catch { return null; }
            })()}
            {viewing.debate_json && (() => {
              try { const msgs = JSON.parse(viewing.debate_json); if (!msgs.length) return null; return (
                <div style={{ marginBottom: 16 }}>
                  <h4 style={{ margin: "0 0 8px", fontSize: 14, color: "#0f172a" }}>🗣️ 辩论过程（{msgs.length} 条消息）</h4>
                  <div style={{ background: "#f8fafc", padding: 12, borderRadius: 8, maxHeight: 400, overflowY: "auto", border: "1px solid #e2e8f0" }}>
                    {(() => { const els: React.JSX.Element[] = []; let lastRound = 0; msgs.forEach((msg: any, i: number) => { if (msg.round !== lastRound) { lastRound = msg.round; els.push(<RoundDivider key={"r" + msg.round} round={msg.round} />); } els.push(<ChatBubble key={i} msg={{ ...msg, msg_id: msg.msg_id || ("h" + i) }} />); }); return els; })()}
                  </div>
                </div>
              ); } catch { return null; }
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