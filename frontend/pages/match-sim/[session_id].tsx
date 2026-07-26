import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/router";
import { API_BASE, st } from "../../lib/types";

// ── Types ───────────────────────────────────────────────────────────────

interface PlayerSummary {
  name: string;
  position: string;
  shirt_number: number;
  rating: number;
}

interface MatchSnapshot {
  session_id: string;
  match_id: number;
  home_team: string;
  away_team: string;
  home_score: number;
  away_score: number;
  match_minute: number;
  match_half: number;
  match_status: string;
  is_paused?: boolean;
  home_formation: string;
  away_formation: string;
  home_attack_modifier: number;
  home_defense_modifier: number;
  away_attack_modifier: number;
  away_defense_modifier: number;
  home_morale: number;
  away_morale: number;
  match_tempo: string;
  home_substitutions_used: number;
  away_substitutions_used: number;
  home_tactical_cooldown: number;
  away_tactical_cooldown: number;
  stats: {
    home_shots: number; away_shots: number;
    home_shots_on_target: number; away_shots_on_target: number;
    home_fouls: number; away_fouls: number;
    home_corners: number; away_corners: number;
    home_offsides: number; away_offsides: number;
    home_yellows: number; away_yellows: number;
    home_reds: number; away_reds: number;
    home_possession: number; away_possession: number;
  };
  active_players_home: PlayerSummary[];
  active_players_away: PlayerSummary[];
  bench_players_home: PlayerSummary[];
  bench_players_away: PlayerSummary[];
}

interface MatchEventData {
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
  home_score?: number;
  away_score?: number;
}

interface SSEPayload {
  type: string;
  session_id: string;
  data: any;
}

// Use direct Go backend URL for SSE to avoid Next.js rewrite buffering
const SSE_BASE = "http://localhost:8080/api";

const TEMPO_LABELS: Record<string, string> = {
  balanced: "正常", slow: "偏慢", very_slow: "很慢", high: "较快", very_high: "很快",
};

// ── Main page ───────────────────────────────────────────────────────────

export default function MatchView() {
  const router = useRouter();
  const { session_id } = router.query;

  const [state, setState] = useState<MatchSnapshot | null>(null);
  const [events, setEvents] = useState<MatchEventData[]>([]);
  const [narrative, setNarrative] = useState("");
  const [connected, setConnected] = useState(false);
  const [finished, setFinished] = useState(false);
  const [paused, setPaused] = useState(false);
  const [activeTab, setActiveTab] = useState<"events" | "stats" | "lineup">("events");
  const [showTactical, setShowTactical] = useState(false);
  const [adjMsg, setAdjMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [showSubModal, setShowSubModal] = useState(false);
  const [subOff, setSubOff] = useState("");
  const [subOn, setSubOn] = useState("");
  const [showFormationModal, setShowFormationModal] = useState(false);
  const [newFormation, setNewFormation] = useState("");

  const eventFeedRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // When new events arrive, scroll the event panel to top (newest events)
  // AND scroll the browser window to top
  useEffect(() => {
    if (eventFeedRef.current) {
      eventFeedRef.current.scrollTop = 0;
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [events]);

  const fetchState = useCallback(async () => {
    if (!session_id) return;
    try {
      const res = await fetch(SSE_BASE + "/match-sim/match/" + session_id + "/state");
      if (res.ok) {
        const data = await res.json();
        if (data.match) {
          setState(data.match);
          if (typeof data.match.is_paused === "boolean") setPaused(data.match.is_paused);
        }
      }
    } catch { /* ignore */ }
  }, [session_id]);

  // Connect SSE
  useEffect(() => {
    if (!session_id) return;
    const es = new EventSource(SSE_BASE + "/match-sim/match/" + session_id + "/events");
    eventSourceRef.current = es;
    setConnected(true);

    es.addEventListener("match_state", (e: MessageEvent) => {
      try {
        const payload: SSEPayload = JSON.parse(e.data);
        if (payload.data) {
          setState(payload.data);
          if (typeof payload.data.is_paused === "boolean") setPaused(payload.data.is_paused);
        }
      } catch { /* ignore */ }
    });

    es.addEventListener("match_event", (e: MessageEvent) => {
      try {
        const payload: SSEPayload = JSON.parse(e.data);
        if (payload.data) {
          setEvents(prev => {
            // 按 event_id 去重，防止同一事件被重复推送
            const exists = payload.data.event_id && prev.some(ev => (ev as any).event_id === payload.data.event_id);
            return exists ? prev : [...prev, payload.data];
          });
          if (payload.data.home_score !== undefined && payload.data.away_score !== undefined) {
            setState(prev => prev ? {
              ...prev,
              home_score: payload.data.home_score,
              away_score: payload.data.away_score,
            } : prev);
          }
        }
      } catch { /* ignore */ }
    });

    es.addEventListener("half_time", (e: MessageEvent) => {
      try {
        const payload: SSEPayload = JSON.parse(e.data);
        if (payload.data) {
          setState(payload.data);
          if (payload.data.narrative) setNarrative(payload.data.narrative);
        }
      } catch { /* ignore */ }
    });

    es.addEventListener("full_time", (e: MessageEvent) => {
      try {
        const payload: SSEPayload = JSON.parse(e.data);
        if (payload.data) {
          setState(payload.data);
          if (payload.data.narrative) setNarrative(payload.data.narrative);
          setFinished(true);
        }
      } catch { /* ignore */ }
    });

    es.addEventListener("tactical_adjustment", () => { fetchState(); });
    es.addEventListener("match_paused", () => { setPaused(true); });
    es.addEventListener("match_resumed", () => { setPaused(false); });

    es.onerror = () => { setConnected(false); };

    const pollTimer = setInterval(fetchState, 5000);

    return () => { es.close(); eventSourceRef.current = null; clearInterval(pollTimer); };
  }, [session_id, fetchState]);

  const doAdjustment = async (type: string, from?: string, to?: string, reason?: string) => {
    try {
      const res = await fetch(API_BASE + "/match-sim/match/" + session_id + "/adjust", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type, from_value: from || null, to_value: to || null, reason: reason || null }),
      });
      const data = await res.json();
      if (res.ok) {
        setAdjMsg({ ok: true, text: data.message || "战术调整已执行" });
        fetchState();
      } else {
        setAdjMsg({ ok: false, text: data.detail || data.error || "调整失败" });
      }
    } catch {
      setAdjMsg({ ok: false, text: "网络错误" });
    }
    setTimeout(() => setAdjMsg(null), 3000);
  };

  const handleFormationChange = async () => {
    if (!newFormation || newFormation === state?.home_formation) { setShowFormationModal(false); return; }
    await doAdjustment("formation_change", undefined, newFormation, "变阵为" + newFormation);
    setShowFormationModal(false);
  };

  const handleSubstitution = async () => {
    if (!subOff || !subOn) { setAdjMsg({ ok: false, text: "请选择换下和换上球员" }); return; }
    await doAdjustment("substitution", subOff, subOn, subOff + " → " + subOn);
    setShowSubModal(false);
    setSubOff(""); setSubOn("");
  };

  const handlePauseResume = async (action: "pause" | "resume") => {
    try {
      const res = await fetch(API_BASE + "/match-sim/match/" + session_id + "/" + action, { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setPaused(action === "pause");
        setAdjMsg({ ok: true, text: data.message || (action === "pause" ? "比赛已暂停" : "比赛已继续") });
      } else {
        setAdjMsg({ ok: false, text: data.detail || data.error || "操作失败" });
      }
    } catch {
      setAdjMsg({ ok: false, text: "网络错误" });
    }
    setTimeout(() => setAdjMsg(null), 3000);
  };

  const handleStop = async () => {
    await fetch(API_BASE + "/match-sim/match/" + session_id + "/stop", { method: "POST" });
    router.push("/match-sim");
  };

  // ── Render ──
  if (!state) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)", color: "#fff" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 56, marginBottom: 16, animation: "pulse 1.4s ease-in-out infinite" }}>⚽</div>
          <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>连接中...</div>
          <div style={{ fontSize: 14, color: "rgba(255,255,255,0.6)" }}>等待比赛开始</div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: "#f0f2f5", fontFamily: "system-ui, sans-serif" }}>
      <style>{`@keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1) } 50% { opacity: 0.6; transform: scale(1.1) } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(6px) } to { opacity: 1; transform: translateY(0) } }
        @keyframes scorePop { 0% { transform: scale(1) } 50% { transform: scale(1.25) } 100% { transform: scale(1) } }`}</style>

      {/* ── Top bar ── */}
      <div style={{ background: "#fff", borderBottom: "1px solid #e5e7eb", padding: "12px 24px", display: "flex", alignItems: "center", justifyContent: "space-between", position: "sticky", top: 0, zIndex: 50 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button onClick={() => router.push("/match-sim")} style={{ ...st.btn, ...st.sb, fontSize: 13 }}>← 返回</button>
          <span style={{ fontSize: 14, fontWeight: 600, color: "#374151" }}>{state.home_team} vs {state.away_team}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: connected ? "#16a34a" : "#ef4444" }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: connected ? "#16a34a" : "#ef4444", display: "inline-block" }} />
            {connected ? "已连接" : "已断开"}
          </span>
          {paused && (
            <span style={{ fontSize: 12, fontWeight: 600, color: "#f59e0b", background: "#fffbeb", border: "1px solid #fde68a", borderRadius: 20, padding: "3px 10px" }}>⏸ 已暂停</span>
          )}
          <button onClick={() => handlePauseResume("pause")} disabled={paused || finished}
            title="暂停比赛"
            style={{ ...st.btn, ...st.sb, fontSize: 12, opacity: (paused || finished) ? 0.5 : 1, cursor: (paused || finished) ? "not-allowed" : "pointer" }}>⏸</button>
          <button onClick={() => handlePauseResume("resume")} disabled={!paused || finished}
            title="继续比赛"
            style={{ ...st.btn, ...st.sb, fontSize: 12, opacity: (!paused || finished) ? 0.5 : 1, cursor: (!paused || finished) ? "not-allowed" : "pointer" }}>▶</button>
          <button onClick={handleStop} style={{ ...st.btn, background: "#fee2e2", color: "#dc2626", fontSize: 12, border: "none" }}>⏹</button>
        </div>
      </div>

      <div style={{ maxWidth: 840, margin: "0 auto", padding: "20px 16px 120px" }}>
        {/* ── Scoreboard ── */}
        <Scoreboard state={state} finished={finished} paused={paused} />

        {/* Feedback message */}
        {adjMsg && (
          <div style={{
            padding: "12px 20px", borderRadius: 12, marginTop: 12,
            background: adjMsg.ok ? "#f0fdf4" : "#fef2f2",
            border: "1px solid " + (adjMsg.ok ? "#86efac" : "#fecaca"),
            color: adjMsg.ok ? "#16a34a" : "#dc2626",
            fontSize: 14, textAlign: "center",
            animation: "fadeIn 0.3s",
          }}>
            {adjMsg.ok ? "✅ " : "❌ "}{adjMsg.text}
          </div>
        )}

        {/* Narrative */}
        {narrative && (
          <div style={{
            marginTop: 12, padding: "14px 18px", borderRadius: 12, fontSize: 14, lineHeight: 1.7,
            background: finished ? "#f0fdf4" : "#fffbeb",
            border: "1px solid " + (finished ? "#86efac" : "#fde68a"),
            color: "#374151",
          }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: finished ? "#16a34a" : "#d97706", marginBottom: 4 }}>
              {finished ? "🏆 比赛结束" : "⏸ 半场总结"}
            </div>
            {narrative}
          </div>
        )}

        {/* ── Tabs ── */}
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

        {/* ── Tab Content ── */}
        <div style={{ marginTop: 12 }}>
          {activeTab === "events" && <EventFeed events={events} containerRef={eventFeedRef} />}
          {activeTab === "stats" && <StatsPanel state={state} />}
          {activeTab === "lineup" && <LineupPanel state={state} />}
        </div>

        {finished && (
          <div style={{ textAlign: "center", marginTop: 20 }}>
            <button onClick={() => router.push("/match-sim")} style={{ ...st.btn, background: "linear-gradient(135deg, #667eea, #764ba2)", color: "#fff", fontSize: 15, padding: "14px 48px", border: "none" }}>
              🔔 开始新比赛
            </button>
          </div>
        )}
      </div>

      {/* ── Floating tactical button ── */}
      {!finished && (
        <>
          <button onClick={() => setShowTactical(!showTactical)}
            style={{
              position: "fixed", bottom: 24, right: 24, zIndex: 100,
              width: 60, height: 60, borderRadius: "50%",
              background: "linear-gradient(135deg, #667eea, #764ba2)",
              color: "#fff", border: "none", cursor: "pointer",
              fontSize: 28, boxShadow: "0 4px 20px rgba(102,126,234,0.4)",
              transition: "transform 0.2s",
              transform: showTactical ? "rotate(45deg)" : "none",
            }}>
            {showTactical ? "+" : "⚙"}
          </button>

          {showTactical && (
            <TacticalPanel
              state={state}
              onAdjust={doAdjustment}
              onOpenSub={() => setShowSubModal(true)}
              onOpenFormation={() => { setNewFormation(state.home_formation); setShowFormationModal(true); }}
              onClose={() => setShowTactical(false)}
            />
          )}

          {/* Substitution modal */}
          {showSubModal && (
            <Modal title="换人" onClose={() => setShowSubModal(false)}>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 13, color: "#64748b", fontWeight: 600, marginBottom: 6 }}>换下</div>
                <select value={subOff} onChange={e => setSubOff(e.target.value)} style={modalSelect}>
                  <option value="">选择球员...</option>
                  {state.active_players_home.map(p => (
                    <option key={p.name} value={p.name}>{p.shirt_number}. {p.name} ({p.position})</option>
                  ))}
                </select>
              </div>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 13, color: "#64748b", fontWeight: 600, marginBottom: 6 }}>换上</div>
                <select value={subOn} onChange={e => setSubOn(e.target.value)} style={modalSelect}>
                  <option value="">选择球员...</option>
                  {state.bench_players_home.map(p => (
                    <option key={p.name} value={p.name}>{p.shirt_number}. {p.name} ({p.position})</option>
                  ))}
                </select>
              </div>
              <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 16 }}>已用换人次数：{state.home_substitutions_used}/5</div>
              <button onClick={handleSubstitution} disabled={!subOff || !subOn}
                style={{ ...st.btn, background: "linear-gradient(135deg, #667eea, #764ba2)", color: "#fff", width: "100%", border: "none", opacity: subOff && subOn ? 1 : 0.5 }}>
                确认换人
              </button>
            </Modal>
          )}

          {/* Formation modal */}
          {showFormationModal && (
            <Modal title="变阵" onClose={() => setShowFormationModal(false)}>
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 13, color: "#64748b", fontWeight: 600, marginBottom: 8 }}>选择新阵型</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {["4-3-3", "4-4-2", "3-5-2", "4-2-3-1", "3-4-3", "5-3-2", "4-1-4-1", "4-3-2-1"].map(f => (
                    <button key={f} onClick={() => setNewFormation(f)}
                      style={{
                        padding: "10px 18px", borderRadius: 10, border: "1.5px solid",
                        borderColor: newFormation === f ? "#667eea" : "#e5e7eb",
                        background: newFormation === f ? "#eef2ff" : "#fff",
                        color: newFormation === f ? "#667eea" : "#64748b",
                        cursor: "pointer", fontSize: 14, fontWeight: newFormation === f ? 700 : 400,
                      }}>
                      {f}
                    </button>
                  ))}
                </div>
              </div>
              <button onClick={handleFormationChange}
                style={{ ...st.btn, background: "linear-gradient(135deg, #667eea, #764ba2)", color: "#fff", width: "100%", border: "none" }}>
                确认变阵
              </button>
            </Modal>
          )}
        </>
      )}
    </div>
  );
}

// ── Scoreboard ──────────────────────────────────────────────────────────

function Scoreboard({ state, finished, paused }: { state: MatchSnapshot; finished: boolean; paused: boolean }) {
  const statusText = (() => {
    if (paused) return "已暂停";
    switch (state.match_status) {
      case "created": return "即将开球";
      case "first_half": return `${state.match_minute}'`;
      case "half_time": return "中场休息";
      case "second_half": return `${state.match_minute}'`;
      case "finished": return "比赛结束";
      default: return state.match_status;
    }
  })();

  const homePoss = state.stats.home_possession || 50;
  const awayPoss = state.stats.away_possession || 50;

  return (
    <div style={{
      background: "#fff", borderRadius: 16, padding: "24px",
      boxShadow: "0 1px 3px rgba(0,0,0,0.08)", textAlign: "center",
    }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 16, alignItems: "center" }}>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: "#1e293b" }}>{state.home_team}</div>
          <div style={{ fontSize: 12, color: "#94a3b8" }}>{state.home_formation}</div>
        </div>
        <div>
          <div style={{ fontSize: 44, fontWeight: 800, letterSpacing: 4, display: "flex", alignItems: "center", justifyContent: "center", gap: 16 }}>
            <span style={{ color: "#2563eb" }}>{state.home_score}</span>
            <span style={{ color: "#cbd5e1", fontSize: 24 }}>:</span>
            <span style={{ color: "#dc2626" }}>{state.away_score}</span>
          </div>
          <div style={{
            display: "inline-block", marginTop: 4,
            padding: "4px 14px", borderRadius: 20,
            fontSize: 13, fontWeight: 600,
            background: finished ? "#f0fdf4" : paused ? "#fffbeb" : "#f1f5f9",
            color: finished ? "#16a34a" : paused ? "#d97706" : "#475569",
          }}>
            {statusText}{!finished && !paused && state.match_half === 1 ? " · 上半场" : !finished && !paused ? " · 下半场" : ""}
          </div>
        </div>
        <div style={{ textAlign: "left" }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: "#1e293b" }}>{state.away_team}</div>
          <div style={{ fontSize: 12, color: "#94a3b8" }}>{state.away_formation}</div>
        </div>
      </div>

      {/* Possession bar */}
      <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: "#2563eb", minWidth: 40, textAlign: "right" }}>{Math.round(homePoss)}%</span>
        <div style={{ flex: 1, height: 6, background: "#f1f5f9", borderRadius: 3, overflow: "hidden", display: "flex" }}>
          <div style={{ height: "100%", width: `${(homePoss / (homePoss + awayPoss)) * 100}%`, background: "linear-gradient(90deg, #2563eb, #60a5fa)", borderRadius: 3 }} />
        </div>
        <span style={{ fontSize: 12, fontWeight: 600, color: "#dc2626", minWidth: 40 }}>{Math.round(awayPoss)}%</span>
      </div>

      <div style={{ display: "flex", justifyContent: "center", gap: 24, marginTop: 8, fontSize: 12, color: "#94a3b8" }}>
        <span>节奏: {TEMPO_LABELS[state.match_tempo] || state.match_tempo}</span>
        <span>士气: {Math.round(state.home_morale * 100)}% / {Math.round(state.away_morale * 100)}%</span>
      </div>
    </div>
  );
}

// ── Event Feed ──────────────────────────────────────────────────────────

function EventFeed({ events, containerRef }: { events: MatchEventData[]; containerRef: React.RefObject<HTMLDivElement | null> }) {
  if (events.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: "60px 0", color: "#94a3b8", background: "#fff", borderRadius: 12, boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}>
        <div style={{ fontSize: 40, marginBottom: 12, animation: "pulse 1.4s ease-in-out infinite" }}>⏳</div>
        <div style={{ fontWeight: 600 }}>等待第一个比赛事件...</div>
      </div>
    );
  }

  const eventEmoji = (e: MatchEventData): string => {
    if (e.event_type === "goal") return "⚽";
    if (e.event_type === "card") return e.event_subtype === "red_card" ? "🟥" : "🟨";
    if (e.event_type === "save") return "🧤";
    if (e.event_type === "shot") return "💨";
    if (e.event_type === "foul") return "🦶";
    if (e.event_type === "corner") return "🚩";
    if (e.event_type === "offside") return "🚩";
    if (e.event_type === "penalty") return "⚫";
    if (e.event_type === "free_kick") return "🛑";
    if (e.event_type === "substitution") return "🔄";
    if (e.event_type === "injury") return "🏥";
    if (e.event_type === "passage_of_play") return "⚡";
    if (e.event_type === "tactical_adjustment") return "📋";
    return "⚪";
  };

  // Sort by match_minute asc, then reverse for latest-first display
  const reversed = [...events].sort((a, b) => a.match_minute - b.match_minute).reverse();

  return (
    <div ref={containerRef} style={{ background: "#fff", borderRadius: 12, boxShadow: "0 1px 3px rgba(0,0,0,0.06)", padding: 12, maxHeight: 520, overflowY: "auto" }}>
      {reversed.map((e, i) => {
        const isGoal = e.event_type === "goal";
        return (
          <div key={e.event_id || i} style={{
            display: "flex", gap: 12, padding: "10px 12px",
            borderBottom: i < reversed.length - 1 ? "1px solid #f1f5f9" : "none",
            animation: "fadeIn 0.4s ease",
            background: isGoal ? "#f0fdf4" : "transparent",
            borderRadius: 10, marginBottom: i < reversed.length - 1 ? 2 : 0,
          }}>
            <div style={{ fontSize: 20, width: 28, textAlign: "center", flexShrink: 0 }}>{eventEmoji(e)}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", gap: 8, alignItems: "baseline", marginBottom: 2 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: "#64748b" }}>{e.match_minute}'</span>
                <span style={{ fontSize: 12, color: e.team === "home" ? "#2563eb" : "#dc2626" }}>
                  {e.team === "home" ? stateLabel("home") : stateLabel("away")}
                </span>
                {isGoal && <span style={{ fontSize: 12, color: "#16a34a", fontWeight: 700 }}>GOAL!</span>}
              </div>
              <div style={{ fontSize: 14, lineHeight: 1.5, color: "#374151" }}>
                {e.description || `${e.actor_name} ${e.event_type}`}
              </div>
              {e.score && <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 2 }}>比分: {e.score}</div>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function stateLabel(_team: string): string {
  return _team === "home" ? "主队" : "客队";
}

// ── Stats Panel ─────────────────────────────────────────────────────────

function StatsPanel({ state }: { state: MatchSnapshot }) {
  const s = state.stats;
  const rows = [
    { label: "射门", h: s.home_shots, a: s.away_shots },
    { label: "射正", h: s.home_shots_on_target, a: s.away_shots_on_target },
    { label: "犯规", h: s.home_fouls, a: s.away_fouls },
    { label: "角球", h: s.home_corners, a: s.away_corners },
    { label: "越位", h: s.home_offsides, a: s.away_offsides },
    { label: "黄牌", h: s.home_yellows, a: s.away_yellows },
    { label: "红牌", h: s.home_reds, a: s.away_reds },
  ];

  return (
    <div style={{ background: "#fff", borderRadius: 12, boxShadow: "0 1px 3px rgba(0,0,0,0.06)", padding: 20 }}>
      {rows.map(row => {
        const total = row.h + row.a;
        const hPct = total > 0 ? (row.h / total) * 100 : 50;
        return (
          <div key={row.label} style={{ display: "flex", alignItems: "center", gap: 12, padding: "8px 0", borderBottom: "1px solid #f1f5f9" }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: "#2563eb", minWidth: 28, textAlign: "right" }}>{row.h}</span>
            <div style={{ flex: 1, height: 6, background: "#f1f5f9", borderRadius: 3, overflow: "hidden", display: "flex" }}>
              <div style={{ height: "100%", width: `${hPct}%`, background: "#3b82f6", borderRadius: 3 }} />
              <div style={{ height: "100%", width: `${100 - hPct}%`, background: "#ef4444", borderRadius: 3 }} />
            </div>
            <span style={{ fontSize: 14, fontWeight: 700, color: "#dc2626", minWidth: 28 }}>{row.a}</span>
            <div style={{ fontSize: 12, color: "#94a3b8", minWidth: 36, textAlign: "center" }}>{row.label}</div>
          </div>
        );
      })}

      {/* Modifier bars */}
      <div style={{ marginTop: 16, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <ModifierBar label="进攻" home={`${state.home_team} (${state.home_attack_modifier.toFixed(1)})`} away={`${state.away_team} (${state.away_attack_modifier.toFixed(1)})`} hVal={state.home_attack_modifier} aVal={state.away_attack_modifier} hColor="#2563eb" aColor="#dc2626" />
        <ModifierBar label="防守" home={`${state.home_team} (${state.home_defense_modifier.toFixed(1)})`} away={`${state.away_team} (${state.away_defense_modifier.toFixed(1)})`} hVal={state.home_defense_modifier} aVal={state.away_defense_modifier} hColor="#60a5fa" aColor="#f87171" />
      </div>
    </div>
  );
}

function ModifierBar({ label, home, away, hVal, aVal, hColor, aColor }: {
  label: string; home: string; away: string; hVal: number; aVal: number; hColor: string; aColor: string;
}) {
  const total = hVal + aVal;
  return (
    <div>
      <div style={{ fontSize: 12, color: "#64748b", fontWeight: 600, marginBottom: 6 }}>{label}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 11, color: hColor, minWidth: 60, textAlign: "right" }}>{home.split(" ").slice(-1)[0]}</span>
        <div style={{ flex: 1, height: 8, background: "#f1f5f9", borderRadius: 4, overflow: "hidden", display: "flex" }}>
          <div style={{ height: "100%", width: `${(hVal / total) * 100}%`, background: hColor, borderRadius: 4 }} />
          <div style={{ height: "100%", width: `${(aVal / total) * 100}%`, background: aColor, borderRadius: 4 }} />
        </div>
        <span style={{ fontSize: 11, color: aColor, minWidth: 60 }}>{away.split(" ").slice(-1)[0]}</span>
      </div>
    </div>
  );
}

// ── Lineup Panel ────────────────────────────────────────────────────────

function LineupPanel({ state }: { state: MatchSnapshot }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
      <TeamLineup title={state.home_team} formation={state.home_formation} players={state.active_players_home} bench={state.bench_players_home} subsUsed={state.home_substitutions_used} color="#2563eb" />
      <TeamLineup title={state.away_team} formation={state.away_formation} players={state.active_players_away} bench={state.bench_players_away} subsUsed={state.away_substitutions_used} color="#dc2626" />
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
      {players.map(p => (
        <div key={p.name} style={{ display: "flex", alignItems: "center", gap: 10, padding: "5px 8px", borderRadius: 6, marginBottom: 2, background: "#f8fafc" }}>
          <span style={{ fontSize: 12, color: "#94a3b8", minWidth: 24, fontWeight: 600 }}>#{p.shirt_number}</span>
          <span style={{ fontSize: 13, flex: 1, color: "#1e293b", fontWeight: 500 }}>{p.name}</span>
          <span style={{ fontSize: 12, color: "#94a3b8", minWidth: 36 }}>{p.position}</span>
          <span style={{ fontSize: 12, fontWeight: 700, color, background: `${color}10`, borderRadius: 6, padding: "1px 8px" }}>{p.rating}</span>
        </div>
      ))}
      <div style={{ fontSize: 12, color: "#64748b", fontWeight: 600, margin: "12px 0 6px" }}>替补</div>
      {bench.map(p => (
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

// ── Tactical Panel ──────────────────────────────────────────────────────

const QUICK_ADJUSTMENTS = [
  { key: "attack_boost", label: "加强进攻", emoji: "⚔️", desc: "进攻倾向+1" },
  { key: "defense_boost", label: "加强防守", emoji: "🛡️", desc: "防守倾向+1" },
  { key: "possession_focus", label: "控制球权", emoji: "🔄", desc: "放慢节奏传控" },
  { key: "counter_attack", label: "防守反击", emoji: "⚡", desc: "稳固防守快速反击" },
  { key: "high_press", label: "高位逼抢", emoji: "🔥", desc: "前场高压" },
  { key: "low_block", label: "低位防守", emoji: "🏗️", desc: "全员退守" },
  { key: "all_out_attack", label: "全力进攻", emoji: "💥", desc: "全员压上" },
  { key: "time_wasting", label: "拖延时间", emoji: "⏳", desc: "控制节奏" },
];

function TacticalPanel({ state, onAdjust, onOpenSub, onOpenFormation, onClose }: {
  state: MatchSnapshot;
  onAdjust: (type: string, from?: string, to?: string, reason?: string) => Promise<void>;
  onOpenSub: () => void;
  onOpenFormation: () => void;
  onClose: () => void;
}) {
  const isTrailing = state.home_score < state.away_score;
  const isLeading = state.home_score > state.away_score;

  const isDisabled = (key: string): boolean => {
    if (key === "all_out_attack") return !isTrailing;
    if (key === "time_wasting") return !isLeading;
    return false;
  };

  return (
    <div style={{
      position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 99,
      background: "#fff", borderTop: "1px solid #e5e7eb",
      borderRadius: "20px 20px 0 0", padding: "20px 20px 28px",
      boxShadow: "0 -8px 32px rgba(0,0,0,0.1)",
      animation: "fadeIn 0.3s ease",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <span style={{ fontSize: 16, fontWeight: 700, color: "#1e293b" }}>⚙ 战术调整</span>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: 18 }}>✕</button>
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <TacticalBtn label="换人" emoji="🔄" desc={`${state.home_substitutions_used}/5`} onClick={onOpenSub} disabled={state.home_substitutions_used >= 5} />
        <TacticalBtn label="变阵" emoji="📐" desc={state.home_formation} onClick={onOpenFormation} />
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {QUICK_ADJUSTMENTS.map(a => (
          <TacticalBtn key={a.key} label={a.label} emoji={a.emoji} desc={a.desc} disabled={isDisabled(a.key)} onClick={() => onAdjust(a.key)} />
        ))}
      </div>
    </div>
  );
}

function TacticalBtn({ label, emoji, desc, onClick, disabled }: {
  label: string; emoji: string; desc: string; onClick: () => void; disabled?: boolean;
}) {
  return (
    <button onClick={onClick} disabled={disabled}
      style={{
        display: "flex", flexDirection: "column", alignItems: "center",
        padding: "10px 14px", borderRadius: 12, gap: 2,
        border: "1.5px solid", minWidth: 72,
        borderColor: disabled ? "#f1f5f9" : "#e5e7eb",
        background: disabled ? "#f8fafc" : "#fff",
        color: disabled ? "#cbd5e1" : "#374151",
        cursor: disabled ? "not-allowed" : "pointer",
        fontSize: 12, transition: "all 0.15s",
        boxShadow: disabled ? "none" : "0 1px 2px rgba(0,0,0,0.04)",
      }}>
      <span style={{ fontSize: 18 }}>{emoji}</span>
      <span style={{ fontWeight: 600 }}>{label}</span>
      <span style={{ fontSize: 10, color: disabled ? "#cbd5e1" : "#94a3b8" }}>{desc}</span>
    </button>
  );
}

// ── Modal ───────────────────────────────────────────────────────────────

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 200,
      display: "flex", alignItems: "center", justifyContent: "center",
      background: "rgba(0,0,0,0.4)",
      animation: "fadeIn 0.2s ease",
    }}>
      <div style={{
        background: "#fff", borderRadius: 16, padding: 24,
        width: "90%", maxWidth: 380,
        boxShadow: "0 16px 48px rgba(0,0,0,0.2)",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "#1e293b" }}>{title}</h3>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: 20 }}>✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

const modalSelect: React.CSSProperties = {
  width: "100%", padding: "10px 14px", fontSize: 14,
  borderRadius: 10, border: "1.5px solid #e5e7eb",
  background: "#f8fafc", color: "#1e293b",
  outline: "none",
};
