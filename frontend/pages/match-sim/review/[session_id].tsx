import { useState, useEffect } from "react";
import { useRouter } from "next/router";
import { st } from "../../../lib/types";

const MATCH_DATA_BASE = "http://localhost:8080/api/match-data";

// ── Types ──────────────────────────────────────────────────────────────

interface PlayerSummary {
  name: string;
  position: string;
  shirt_number: number;
  rating: number;
}

interface MatchDetail {
  session_id: string;
  home_team_name: string;
  away_team_name: string;
  home_score: number;
  away_score: number;
  match_status: string;
  match_minute: number;
  home_formation: string;
  away_formation: string;
  stats?: {
    shots?: { home?: number; away?: number };
    shots_on_target?: { home?: number; away?: number };
    fouls?: { home?: number; away?: number };
    corners?: { home?: number; away?: number };
    offsides?: { home?: number; away?: number };
    yellows?: { home?: number; away?: number };
    reds?: { home?: number; away?: number };
    possession?: { home?: number; away?: number };
  };
  events?: MatchDetailEvent[];
  tactical_adjustments?: any[];
  lineup?: {
    active_players_home?: PlayerSummary[];
    active_players_away?: PlayerSummary[];
    bench_players_home?: PlayerSummary[];
    bench_players_away?: PlayerSummary[];
    home_substitutions_used?: number;
    away_substitutions_used?: number;
    home_attack_modifier?: number;
    home_defense_modifier?: number;
    away_attack_modifier?: number;
    away_defense_modifier?: number;
    home_morale?: number;
    away_morale?: number;
    match_tempo?: string;
  };
  winner?: string;
  created_at?: string;
  finished_at?: string;
}

interface MatchDetailEvent {
  event_id: string;
  event_type: string;
  event_subtype: string | null;
  team: string;
  actor_name: string | null;
  target_name: string | null;
  description: string;
  match_minute: number;
  half: number;
  importance: number;
  position: string | null;
  score: string | null;
}

const TEMPO_LABELS: Record<string, string> = {
  balanced: "正常", slow: "偏慢", very_slow: "很慢", high: "较快", very_high: "很快",
};

// ── Main Page ──────────────────────────────────────────────────────────

export default function MatchReview() {
  const router = useRouter();
  const { session_id } = router.query;

  const [detail, setDetail] = useState<MatchDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"events" | "stats" | "lineup">("events");

  useEffect(() => {
    if (!session_id) return;
    fetch(MATCH_DATA_BASE + "/match/" + session_id + "/detail")
      .then(r => r.json())
      .then(data => {
        if (data.match) setDetail(data.match);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [session_id]);

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#f0f2f5", color: "#64748b" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>⏳</div>
          <div style={{ fontWeight: 600 }}>加载比赛详情...</div>
        </div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#f0f2f5" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>❌</div>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>未找到比赛记录</div>
          <button onClick={() => router.push("/match-sim")} style={{ ...st.btn, background: "#667eea", color: "#fff", border: "none" }}>
            ← 返回
          </button>
        </div>
      </div>
    );
  }

  const stats = detail.stats || {};
  const lineup = detail.lineup || {};
  const events = detail.events || [];

  return (
    <div style={{ minHeight: "100vh", background: "#f0f2f5", fontFamily: "system-ui, sans-serif" }}>
      <style>{`@keyframes pulse { 0%,100% { opacity:1;transform:scale(1) } 50% { opacity:0.6;transform:scale(1.1) } }`}</style>

      {/* Top bar */}
      <div style={{ background: "#fff", borderBottom: "1px solid #e5e7eb", padding: "12px 24px", display: "flex", alignItems: "center", justifyContent: "space-between", position: "sticky", top: 0, zIndex: 50 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button onClick={() => router.push("/match-sim/history")} style={{ ...st.btn, ...st.sb, fontSize: 13 }}>← 返回历史</button>
          <span style={{ fontSize: 14, fontWeight: 600, color: "#374151" }}>{detail.home_team_name} vs {detail.away_team_name}</span>
        </div>
        <span style={{ fontSize: 12, color: "#94a3b8" }}>
          {detail.finished_at ? new Date(detail.finished_at).toLocaleString("zh-CN") : ""}
        </span>
      </div>

      <div style={{ maxWidth: 840, margin: "0 auto", padding: "20px 16px 80px" }}>
        {/* Scoreboard */}
        <Scoreboard detail={detail} />

        {/* Tabs */}
        <div style={{ display: "flex", gap: 4, marginTop: 16, background: "#fff", borderRadius: 12, padding: 4, boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}>
          {[
            { key: "events" as const, label: "📋 事件", count: events.length },
            { key: "stats" as const, label: "📊 数据" },
            { key: "lineup" as const, label: "👥 阵容" },
          ].map(tab => (
            <button key={tab.key} onClick={() => setActiveTab(tab.key)}
              style={{
                flex: 1, padding: "10px 16px", borderRadius: 10,
                border: "none", cursor: "pointer",
                background: activeTab === tab.key ? "linear-gradient(135deg, #667eea, #764ba2)" : "transparent",
                color: activeTab === tab.key ? "#fff" : "#64748b",
                fontWeight: activeTab === tab.key ? 600 : 400,
                fontSize: 14, transition: "all 0.2s",
              }}>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div style={{ marginTop: 12 }}>
          {activeTab === "events" && <EventFeed events={events} />}
          {activeTab === "stats" && <StatsPanel detail={detail} />}
          {activeTab === "lineup" && <LineupPanel detail={detail} lineup={lineup} />}
        </div>
      </div>
    </div>
  );
}

// ── Scoreboard ─────────────────────────────────────────────────────────

function Scoreboard({ detail }: { detail: MatchDetail }) {
  const s = detail.stats || {};
  const homePoss = (s.possession?.home != null ? s.possession.home : 50) as number;
  const awayPoss = (s.possession?.away != null ? s.possession.away : 50) as number;
  const total = homePoss + awayPoss;

  return (
    <div style={{ background: "#fff", borderRadius: 16, padding: "24px", boxShadow: "0 1px 3px rgba(0,0,0,0.08)", textAlign: "center" }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 16, alignItems: "center" }}>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: "#1e293b" }}>{detail.home_team_name}</div>
          <div style={{ fontSize: 12, color: "#94a3b8" }}>{detail.home_formation}</div>
        </div>
        <div>
          <div style={{ fontSize: 44, fontWeight: 800, letterSpacing: 4, display: "flex", alignItems: "center", justifyContent: "center", gap: 16 }}>
            <span style={{ color: "#2563eb" }}>{detail.home_score}</span>
            <span style={{ color: "#cbd5e1", fontSize: 24 }}>:</span>
            <span style={{ color: "#dc2626" }}>{detail.away_score}</span>
          </div>
          <div style={{ display: "inline-block", marginTop: 4, padding: "4px 14px", borderRadius: 20, fontSize: 13, fontWeight: 600, background: "#f0fdf4", color: "#16a34a" }}>
            比赛结束
          </div>
        </div>
        <div style={{ textAlign: "left" }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: "#1e293b" }}>{detail.away_team_name}</div>
          <div style={{ fontSize: 12, color: "#94a3b8" }}>{detail.away_formation}</div>
        </div>
      </div>

      {/* Possession */}
      <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: "#2563eb", minWidth: 40, textAlign: "right" }}>{Math.round((homePoss / total) * 100)}%</span>
        <div style={{ flex: 1, height: 6, background: "#f1f5f9", borderRadius: 3, overflow: "hidden", display: "flex" }}>
          <div style={{ height: "100%", width: `${(homePoss / total) * 100}%`, background: "linear-gradient(90deg, #2563eb, #60a5fa)", borderRadius: 3 }} />
        </div>
        <span style={{ fontSize: 12, fontWeight: 600, color: "#dc2626", minWidth: 40 }}>{Math.round((awayPoss / total) * 100)}%</span>
      </div>

      {detail.lineup && (
        <div style={{ display: "flex", justifyContent: "center", gap: 24, marginTop: 8, fontSize: 12, color: "#94a3b8" }}>
          <span>节奏: {TEMPO_LABELS[detail.lineup.match_tempo || ""] || detail.lineup.match_tempo || "正常"}</span>
          {detail.lineup.home_morale != null && (
            <span>士气: {Math.round(detail.lineup.home_morale * 100)}% / {Math.round(detail.lineup.away_morale! * 100)}%</span>
          )}
        </div>
      )}
    </div>
  );
}

// ── Event Feed ─────────────────────────────────────────────────────────

function EventFeed({ events }: { events: MatchDetailEvent[] }) {
  if (events.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: "60px 0", color: "#94a3b8", background: "#fff", borderRadius: 12 }}>
        <div style={{ fontSize: 40, marginBottom: 12 }}>⚪</div>
        <div>暂无事件记录</div>
      </div>
    );
  }

  const emoji = (e: MatchDetailEvent): string => {
    if (e.event_type === "goal") return "⚽";
    if (e.event_type === "card") return e.event_subtype === "red_card" ? "🟥" : "🟨";
    if (e.event_type === "save") return "🧤";
    if (e.event_type === "shot") return "💨";
    if (e.event_type === "foul") return "🦶";
    if (e.event_type === "corner" || e.event_type === "offside") return "🚩";
    if (e.event_type === "penalty") return "⚫";
    if (e.event_type === "free_kick") return "🛑";
    if (e.event_type === "substitution") return "🔄";
    if (e.event_type === "injury") return "🏥";
    if (e.event_type === "passage_of_play") return "⚡";
    if (e.event_type === "tactical_adjustment") return "📋";
    return "⚪";
  };

  return (
    <div style={{ background: "#fff", borderRadius: 12, boxShadow: "0 1px 3px rgba(0,0,0,0.06)", padding: 12, maxHeight: 520, overflowY: "auto" }}>
      {[...events].sort((a: any, b: any) => a.match_minute - b.match_minute).reverse().map((e: any, i: any) => (
        <div key={e.event_id || i} style={{
          display: "flex", gap: 12, padding: "10px 12px",
          borderBottom: i < events.length - 1 ? "1px solid #f1f5f9" : "none",
          background: e.event_type === "goal" ? "#f0fdf4" : "transparent",
          borderRadius: 10, marginBottom: 2,
        }}>
          <div style={{ fontSize: 20, width: 28, textAlign: "center", flexShrink: 0 }}>{emoji(e)}</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", gap: 8, alignItems: "baseline", marginBottom: 2 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: "#64748b" }}>{e.match_minute}'</span>
              <span style={{ fontSize: 12, color: e.team === "home" ? "#2563eb" : "#dc2626" }}>
                {e.team === "home" ? "主队" : "客队"}
              </span>
              {e.event_type === "goal" && <span style={{ fontSize: 12, color: "#16a34a", fontWeight: 700 }}>GOAL!</span>}
            </div>
            <div style={{ fontSize: 14, lineHeight: 1.5, color: "#374151" }}>
              {e.description || `${e.actor_name || ""} ${e.event_type}`}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Stats Panel ────────────────────────────────────────────────────────

function StatsPanel({ detail }: { detail: MatchDetail }) {
  const s = detail.stats || {};
  const rows = [
    { label: "射门", h: (s.shots as any)?.home ?? "-", a: (s.shots as any)?.away ?? "-" },
    { label: "射正", h: (s.shots_on_target as any)?.home ?? "-", a: (s.shots_on_target as any)?.away ?? "-" },
    { label: "犯规", h: (s.fouls as any)?.home ?? "-", a: (s.fouls as any)?.away ?? "-" },
    { label: "角球", h: (s.corners as any)?.home ?? "-", a: (s.corners as any)?.away ?? "-" },
    { label: "越位", h: (s.offsides as any)?.home ?? "-", a: (s.offsides as any)?.away ?? "-" },
    { label: "黄牌", h: (s.yellows as any)?.home ?? "-", a: (s.yellows as any)?.away ?? "-" },
    { label: "红牌", h: (s.reds as any)?.home ?? "-", a: (s.reds as any)?.away ?? "-" },
  ];

  return (
    <div style={{ background: "#fff", borderRadius: 12, boxShadow: "0 1px 3px rgba(0,0,0,0.06)", padding: 20 }}>
      {rows.map(row => {
        const hv = typeof row.h === "number" ? row.h : 0;
        const av = typeof row.a === "number" ? row.a : 0;
        const total = hv + av;
        const hPct = total > 0 ? (hv / total) * 100 : 50;
        return (
          <div key={row.label} style={{ display: "flex", alignItems: "center", gap: 12, padding: "8px 0", borderBottom: "1px solid #f1f5f9" }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: "#2563eb", minWidth: 28, textAlign: "right" }}>{row.h}</span>
            <div style={{ flex: 1, height: 6, background: "#f1f5f9", borderRadius: 3, overflow: "hidden", display: "flex" }}>
              <div style={{ height: "100%", width: `${hPct}%`, background: "#3b82f6", borderRadius: 3 }} />
            </div>
            <span style={{ fontSize: 14, fontWeight: 700, color: "#dc2626", minWidth: 28 }}>{row.a}</span>
            <div style={{ fontSize: 12, color: "#94a3b8", minWidth: 36, textAlign: "center" }}>{row.label}</div>
          </div>
        );
      })}
    </div>
  );
}

// ── Lineup Panel ───────────────────────────────────────────────────────

function LineupPanel({ detail, lineup }: { detail: MatchDetail; lineup: any }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
      <TeamLineup title={detail.home_team_name} formation={detail.home_formation}
        players={lineup.active_players_home || []} bench={lineup.bench_players_home || []}
        subsUsed={lineup.home_substitutions_used || 0} color="#2563eb" />
      <TeamLineup title={detail.away_team_name} formation={detail.away_formation}
        players={lineup.active_players_away || []} bench={lineup.bench_players_away || []}
        subsUsed={lineup.away_substitutions_used || 0} color="#dc2626" />
    </div>
  );
}

function TeamLineup({ title, formation, players, bench, subsUsed, color }: {
  title: string; formation: string; players: PlayerSummary[]; bench: PlayerSummary[]; subsUsed: number; color: string;
}) {
  return (
    <div style={{ background: "#fff", borderRadius: 12, boxShadow: "0 1px 3px rgba(0,0,0,0.06)", padding: 16 }}>
      <h3 style={{ margin: "0 0 4px", fontSize: 15, fontWeight: 700, color }}>{title}</h3>
      <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 12 }}>{formation}</div>
      <div style={{ fontSize: 12, color: "#64748b", fontWeight: 600, marginBottom: 6 }}>首发</div>
      {players.map((p: any) => (
        <div key={p.name} style={{ display: "flex", alignItems: "center", gap: 10, padding: "5px 8px", borderRadius: 6, marginBottom: 2, background: "#f8fafc" }}>
          <span style={{ fontSize: 12, color: "#94a3b8", minWidth: 24, fontWeight: 600 }}>#{p.shirt_number}</span>
          <span style={{ fontSize: 13, flex: 1, color: "#1e293b", fontWeight: 500 }}>{p.name}</span>
          <span style={{ fontSize: 12, color: "#94a3b8", minWidth: 36 }}>{p.position}</span>
          <span style={{ fontSize: 12, fontWeight: 700, color, background: `${color}10`, borderRadius: 6, padding: "1px 8px" }}>{p.rating}</span>
        </div>
      ))}
      <div style={{ fontSize: 12, color: "#64748b", fontWeight: 600, margin: "12px 0 6px" }}>替补</div>
      {bench.map((p: any) => (
        <div key={p.name} style={{ display: "flex", alignItems: "center", gap: 10, padding: "4px 8px", borderRadius: 6, marginBottom: 1 }}>
          <span style={{ fontSize: 12, color: "#94a3b8", minWidth: 24 }}>#{p.shirt_number}</span>
          <span style={{ fontSize: 13, flex: 1, color: "#475569" }}>{p.name}</span>
          <span style={{ fontSize: 12, color: "#94a3b8", minWidth: 36 }}>{p.position}</span>
          <span style={{ fontSize: 12, color: "#94a3b8" }}>{p.rating}</span>
        </div>
      ))}
      <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 8 }}>换人: {subsUsed}/5</div>
    </div>
  );
}
