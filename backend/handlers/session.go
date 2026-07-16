package handlers

import (
	"encoding/json"
	"net/http"

	"github.com/gin-gonic/gin"
	"scout-backend/database"
)

type SessionStatusResponse struct {
	SessionID          string          `json:"session_id"`
	OriginalQuery      string          `json:"original_query"`
	CandidatesJSON     json.RawMessage `json:"candidates_json,omitempty"`
	DebateJSON         json.RawMessage `json:"debate_json,omitempty"`
	FinalCandidateJSON json.RawMessage `json:"final_candidate_json,omitempty"`
	FinalReport        string          `json:"final_report,omitempty"`
	EliminatedJSON     json.RawMessage `json:"eliminated_json,omitempty"`
	Status             string          `json:"status"`
	CreatedAt          string          `json:"created_at"`
	UpdatedAt          string          `json:"updated_at"`
}

func GetSessionStatus(c *gin.Context) {
	sessionID := c.Query("session_id")
	if sessionID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "session_id is required"})
		return
	}

	var resp SessionStatusResponse
	err := database.GetDB().QueryRow(
		`SELECT session_id, original_query, COALESCE(candidates_json, 'null'),
		        COALESCE(debate_json, 'null'), COALESCE(final_candidate_json, 'null'),
		        COALESCE(final_report, ''), COALESCE(eliminated_json, 'null'),
		        status, created_at, updated_at
		 FROM sessions WHERE session_id = ?`, sessionID,
	).Scan(
		&resp.SessionID, &resp.OriginalQuery, &resp.CandidatesJSON,
		&resp.DebateJSON, &resp.FinalCandidateJSON,
		&resp.FinalReport, &resp.EliminatedJSON,
		&resp.Status, &resp.CreatedAt, &resp.UpdatedAt,
	)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "session not found"})
		return
	}

	c.JSON(http.StatusOK, resp)
}

func GetActiveSessions(c *gin.Context) {
	userID := c.GetInt("user_id")

	rows, err := database.GetDB().Query(
		`SELECT session_id, original_query,
		        COALESCE(candidates_json, 'null'),
		        COALESCE(debate_json, 'null'),
		        COALESCE(final_candidate_json, 'null'),
		        COALESCE(final_report, ''),
		        COALESCE(eliminated_json, 'null'),
		        status, created_at, updated_at
		 FROM sessions WHERE user_id = ? AND status = 'running'
		 ORDER BY updated_at DESC`,
		userID,
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to query sessions"})
		return
	}
	defer rows.Close()

	sessions := make([]SessionStatusResponse, 0)
	for rows.Next() {
		var s SessionStatusResponse
		if err := rows.Scan(
			&s.SessionID, &s.OriginalQuery, &s.CandidatesJSON,
			&s.DebateJSON, &s.FinalCandidateJSON,
			&s.FinalReport, &s.EliminatedJSON,
			&s.Status, &s.CreatedAt, &s.UpdatedAt,
		); err != nil {
			continue
		}
		sessions = append(sessions, s)
	}

	c.JSON(http.StatusOK, gin.H{"sessions": sessions})
}