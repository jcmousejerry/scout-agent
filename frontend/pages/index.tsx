import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/router";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { API_BASE, st, Step, Candidate, Question, DebateMessage } from "../lib/types";
import { clearAuth } from "../lib/auth";
import { ProgressBar } from "../components/ProgressBar";
import { RoundDivider } from "../components/RoundDivider";
import { ChatBubble } from "../components/ChatBubble";

export default function Home() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [username, setUsername] = useState("");
  const [query, setQuery] = useState("");
  const [candidateCount, setCandidateCount] = useState(3);
  const [step, setStep] = useState<Step>("input");
  const [sessionId, setSessionId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [currentQIdx, setCurrentQIdx] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [answeredQuestions, setAnsweredQuestions] = useState<Record<string, string>>({});
  const [progress, setProgress] = useState<{ step: string; message: string; progress: number } | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [debateMessages, setDebateMessages] = useState<DebateMessage[]>([]);
  const [eliminated, setEliminated] = useState<string[]>([]);
  const [report, setReport] = useState("");
  const [finalCandidate, setFinalCandidate] = useState<Candidate | null>(null);
  const [currentRound, setCurrentRound] = useState(0);
  const [authChecked, setAuthChecked] = useState(false);
  const [debateExpanded, setDebateExpanded] = useState(true);
  const [runningSessions, setRunningSessions] = useState<any[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const debateEndRef = useRef<HTMLDivElement>(null);
  const submittingRef = useRef(false);
  const gotTerminalRef = useRef(false);

  useEffect(() => {
    const savedToken = localStorage.getItem("token");
    const savedUsername = localStorage.getItem("username");
    if (!savedToken || !savedUsername) { setAuthChecked(true); return; }
    fetch(API_BASE + "/history", { headers: { Authorization: "Bearer " + savedToken } })
      .then(r => {
        if (r.status === 401) { localStorage.removeItem("token"); localStorage.removeItem("username"); setAuthChecked(true); return null; }
        if (r.ok) { setToken(savedToken); setUsername(savedUsername); return r.json(); }
        return null;
      })
      .catch(() => {})
      .finally(() => setAuthChecked(true));
  }, []);

  useEffect(() => { debateEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [debateMessages]);

  useEffect(() => {
    if (step !== "input" && step !== "result") {
      const handler = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ""; };
      window.addEventListener("beforeunload", handler);
      return () => window.removeEventListener("beforeunload", handler);
    }
  }, [step]);

  useEffect(() => {
    if (!token) return;
    const poll = async () => {
      try {
        const res = await fetch(API_BASE + "/sessions/active", { headers: { Authorization: "Bearer " + token } });
        if (res.ok) { const d = await res.json(); setRunningSessions(d.sessions || []); }
      } catch {}
    };
    poll();
    const interval = setInterval(poll, 3000);
    return () => clearInterval(interval);
  }, [token]);

  const doFetch = async (url: string, body: any) => {
    const res = await fetch(API_BASE + url, { method: "POST", headers: { "Content-Type": "application/json", Authorization: "Bearer " + token }, body: JSON.stringify(body) });
    if (res.status === 401) { clearAuth(); setToken(""); setUsername(""); return null; }
    return res;
  };

  const handleLogout = () => { clearAuth(); setToken(""); setUsername(""); router.push("/login"); };

  const handleStartClarify = async () => {
    if (!query.trim() || submittingRef.current) return;
    submittingRef.current = true; setSubmitting(true);
    setStep("clarify"); setProgress({ step: "rag", message: "正在分析需求...", progress: 10 });
    try {
      const res = await doFetch("/scout/clarify", { query, candidate_count: candidateCount });
      if (!res) return;
      const data = await res.json();
      if (!res.ok) { setReport("Error: " + (data.error || "unknown")); setStep("result"); return; }
      setSessionId(data.session_id);
      if (data.clarification_done) { startAnalysis(data.session_id); }
      else { setQuestions(data.questions || []); setCurrentQIdx(0); setProgress(null); }
    } catch { setReport("连接失败"); setStep("result"); }
    finally { submittingRef.current = false; setSubmitting(false); }
  };

  const handleAnswer = async (questionId: string, value: string) => {
    if (submittingRef.current) return;
    const newAnswers = { ...answers, [questionId]: value };
    setAnswers(newAnswers);
    setAnsweredQuestions(prev => ({ ...prev, [questionId]: value }));
    if (currentQIdx + 1 < questions.length) { setCurrentQIdx(currentQIdx + 1); return; }
    submittingRef.current = true; setSubmitting(true);
    setProgress({ step: "rag", message: "正在分析您的需求...", progress: 15 });
    try {
      const res = await doFetch("/scout/clarify", { query, session_id: sessionId, answers: newAnswers, candidate_count: candidateCount });
      if (!res) return;
      const data = await res.json();
      if (!res.ok) { setReport("Error: " + (data.error || "unknown")); setStep("result"); return; }
      if (data.clarification_done) { setProgress(null); startAnalysis(data.session_id); }
      else { setQuestions(data.questions || []); setCurrentQIdx(0); setProgress(null); }
    } catch { setReport("连接失败"); setStep("result"); }
    finally { submittingRef.current = false; setSubmitting(false); }
  };

  const startAnalysis = async (sid: string) => {
    setStep("loading"); setDebateMessages([]); setEliminated([]);
    setProgress({ step: "rag", message: "开始检索足球通识知识库...", progress: 10 });
    gotTerminalRef.current = false;
    abortRef.current = new AbortController();
    try {
      const res = await fetch(API_BASE + "/scout/analyze", { method: "POST", headers: { "Content-Type": "application/json", Authorization: "Bearer " + token }, body: JSON.stringify({ session_id: sid }), signal: abortRef.current.signal });
      if (res.status === 401) { clearAuth(); setToken(""); setUsername(""); return; }
      if (!res.ok) { setReport("Error: " + res.status); setStep("result"); return; }
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
          const lines = part.split("\n");
          let eventType = "message", dataStr = "";
          for (const line of lines) {
            if (line.startsWith("event: ")) eventType = line.slice(7);
            else if (line.startsWith("data: ")) dataStr = line.slice(6);
          }
          if (!dataStr) continue;
          handleSSEEvent(eventType, dataStr);
        }
      }
      if (!gotTerminalRef.current) { setReport("分析失败：未收到有效响应，请检查后端服务是否正常运行。"); setStep("result"); }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") return;
      if (!gotTerminalRef.current) { setReport("连接中断"); setStep("result"); }
    } finally { setProgress(null); abortRef.current = null; }
  };

  const handleSSEEvent = useCallback((eventType: string, dataStr: string) => {
    const data = JSON.parse(dataStr);
    switch (eventType) {
      case "progress":
        setProgress({ step: data.step, message: data.message, progress: data.progress });
        if (data.step === "candidates") setStep("candidates");
        break;
      case "candidate":
        setCandidates(data.candidates_so_far || []);
        setStep("candidates");
        break;
      case "candidates":
        setCandidates(data.candidates || []);
        setStep("candidates");
        break;
      case "round_start":
        setCurrentRound(data.round);
        setStep("debate");
        break;
      case "debate_start":
        setDebateMessages(prev => [...prev, {
          type: data.type, speaker: data.speaker, speaker_key: data.speaker_key,
          content: "", round: data.round, msg_id: data.msg_id, streaming: true,
        }]);
        setStep("debate");
        break;
      case "debate_chunk":
        setDebateMessages(prev => prev.map(m =>
          m.msg_id === data.msg_id ? { ...m, content: m.content + data.delta } : m
        ));
        setStep("debate");
        break;
      case "debate_done":
        setDebateMessages(prev => prev.map(m =>
          m.msg_id === data.msg_id
            ? { ...m, content: data.content || m.content, streaming: false, type: data.type || m.type }
            : m
        ));
        if (data.type === "elimination" && data.eliminated) setEliminated(data.eliminated);
        setStep("debate");
        break;
      case "result":
        gotTerminalRef.current = true;
        setReport(data.report || ""); setFinalCandidate(data.final_candidate || null);
        setEliminated(data.eliminated || []);
        setDebateMessages(prev => {
          const backendMsgs: DebateMessage[] = data.debate_messages || [];
          if (prev.length && prev.length === backendMsgs.length) return prev;
          return backendMsgs;
        });
        setStep("result"); setProgress(null);
        break;
      case "error": gotTerminalRef.current = true; setReport("Error: " + (data.message || "unknown")); setStep("result"); break;
    }
  }, []);

  const handleCancel = () => { abortRef.current?.abort(); };
  const handleNewSearch = () => {
    setStep("input"); setSessionId(""); setQuestions([]); setCurrentQIdx(0); setAnswers({}); setAnsweredQuestions({});
    setProgress(null); setCandidates([]); setDebateMessages([]); setEliminated([]); setReport(""); setFinalCandidate(null);
    setQuery(""); setSubmitting(false); submittingRef.current = false; setCurrentRound(0);
    setCandidateCount(3);
  };
  const handleNewQuery = () => {
    abortRef.current?.abort();
    setStep("input"); setProgress(null); setCandidates([]); setDebateMessages([]);
    setEliminated([]); setReport(""); setFinalCandidate(null); setQuery("");
    setSubmitting(false); submittingRef.current = false; setSessionId("");
  };

  if (!authChecked) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)", color: "#fff", fontSize: 16 }}>
        <div style={{ textAlign: "center" }}><div style={{ fontSize: 32, marginBottom: 12 }}>⚽</div><div>正在验证登录状态...</div></div>
      </div>
    );
  }
  if (!token) {
    router.push("/login");
    return null;
  }

  return (
    <div style={{ minHeight: "100vh", background: "#f8fafc", fontFamily: "system-ui, sans-serif" }}>
      <header style={{ background: "#fff", borderBottom: "1px solid #e2e8f0", position: "sticky", top: 0, zIndex: 10 }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "12px 24px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 24 }}>⚽</span>
            <span style={{ fontSize: 18, fontWeight: 700, color: "#0f172a" }}>Scout Agent</span>
            {runningSessions.length > 0 && (
              <span style={{ fontSize: 12, color: "#92400e", background: "#fffbeb", padding: "2px 10px", borderRadius: 12, border: "1px solid #fde68a" }}>
                📌 {runningSessions.length} 活跃
              </span>
            )}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {step !== "input" && step !== "result" && (
              <button onClick={handleNewQuery} style={{ ...st.btn, ...st.pb, fontSize: 13 }}>🔍 新查询</button>
            )}
            <button onClick={() => router.push("/history")} style={{ ...st.btn, ...st.sb, fontSize: 13 }}>📋 历史</button>
            <span style={{ fontSize: 14, color: "#64748b" }}>{username}</span>
            <button onClick={handleLogout} style={{ ...st.btn, ...st.sb, fontSize: 13 }}>退出</button>
          </div>
        </div>
      </header>
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "24px" }}>
        {/* 功能模块选择 */}
        {step === "input" && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
            <div
              onClick={() => {}}
              style={{
                ...st.card, cursor: "pointer", padding: "24px", textAlign: "center",
                border: "2.5px solid #2563eb", background: "#eff6ff",
                transition: "all 0.2s",
              }}
              onMouseOver={e => { e.currentTarget.style.borderColor = "#1d4ed8"; e.currentTarget.style.background = "#dbeafe"; }}
              onMouseOut={e => { e.currentTarget.style.borderColor = "#2563eb"; e.currentTarget.style.background = "#eff6ff"; }}
            >
              <div style={{ fontSize: 40, marginBottom: 8 }}>🔍</div>
              <h3 style={{ margin: "0 0 4px", fontSize: 16, fontWeight: 700, color: "#1e40af" }}>智能球探球员推荐</h3>
              <p style={{ margin: 0, fontSize: 13, color: "#64748b" }}>AI多专家辩论，推荐最佳球员人选</p>
              <div style={{ marginTop: 12, fontSize: 12, color: "#2563eb", fontWeight: 600 }}>✓ 当前功能</div>
            </div>
            <div
              onClick={() => router.push("/match-sim")}
              style={{
                ...st.card, cursor: "pointer", padding: "24px", textAlign: "center",
                border: "2.5px solid #16a34a", background: "#f0fdf4",
                transition: "all 0.2s",
              }}
              onMouseOver={e => { e.currentTarget.style.borderColor = "#15803d"; e.currentTarget.style.background = "#dcfce7"; }}
              onMouseOut={e => { e.currentTarget.style.borderColor = "#16a34a"; e.currentTarget.style.background = "#f0fdf4"; }}
            >
              <div style={{ fontSize: 40, marginBottom: 8 }}>🏟️</div>
              <h3 style={{ margin: "0 0 4px", fontSize: 16, fontWeight: 700, color: "#166534" }}>比赛策略战术模拟</h3>
              <p style={{ margin: 0, fontSize: 13, color: "#64748b" }}>AI实时模拟比赛，可战术调整</p>
              <div style={{ marginTop: 12, fontSize: 12, color: "#16a34a", fontWeight: 600 }}>点击进入 →</div>
            </div>
          </div>
        )}

        {/* 活跃会话列表 - 从后端 sessions 表实时拉取 */}
        {runningSessions.length > 0 && step === "input" && (
          <div style={{ ...st.card, marginBottom: 20, border: "1.5px solid #f59e0b", background: "#fffbeb" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: "#92400e" }}>📌 活跃的分析会话（{runningSessions.length}个）</h3>
            </div>
            {runningSessions.map(s => {
              let statusText = "⏳ 等待中...";
              if (s.candidates_json) { const c = s.candidates_json; statusText = `⏳ 已推荐 ${Array.isArray(c) ? c.length : 0} 名候选人`; }
              return (
                <div key={s.session_id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 12px", background: "#fff", borderRadius: 8, marginBottom: 6, border: "1px solid #fde68a" }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 14, fontWeight: 500, color: "#0f172a", marginBottom: 2 }}>{s.original_query?.slice(0, 50)}{s.original_query?.length > 50 ? "..." : ""}</div>
                    <div style={{ fontSize: 12, color: "#a16207" }}>{statusText}</div>
                  </div>
                  <button onClick={() => router.push("/session/" + s.session_id)}
                    style={{ ...st.btn, ...st.pb, fontSize: 12, padding: "6px 14px", whiteSpace: "nowrap", marginLeft: 12 }}>查看进度</button>
                </div>
              );
            })}
          </div>
        )}
        {/* 输入区域 */}
        {step === "input" && (
          <div style={{ ...st.card, textAlign: "center", padding: runningSessions.length > 0 ? "40px 40px" : "60px 40px" }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>⚽</div>
            <h2 style={{ margin: "0 0 8px", fontSize: 22, fontWeight: 700, color: "#0f172a" }}>输入球探需求</h2>
            <p style={{ margin: "0 0 24px", fontSize: 14, color: "#64748b" }}>描述您要寻找的球员类型，系统将通过多专家辩论为您推荐最佳人选</p>
            <div style={{ display: "flex", gap: 8, maxWidth: 600, margin: "0 auto", marginBottom: 16 }}>
              <input value={query} onChange={e => setQuery(e.target.value)} placeholder="例如：寻找一名速度快、进球能力强的年轻前锋" style={{ ...st.input, flex: 1 }} onKeyDown={e => e.key === "Enter" && handleStartClarify()} />
              <button onClick={handleStartClarify} disabled={!query.trim() || submitting} style={{ ...st.btn, ...st.pb, opacity: (!query.trim() || submitting) ? 0.6 : 1 }}>开始分析</button>
            </div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 12, fontSize: 14, color: "#475569" }}>
              <span>候选人数：</span>
              {[2, 3, 4, 5].map(n => (
                <button key={n} onClick={() => setCandidateCount(n)} disabled={submitting}
                  style={{ ...st.btn, fontSize: 13, padding: "6px 14px", minWidth: 40,
                    background: candidateCount === n ? "#2563eb" : "#f1f5f9",
                    color: candidateCount === n ? "#fff" : "#475569",
                    border: candidateCount === n ? "none" : "1.5px solid #e2e8f0",
                    opacity: submitting ? 0.6 : 1, cursor: submitting ? "not-allowed" : "pointer",
                  }}>
                  {n}
                </button>
              ))}
              <span style={{ fontSize: 12, color: "#94a3b8" }}>人（{candidateCount - 1}轮辩论）</span>
            </div>
          </div>
        )}
        {step === "clarify" && (
          <div>
            {progress && <ProgressBar step={progress.step} message={progress.message} progress={progress.progress} />}
            {Object.entries(answeredQuestions).length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 13, color: "#64748b", marginBottom: 8 }}>已明确的偏好：</div>
                {Object.entries(answeredQuestions).map(([qId, val]) => {
                  const q = questions.find(qq => qq.id === qId) ?? { question: qId, options: [] };
                  const opt = q.options.find(o => o.value === val);
                  return (
                    <div key={qId} style={{ padding: "8px 14px", background: "#f0f9ff", borderRadius: 8, marginBottom: 4, fontSize: 14, border: "1px solid #bae6fd" }}>
                      <span style={{ color: "#0369a1" }}>{q.question}：</span>
                      <span style={{ color: "#2563eb", fontWeight: 600 }}>{opt?.label || val}</span>
                    </div>
                  );
                })}
              </div>
            )}
            {currentQIdx < questions.length && (
              <div style={{ ...st.card }}>
                <div style={{ fontSize: 13, color: "#94a3b8", marginBottom: 8 }}>问题 {currentQIdx + 1} / {questions.length}</div>
                <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 20, color: "#0f172a" }}>{questions[currentQIdx]?.question}</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {questions[currentQIdx]?.options.map((opt) => (
                    <button key={opt.value} onClick={() => handleAnswer(questions[currentQIdx].id, opt.label)} disabled={submitting}
                      style={{ padding: "14px 20px", fontSize: 15, borderRadius: 8, border: "2px solid #e2e8f0", background: "#fff", cursor: submitting ? "not-allowed" : "pointer", textAlign: "left", opacity: submitting ? 0.6 : 1 }}
                      onMouseOver={e => { if (!submitting) { e.currentTarget.style.borderColor = "#2563eb"; e.currentTarget.style.background = "#eff6ff"; } }}
                      onMouseOut={e => { e.currentTarget.style.borderColor = "#e2e8f0"; e.currentTarget.style.background = "#fff"; }}>
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        {step === "loading" && (
          <div style={{ marginTop: 20 }}>
            {progress ? <ProgressBar step={progress.step} message={progress.message} progress={progress.progress} /> : <ProgressBar step="rag" message="正在启动分析..." progress={5} />}
            <div style={{ textAlign: "center", marginTop: 12 }}>
              <button onClick={handleCancel} style={{ ...st.btn, ...st.sb, fontSize: 13 }}>取消</button>
            </div>
          </div>
        )}
        {step === "candidates" && (
          <div>
            {progress && <ProgressBar step={progress.step} message={progress.message} progress={progress.progress} />}
            <h3 style={{ margin: "0 0 4px", fontSize: 16, color: "#0f172a" }}>🎯 推荐候选球员</h3>
            <div style={{ fontSize: 13, color: "#64748b", marginBottom: 16 }}>
              {candidates.length > 0 && candidates.length < candidateCount
                ? `已筛选出 ${candidates.length} / ${candidateCount} 名候选球员，正在联网搜索后续候选人...`
                : candidates.length === candidateCount
                  ? `${candidateCount} 名候选球员已确定，即将进入多专家群聊辩论阶段...`
                  : "正在联网搜索并生成候选球员，请稍候..."}
            </div>
            {candidates.length > 0 ? (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
                {candidates.map((c, i) => (
                  <div key={i} style={{ padding: 16, borderRadius: 10, border: "1.5px solid " + (eliminated.includes(c.name) ? "#fecaca" : "#e2e8f0"), background: eliminated.includes(c.name) ? "#fef2f2" : "#fff", opacity: eliminated.includes(c.name) ? 0.5 : 1, animation: i === candidates.length - 1 ? "fadeIn 0.4s ease" : undefined }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                      <div style={{ fontSize: 16, fontWeight: 700, color: "#0f172a" }}>{c.name}</div>
                      <span style={{ fontSize: 11, color: "#94a3b8" }}>#{i + 1}</span>
                    </div>
                    <div style={{ fontSize: 13, color: "#64748b", marginBottom: 8 }}>{c.position} | {c.team} | {c.age}岁</div>
                    {eliminated.includes(c.name) && <div style={{ color: "#dc2626", fontSize: 13, fontWeight: 600, marginBottom: 8 }}>❌ 已被淘汰</div>}
                    {c.reasoning && <div style={{ fontSize: 13, color: "#475569", marginBottom: 8, lineHeight: 1.6 }}>{c.reasoning}</div>}
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                      {c.key_strengths?.map((s, j) => (
                        <span key={j} style={{ padding: "2px 8px", background: "#f0fdf4", borderRadius: 10, fontSize: 12, color: "#16a34a", border: "1px solid #bbf7d0" }}>{s}</span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
                {Array.from({ length: candidateCount }).map((_, i) => (
                  <div key={i} style={{ padding: 16, borderRadius: 10, border: "1.5px dashed #cbd5e1", background: "#f8fafc", display: "flex", alignItems: "center", justifyContent: "center", minHeight: 120 }}>
                    <div style={{ textAlign: "center", color: "#94a3b8", fontSize: 13 }}>
                      <div style={{ fontSize: 22, marginBottom: 6, animation: "blink 1.4s ease-in-out infinite" }}>🔍</div>
                      正在搜索第 {i + 1} 名候选人...
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        {step === "debate" && (
          <div>
            {progress && <ProgressBar step={progress.step} message={progress.message} progress={progress.progress} />}
            {candidates.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                  <h3 style={{ margin: 0, fontSize: 16, color: "#0f172a" }}>🎯 候选球员 ({candidates.length}人)</h3>
                  <div style={{ display: "flex", gap: 12, fontSize: 13 }}>
                    <span style={{ color: "#16a34a", fontWeight: 600 }}>剩余: {candidates.filter(c => !eliminated.includes(c.name)).length}</span>
                    <span style={{ color: "#dc2626", fontWeight: 600 }}>已淘汰: {eliminated.length}</span>
                  </div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 10 }}>
                  {candidates.map((c, i) => {
                    const isOut = eliminated.includes(c.name);
                    return (
                      <div key={i} style={{ padding: 12, borderRadius: 8, border: "1.5px solid " + (isOut ? "#fecaca" : "#e2e8f0"), background: isOut ? "#fef2f2" : "#fff", opacity: isOut ? 0.5 : 1 }}>
                        <div style={{ fontSize: 14, fontWeight: 700, color: "#0f172a", display: "flex", alignItems: "center", gap: 6 }}>
                          {isOut ? "❌" : "✅"} {c.name}
                        </div>
                        <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>{c.position} | {c.team} | {c.age}岁</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
            <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", padding: 20, maxHeight: 600, overflowY: "auto" }}>
              {debateMessages.length === 0 && (
                <div style={{ textAlign: "center", padding: "40px 0", color: "#94a3b8", fontSize: 14 }}>
                  <div style={{ fontSize: 32, marginBottom: 8 }}>🗣️</div>
                  即将开始多专家群聊辩论...
                </div>
              )}
              {(() => {
                const elements: React.JSX.Element[] = [];
                let lastRound = 0;
                debateMessages.forEach((msg, i) => {
                  if (msg.round !== lastRound) { lastRound = msg.round; elements.push(<RoundDivider key={"r" + msg.round} round={msg.round} />); }
                  elements.push(<ChatBubble key={i} msg={msg} />);
                });
                return elements;
              })()}
              <div ref={debateEndRef} />
            </div>
            {progress?.step === "report" && <div style={{ textAlign: "center", marginTop: 8, fontSize: 14, color: "#64748b" }}>⚙️ 正在生成最终报告...</div>}
          </div>
        )}
        {step === "result" && (
          <div>
            <button onClick={handleNewSearch} style={{ ...st.btn, ...st.pb, marginBottom: 16, fontSize: 13 }}>🔍 新的查询</button>
            {finalCandidate && (
              <div style={{ marginBottom: 20, padding: 20, background: "#f0fdf4", borderRadius: 12, border: "2px solid #86efac" }}>
                <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 8, color: "#16a34a" }}>🏆 最终推荐球员</div>
                <div style={{ fontSize: 16, fontWeight: 600, color: "#0f172a" }}>{finalCandidate.name}</div>
                <div style={{ fontSize: 14, color: "#475569" }}>{finalCandidate.position} | {finalCandidate.team} | {finalCandidate.age}岁</div>
              </div>
            )}
            {report && (
              <div style={{ background: "#fff", padding: 24, borderRadius: 12, border: "1px solid #e2e8f0", lineHeight: 1.7, overflowX: "auto" }}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
              </div>
            )}
            {eliminated.length > 0 && (
              <div style={{ marginTop: 20, padding: 16, background: "#fef2f2", borderRadius: 10, border: "1px solid #fecaca" }}>
                <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8, color: "#dc2626" }}>淘汰球员</div>
                {eliminated.map((name, i) => <div key={i} style={{ fontSize: 14, color: "#64748b", padding: "2px 0" }}>❌ {name}</div>)}
              </div>
            )}
            {debateMessages.length > 0 && (
              <div style={{ marginTop: 20, background: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", overflow: "hidden" }}>
                <div onClick={() => setDebateExpanded(!debateExpanded)} style={{ padding: "14px 20px", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "space-between", userSelect: "none", background: "#f8fafc", borderBottom: debateExpanded ? "1px solid #e2e8f0" : "none" }}>
                  <span style={{ fontSize: 14, fontWeight: 600, color: "#0f172a" }}>🗣️ 完整辩论过程（{debateMessages.length} 条消息）</span>
                  <span style={{ fontSize: 12, color: "#64748b", transform: debateExpanded ? "rotate(180deg)" : "none", transition: "transform 0.2s" }}>▼</span>
                </div>
                {debateExpanded && (
                  <div style={{ padding: 20, maxHeight: 500, overflowY: "auto" }}>
                    {(() => {
                      const elements: React.JSX.Element[] = [];
                      let lastRound = 0;
                      debateMessages.forEach((msg, i) => {
                        if (msg.round !== lastRound) { lastRound = msg.round; elements.push(<RoundDivider key={"r" + msg.round} round={msg.round} />); }
                        elements.push(<ChatBubble key={i} msg={msg} />);
                      });
                      return elements;
                    })()}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}