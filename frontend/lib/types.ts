export type Step = "input" | "clarify" | "loading" | "candidates" | "debate" | "result";

export interface Candidate {
  name: string;
  position: string;
  team: string;
  age: number;
  reasoning: string;
  key_strengths: string[];
}

export interface Question {
  id: string;
  question: string;
  options: { label: string; value: string }[];
}

export interface DebateMessage {
  type: string;
  speaker: string;
  speaker_key: string;
  content: string;
  round: number;
  eliminated?: string[];
  active_count?: number;
  msg_id?: string;
  streaming?: boolean;
}

export interface HistoryItem {
  id: number;
  query: string;
  report: string;
  retrieved_count: number;
  created_at: string;
  candidates_json?: string;
  debate_json?: string;
  final_candidate_json?: string;
  eliminated_json?: string;
}

export const API_BASE = "/api";

export const AGENT_AVATARS: Record<string, string> = {
  tactical_analyst: "📋", financial_advisor: "💰", injury_risk_analyst: "🏥",
  potential_evaluator: "📈", chief_scout: "🎖️", data_analyst: "📊", orchestrator: "🎯",
};
export const AGENT_NAMES: Record<string, string> = {
  data_analyst: "数据分析师", tactical_analyst: "战术分析师", financial_advisor: "财务顾问",
  injury_risk_analyst: "伤病风险分析师", potential_evaluator: "潜力评估分析师", chief_scout: "总球探",
};
export const AGENT_COLORS: Record<string, string> = {
  data_analyst: "#2563eb", tactical_analyst: "#16a34a", financial_advisor: "#ea580c",
  injury_risk_analyst: "#dc2626", potential_evaluator: "#9333ea", chief_scout: "#0f172a",
};
export const AGENT_BUBBLE_BG: Record<string, string> = {
  tactical_analyst: "#f0fdf4", financial_advisor: "#fff7ed", injury_risk_analyst: "#fef2f2",
  potential_evaluator: "#faf5ff", chief_scout: "#fffbeb", data_analyst: "#eff6ff",
};
export const AGENT_BUBBLE_BORDER: Record<string, string> = {
  tactical_analyst: "#bbf7d0", financial_advisor: "#fed7aa", injury_risk_analyst: "#fecaca",
  potential_evaluator: "#e9d5ff", chief_scout: "#fde68a", data_analyst: "#bfdbfe",
};

export const st = {
  card: { background: "#fff", borderRadius: 12, boxShadow: "0 1px 3px rgba(0,0,0,0.08)", padding: 24 },
  input: { width: "100%", padding: "12px 16px", fontSize: 15, borderRadius: 8, border: "1.5px solid #e2e8f0", outline: "none", boxSizing: "border-box" as const, background: "#f8fafc" },
  btn: { padding: "10px 24px", fontSize: 14, fontWeight: 600, borderRadius: 8, border: "none", cursor: "pointer" },
  pb: { background: "linear-gradient(135deg, #2563eb, #1d4ed8)", color: "#fff" },
  sb: { background: "#f1f5f9", color: "#475569", border: "1.5px solid #e2e8f0" },
};