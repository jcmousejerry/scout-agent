import { useState, useEffect } from "react";
import { useRouter } from "next/router";
import { API_BASE, st } from "../../lib/types";

interface Team {
  id: number;
  name: string;
  short_name: string;
  league: string;
  country: string;
  strength_rating: number;
  default_formation: string;
}

const FORMATIONS = ["4-3-3", "4-4-2", "3-5-2", "4-2-3-1", "3-4-3", "5-3-2", "4-1-4-1", "4-3-2-1"];

const LEAGUE_ORDER: Record<string, number> = {
  "Premier League": 1, "La Liga": 2, "Bundesliga": 3, "Serie A": 4, "Ligue 1": 5, "Eredivisie": 6, "Primeira Liga": 7,
};

const LEAGUE_COLORS: Record<string, string> = {
  "Premier League": "#38003c",
  "La Liga": "#c90b1b",
  "Bundesliga": "#d40511",
  "Serie A": "#00469b",
  "Ligue 1": "#004170",
};

export default function MatchSimLobby() {
  const router = useRouter();
  const [teams, setTeams] = useState<Team[]>([]);
  const [homeTeam, setHomeTeam] = useState<number | null>(null);
  const [awayTeam, setAwayTeam] = useState<number | null>(null);
  const [homeFormation, setHomeFormation] = useState("4-3-3");
  const [awayFormation, setAwayFormation] = useState("4-3-3");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }
    fetch(API_BASE + "/match-sim/teams", {
      headers: { Authorization: "Bearer " + token },
    })
      .then(r => r.json())
      .then(data => {
        const sorted = [...(data.teams || [])].sort(
          (a: Team, b: Team) => (LEAGUE_ORDER[a.league] || 99) - (LEAGUE_ORDER[b.league] || 99) || b.strength_rating - a.strength_rating
        );
        setTeams(sorted);
        setLoading(false);
      })
      .catch(() => { setError("无法加载球队数据"); setLoading(false); });
  }, [router]);

  const groupedTeams = teams.reduce<Record<string, Team[]>>((acc, t) => {
    (acc[t.league] = acc[t.league] || []).push(t);
    return acc;
  }, {});

  const handleStart = async () => {
    if (!homeTeam || !awayTeam) { setError("请选择主队和客队"); return; }
    if (homeTeam === awayTeam) { setError("主队和客队不能相同"); return; }
    setCreating(true);
    setError("");
    const token = localStorage.getItem("token");
    try {
      const res = await fetch(API_BASE + "/match-sim/match/create", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
        body: JSON.stringify({
          home_team_id: homeTeam,
          away_team_id: awayTeam,
          home_formation: homeFormation,
          away_formation: awayFormation,
        }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error || data.detail || "创建失败"); setCreating(false); return; }
      router.push("/match-sim/" + data.session_id);
    } catch {
      setError("网络错误，请检查后端服务"); setCreating(false);
    }
  };

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)", color: "#fff", fontSize: 16 }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 48, marginBottom: 16, animation: "pulse 1.4s ease-in-out infinite" }}>⚽</div>
          <div style={{ fontWeight: 600 }}>正在加载球队数据...</div>
        </div>
      </div>
    );
  }

  const homeTeamData = homeTeam ? teams.find(t => t.id === homeTeam) : null;
  const awayTeamData = awayTeam ? teams.find(t => t.id === awayTeam) : null;

  return (
    <div style={{ minHeight: "100vh", background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)", fontFamily: "system-ui, sans-serif" }}>
      <style>{`@keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1) } 50% { opacity: 0.6; transform: scale(1.1) } }
        @keyframes slideUp { from { opacity: 0; transform: translateY(20px) } to { opacity: 1; transform: translateY(0) } }`}</style>

      <header style={{ padding: "16px 24px", display: "flex", alignItems: "center", justifyContent: "space-between", background: "rgba(255,255,255,0.1)", backdropFilter: "blur(10px)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 28 }}>⚽</span>
          <span style={{ fontSize: 18, fontWeight: 700, color: "#fff" }}>比赛策略战术模拟</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button onClick={() => router.push("/match-sim/history")} style={{ padding: "8px 20px", fontSize: 13, fontWeight: 600, borderRadius: 10, border: "1.5px solid rgba(255,255,255,0.3)", background: "rgba(255,255,255,0.15)", color: "#fff", cursor: "pointer" }}>
            📋 历史记录
          </button>
          <button onClick={() => router.push("/")} style={{ padding: "8px 20px", fontSize: 13, fontWeight: 600, borderRadius: 10, border: "1.5px solid rgba(255,255,255,0.3)", background: "rgba(255,255,255,0.15)", color: "#fff", cursor: "pointer" }}>
            ← 返回首页
          </button>
        </div>
      </header>

      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 24px", animation: "slideUp 0.5s ease" }}>
        <h1 style={{ fontSize: 32, fontWeight: 800, textAlign: "center", margin: "0 0 8px", color: "#fff" }}>🏟️ 新比赛</h1>
        <p style={{ textAlign: "center", color: "rgba(255,255,255,0.7)", fontSize: 15, margin: "0 0 32px" }}>选择两支球队，AI 将自动生成一场完整的比赛</p>

        {error && (
          <div style={{ padding: "14px 20px", background: "rgba(239,68,68,0.15)", border: "1px solid rgba(239,68,68,0.4)", borderRadius: 12, marginBottom: 24, color: "#fca5a5", fontSize: 14, textAlign: "center", backdropFilter: "blur(8px)" }}>
            {error}
          </div>
        )}

        {/* VS Banner */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 20, marginBottom: 32 }}>
          <div style={{
            flex: 1, textAlign: "right", padding: "16px 24px",
            background: "rgba(255,255,255,0.12)", borderRadius: 16,
            backdropFilter: "blur(8px)", border: "1.5px solid rgba(255,255,255,0.15)",
          }}>
            <div style={{ fontSize: 14, color: "rgba(255,255,255,0.5)", marginBottom: 4 }}>主队</div>
            <div style={{ fontSize: 22, fontWeight: 800, color: homeTeamData ? "#fff" : "rgba(255,255,255,0.3)" }}>
              {homeTeamData ? homeTeamData.short_name : "?"}
            </div>
            <div style={{ fontSize: 13, color: "rgba(255,255,255,0.5)", marginTop: 2 }}>
              {homeTeamData ? homeTeamData.name : "未选择"}
            </div>
          </div>
          <div style={{ fontSize: 36, fontWeight: 900, color: "rgba(255,255,255,0.6)", textShadow: "0 2px 10px rgba(0,0,0,0.2)" }}>VS</div>
          <div style={{
            flex: 1, padding: "16px 24px",
            background: "rgba(255,255,255,0.12)", borderRadius: 16,
            backdropFilter: "blur(8px)", border: "1.5px solid rgba(255,255,255,0.15)",
          }}>
            <div style={{ fontSize: 14, color: "rgba(255,255,255,0.5)", marginBottom: 4 }}>客队</div>
            <div style={{ fontSize: 22, fontWeight: 800, color: awayTeamData ? "#fff" : "rgba(255,255,255,0.3)" }}>
              {awayTeamData ? awayTeamData.short_name : "?"}
            </div>
            <div style={{ fontSize: 13, color: "rgba(255,255,255,0.5)", marginTop: 2 }}>
              {awayTeamData ? awayTeamData.name : "未选择"}
            </div>
          </div>
        </div>

        {/* Team selection */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          <TeamSelectSide
            label="主队"
            teams={groupedTeams}
            selectedId={homeTeam}
            formation={homeFormation}
            color="#3b82f6"
            onTeamChange={setHomeTeam}
            onFormationChange={setHomeFormation}
          />
          <TeamSelectSide
            label="客队"
            teams={groupedTeams}
            selectedId={awayTeam}
            formation={awayFormation}
            color="#f97316"
            onTeamChange={setAwayTeam}
            onFormationChange={setAwayFormation}
          />
        </div>

        {/* Start button */}
        <div style={{ textAlign: "center", marginTop: 32 }}>
          <button
            onClick={handleStart}
            disabled={!homeTeam || !awayTeam || creating || homeTeam === awayTeam}
            style={{
              padding: "18px 72px",
              fontSize: 20,
              fontWeight: 800,
              borderRadius: 16,
              border: "none",
              cursor: (!homeTeam || !awayTeam || creating || homeTeam === awayTeam) ? "not-allowed" : "pointer",
              background: (!homeTeam || !awayTeam || homeTeam === awayTeam)
                ? "rgba(255,255,255,0.15)"
                : "linear-gradient(135deg, #f97316, #ef4444)",
              color: "#fff",
              opacity: creating ? 0.7 : 1,
              boxShadow: (!homeTeam || !awayTeam || homeTeam === awayTeam) ? "none" : "0 8px 32px rgba(249,115,22,0.35)",
              transition: "all 0.3s",
              letterSpacing: 1,
            }}
          >
            {creating ? "⚙️ 正在创建比赛..." : "🔔 开球！"}
          </button>
          <div style={{ marginTop: 12, fontSize: 13, color: "rgba(255,255,255,0.5)" }}>
            AI 模拟 90 分钟比赛 · 约 45 秒完赛 · 可随时战术调整
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Team Selection Side Panel ───────────────────────────────────────────

function TeamSelectSide({
  label, teams, selectedId, formation, color, onTeamChange, onFormationChange,
}: {
  label: string;
  teams: Record<string, Team[]>;
  selectedId: number | null;
  formation: string;
  color: string;
  onTeamChange: (id: number) => void;
  onFormationChange: (f: string) => void;
}) {
  return (
    <div style={{ background: "rgba(255,255,255,0.95)", borderRadius: 16, padding: 20, boxShadow: "0 8px 32px rgba(0,0,0,0.12)" }}>
      <h3 style={{ fontSize: 15, fontWeight: 700, margin: "0 0 16px", color, textAlign: "center" }}>{label}</h3>

      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 12, color: "#64748b", fontWeight: 600, marginBottom: 8 }}>阵型</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {["4-3-3", "4-4-2", "3-5-2", "4-2-3-1", "3-4-3", "5-3-2", "4-1-4-1", "4-3-2-1"].map(f => (
            <button key={f} onClick={() => onFormationChange(f)}
              style={{
                padding: "5px 12px", fontSize: 12, fontWeight: 600, borderRadius: 8, border: "1.5px solid",
                borderColor: formation === f ? color : "#e2e8f0",
                background: formation === f ? `${color}15` : "#f8fafc",
                color: formation === f ? color : "#64748b",
                cursor: "pointer", transition: "all 0.15s",
              }}>
              {f}
            </button>
          ))}
        </div>
      </div>

      <div style={{ maxHeight: 400, overflowY: "auto" }}>
        {Object.entries(teams).map(([league, leagueTeams]) => (
          <div key={league} style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 1.5, marginBottom: 6 }}>
              {league}
            </div>
            {leagueTeams.map(t => (
              <button key={t.id} onClick={() => onTeamChange(t.id)}
                style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  width: "100%", padding: "10px 14px", marginBottom: 4,
                  borderRadius: 10, border: "1.5px solid",
                  borderColor: selectedId === t.id ? color : "#f1f5f9",
                  background: selectedId === t.id ? `${color}08` : "#fff",
                  color: selectedId === t.id ? "#0f172a" : "#334155",
                  cursor: "pointer", textAlign: "left",
                  boxShadow: selectedId === t.id ? `0 2px 8px ${color}20` : "none",
                  transition: "all 0.15s",
                }}
              >
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600 }}>{t.short_name}</div>
                  <div style={{ fontSize: 11, color: "#94a3b8" }}>{t.name}</div>
                </div>
                <span style={{ fontSize: 12, fontWeight: 700, color: "#64748b", background: "#f1f5f9", borderRadius: 8, padding: "3px 10px" }}>
                  {t.strength_rating}
                </span>
              </button>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
