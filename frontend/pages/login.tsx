import { useState } from "react";
import { useRouter } from "next/router";
import { API_BASE, st } from "../lib/types";
import { setAuth, getStoredAuth } from "../lib/auth";
import { useEffect } from "react";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (getStoredAuth()) router.replace("/");
  }, []);

  const handleSubmit = async () => {
    setError(""); setLoading(true);
    try {
      const res = await fetch(API_BASE + "/" + mode, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error || "请求失败"); return; }
      setAuth(data.token, data.username);
      router.replace("/");
    } catch { setError("无法连接到服务器"); }
    finally { setLoading(false); }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)" }}>
      <div style={{ ...st.card, width: 400, padding: 40 }}>
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{ fontSize: 40, marginBottom: 8 }}>⚽</div>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: "#0f172a" }}>Scout Agent</h1>
          <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>智能球探分析系统</p>
        </div>
        <input value={username} onChange={e => setUsername(e.target.value)} placeholder="用户名" style={{ ...st.input, marginBottom: 12 }} onKeyDown={e => e.key === "Enter" && !loading && handleSubmit()} />
        <input value={password} onChange={e => setPassword(e.target.value)} placeholder="密码" type="password" style={{ ...st.input, marginBottom: 12 }} onKeyDown={e => e.key === "Enter" && !loading && handleSubmit()} />
        {error && <div style={{ color: "#dc2626", fontSize: 13, marginBottom: 12, padding: "8px 12px", background: "#fef2f2", borderRadius: 6 }}>{error}</div>}
        <button onClick={handleSubmit} disabled={loading} style={{ ...st.btn, ...st.pb, width: "100%", marginBottom: 12, opacity: loading ? 0.7 : 1 }}>{loading ? "处理中..." : mode === "login" ? "登录" : "注册"}</button>
        <div style={{ textAlign: "center", fontSize: 13, color: "#64748b", cursor: "pointer" }} onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>{mode === "login" ? "没有账号？注册" : "已有账号？登录"}</div>
      </div>
    </div>
  );
}