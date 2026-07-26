import { useState, useEffect } from "react";
import { useRouter } from "next/router";
import { st } from "../../lib/types";

const MATCH_DATA_BASE = "http://localhost:8080/api/match-data";
interface MatchHistoryItem {
  session_id: string;
  home_team_name: string;
  away_team_name: string;
  home_score: number;
  away_score: number;
  match_status: string;
  match_minute: number;
  created_at: string | null;
  finished_at: string | null;
}

const STATUS_LABELS: Record<string, string> = {
  created: "已终止",
  first_half: "已终止",
  half_time: "已终止",
  second_half: "已终止",
  finished: "已结束",
};

function statusColor(s: string) {
  if (s === "finished") return { bg: "#f0fdf4", fg: "#16a34a" };
  return { bg: "#fffbeb", fg: "#d97706" };
}

export default function MatchHistory() {
  const router = useRouter();
  const [matches, setMatches] = useState<MatchHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }
    fetch(MATCH_DATA_BASE + "/matches", {
      headers: { Authorization: "Bearer " + token },
    })
      .then(r => r.json())
      .then(data => {
        setMatches(data.matches || []);
        setLoading(false);
      })
      .catch(() => { setError("无法加载历史记录"); setLoading(false); });
  }, [router]);

  const formatTime = (s: string | null) => {
    if (!s) return "";
    try {
      return new Date(s).toLocaleString("zh-CN", {
        month: "2-digit", day: "2-digit",
        hour: "2-digit", minute: "2-digit",
      });
    } catch {
      return s;
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: "#f0f2f5", fontFamily: "system-ui, sans-serif" }}>
      <header style={{ background: "#fff", borderBottom: "1px solid #e5e7eb", padding: "12px 24px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button onClick={() => router.push("/match-sim")} style={{ ...st.btn, ...st.sb, fontSize: 13 }}>← 返回</button>
          <span style={{ fontSize: 18, fontWeight: 700, color: "#1e293b" }}>📋 历史比赛记录</span>
        </div>
      </header>

      <div style={{ maxWidth: 800, margin: "0 auto", padding: "20px 16px" }}>
        {error && (
          <div style={{ padding: "14px 20px", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 12, marginBottom: 16, color: "#dc2626", fontSize: 14 }}>
            {error}
          </div>
        )}

        {loading ? (
          <div style={{ textAlign: "center", padding: "60px 0", color: "#94a3b8" }}>
            <div style={{ fontSize: 40, marginBottom: 12, animation: "pulse 1.4s ease-in-out infinite" }}>⏳</div>
            <div style={{ fontWeight: 600 }}>加载中...</div>
          </div>
        ) : matches.length === 0 ? (
          <div style={{ textAlign: "center", padding: "60px 0", color: "#94a3b8", background: "#fff", borderRadius: 16, boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>🏟️</div>
            <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 4 }}>暂无历史比赛记录</div>
            <div style={{ fontSize: 13 }}>开始一场新的比赛，记录会自动保存</div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {matches.map((m, i) => (
              <button
                key={m.session_id || `match-${i}`}
                onClick={() => m.session_id && router.push("/match-sim/review/" + m.session_id)}
                style={{
                  display: "flex", alignItems: "center", gap: 16,
                  width: "100%", padding: "16px 20px",
                  background: "#fff", border: "1px solid #e5e7eb",
                  borderRadius: 14, cursor: "pointer",
                  textAlign: "left", transition: "all 0.15s",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
                }}
              >
                {/* Date */}
                <div style={{ minWidth: 80, fontSize: 12, color: "#94a3b8" }}>
                  {formatTime(m.created_at)}
                </div>

                {/* Teams */}
                <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 15, fontWeight: 700, color: "#2563eb", minWidth: 90, textAlign: "right" }}>{m.home_team_name}</span>
                  <span style={{ fontSize: 13, color: "#94a3b8" }}>vs</span>
                  <span style={{ fontSize: 15, fontWeight: 700, color: "#dc2626", minWidth: 90 }}>{m.away_team_name}</span>
                </div>

                {/* Score */}
                <div style={{ fontSize: 22, fontWeight: 800, color: "#1e293b", minWidth: 60, textAlign: "center" }}>
                  {m.home_score} : {m.away_score}
                </div>

                {/* Status */}
                <div style={{
                  fontSize: 12, fontWeight: 600,
                  padding: "4px 12px", borderRadius: 20,
                  background: statusColor(m.match_status).bg,
                  color: statusColor(m.match_status).fg,
                }}>
                  {m.match_status === "finished" ? "已结束" : "已终止"}
                </div>

                {/* Arrow */}
                <span style={{ fontSize: 16, color: "#cbd5e1" }}>→</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
