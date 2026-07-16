package config

import (
	"crypto/rand"
	"encoding/hex"
	"log"
)

const (
	AgentAPIBaseURL     = "http://localhost:8000"
	ScoutEndpoint       = "/api/scout"
	ScoutStreamEndpoint = "/api/scout/stream"
	ServerPort          = ":8080"

	DBUser     = "root"
	DBPassword = "123456"
	DBHost     = "127.0.0.1"
	DBPort     = "3306"
	DBName     = "scout_agent"
)

// JWTSecret 在每次进程启动时随机生成（不持久化）。
// 这意味着：后端服务一重启，之前签发的所有 JWT 立即失效，
// 客户端必须重新登录，避免"重启服务后旧 token 仍可用"。
var JWTSecret = func() string {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		log.Fatalf("failed to generate JWT secret: %v", err)
	}
	s := hex.EncodeToString(b)
	log.Printf("[config] JWT secret randomized for this process (prefix=%s)", s[:8])
	return s
}()
