package models

import "time"

type ScoutRequest struct {
	Query string `json:"query" binding:"required"`
}

type ScoutResponse struct {
	Query          string `json:"query"`
	Report         string `json:"report"`
	RetrievedCount int    `json:"retrieved_count"`
}

type ErrorResponse struct {
	Error string `json:"error"`
}

type LoginRequest struct {
	Username string `json:"username" binding:"required"`
	Password string `json:"password" binding:"required"`
}

type LoginResponse struct {
	Token    string `json:"token"`
	Username string `json:"username"`
}

type RegisterRequest struct {
	Username string `json:"username" binding:"required"`
	Password string `json:"password" binding:"required"`
}

type User struct {
	ID           int       `json:"id"`
	Username     string    `json:"username"`
	PasswordHash string    `json:"-"`
	CreatedAt    time.Time `json:"created_at"`
}

type QueryHistory struct {
	ID               int       `json:"id"`
	UserID           int       `json:"user_id"`
	Query            string    `json:"query"`
	Report           string    `json:"report"`
	RetrievedCount   int       `json:"retrieved_count"`
	CreatedAt        time.Time `json:"created_at"`
	CandidatesJSON   string    `json:"candidates_json,omitempty"`
	DebateJSON       string    `json:"debate_json,omitempty"`
	FinalCandidateJSON string  `json:"final_candidate_json,omitempty"`
	EliminatedJSON   string    `json:"eliminated_json,omitempty"`
}

type PreferenceRequest struct {
	Preferences map[string]string `json:"preferences" binding:"required"`
}

type PreferenceResponse struct {
	Preferences map[string]string `json:"preferences"`
}

type ClarifyRequest struct {
	Query          string            `json:"query" binding:"required"`
	SessionID      string            `json:"session_id"`
	Answers        map[string]string `json:"answers"`
	CandidateCount int               `json:"candidate_count"`
}

type ClarifyResponse struct {
	SessionID        string              `json:"session_id"`
	Questions        []map[string]any    `json:"questions"`
	ClarificationDone bool               `json:"clarification_done"`
	Answers          map[string]string   `json:"answers,omitempty"`
}

type AnalyzeRequest struct {
	SessionID         string `json:"session_id" binding:"required"`
	PreferencesMemory string `json:"preferences_memory,omitempty"`
}
