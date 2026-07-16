import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { DebateMessage, AGENT_AVATARS, AGENT_NAMES, AGENT_COLORS, AGENT_BUBBLE_BG, AGENT_BUBBLE_BORDER } from "../lib/types";

export function ChatBubble({ msg }: { msg: DebateMessage }) {
  const isElimination = msg.type === "elimination";
  const color = AGENT_COLORS[msg.speaker_key] || "#475569";
  const avatar = AGENT_AVATARS[msg.speaker_key] || "👤";
  const name = AGENT_NAMES[msg.speaker_key] || msg.speaker;
  const bubbleBg = isElimination ? "#fffbeb" : (AGENT_BUBBLE_BG[msg.speaker_key] || "#fff");
  const bubbleBorder = isElimination ? "#fde68a" : (AGENT_BUBBLE_BORDER[msg.speaker_key] || "#e2e8f0");
  const isStreaming = !!msg.streaming;

  return (
    <div style={{ display: "flex", gap: 10, marginBottom: 16, alignItems: "flex-start" }}>
      <div style={{ width: 40, height: 40, borderRadius: 10, background: color, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, flexShrink: 0, color: "#fff" }}>{avatar}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color }}>{name}</span>
          {isStreaming && <span style={{ fontSize: 11, color: "#94a3b8" }}>{isElimination ? "正在综合各专家意见..." : "正在输入..."}</span>}
          {isElimination && <span style={{ padding: "1px 8px", background: "#fef2f2", color: "#dc2626", borderRadius: 10, fontSize: 11, fontWeight: 600, border: "1px solid #fecaca" }}>淘汰决定</span>}
        </div>
        <div style={{ padding: "12px 16px", background: bubbleBg, borderRadius: "4px 12px 12px 12px", border: "1px solid " + bubbleBorder, fontSize: 14, lineHeight: 1.7, color: "#334155", wordBreak: "break-word" }}>
          {msg.content
            ? <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
                p: ({ node, ...props }) => <p style={{ margin: "0 0 8px" }} {...props} />,
                ul: ({ node, ...props }) => <ul style={{ margin: "4px 0 8px", paddingLeft: 20 }} {...props} />,
                ol: ({ node, ...props }) => <ol style={{ margin: "4px 0 8px", paddingLeft: 20 }} {...props} />,
                strong: ({ node, ...props }) => <strong style={{ color: "#0f172a", fontWeight: 700 }} {...props} />,
                h1: ({ node, ...props }) => <h4 style={{ margin: "8px 0 4px", fontSize: 15 }} {...props} />,
                h2: ({ node, ...props }) => <h4 style={{ margin: "8px 0 4px", fontSize: 15 }} {...props} />,
                h3: ({ node, ...props }) => <h4 style={{ margin: "8px 0 4px", fontSize: 15 }} {...props} />,
                code: ({ node, ...props }) => <code style={{ background: "#e2e8f0", padding: "1px 4px", borderRadius: 3, fontSize: 13 }} {...props} />,
              }}>
              {msg.content}
            </ReactMarkdown>
            : (isStreaming ? <span style={{ color: "#94a3b8", fontSize: 13 }}>思考中...</span> : <span style={{ color: "#94a3b8", fontSize: 13 }}>（空）</span>)
          }
          {isStreaming && msg.content && <span style={{ display: "inline-block", width: 7, height: 15, background: color, marginLeft: 2, verticalAlign: "text-bottom", animation: "blink-cursor 1s step-end infinite", borderRadius: 1 }} />}
        </div>
      </div>
    </div>
  );
}