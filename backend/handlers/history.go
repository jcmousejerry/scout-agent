package handlers

import (
	"encoding/json"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
	"scout-backend/database"
	"scout-backend/models"
)

func GetHistory(c *gin.Context) {
	userID := c.GetInt("user_id")

	rows, err := database.GetDB().Query(
		`SELECT id, user_id, query, report, retrieved_count, created_at,
		        candidates_json, debate_json, final_candidate_json, eliminated_json
		 FROM query_history WHERE user_id = ? ORDER BY created_at DESC LIMIT 50`,
		userID,
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to query history"})
		return
	}
	defer rows.Close()

	var history []models.QueryHistory
	for rows.Next() {
		var h models.QueryHistory
		var cand, debate, final, elim interface{}
		if err := rows.Scan(&h.ID, &h.UserID, &h.Query, &h.Report, &h.RetrievedCount, &h.CreatedAt,
			&cand, &debate, &final, &elim); err != nil {
			continue
		}
		if s, ok := cand.([]byte); ok {
			h.CandidatesJSON = string(s)
		}
		if s, ok := debate.([]byte); ok {
			h.DebateJSON = string(s)
		}
		if s, ok := final.([]byte); ok {
			h.FinalCandidateJSON = string(s)
		}
		if s, ok := elim.([]byte); ok {
			h.EliminatedJSON = string(s)
		}
		history = append(history, h)
	}

	if history == nil {
		history = []models.QueryHistory{}
	}

	c.JSON(http.StatusOK, gin.H{"history": history})
}

func SaveQuery(c *gin.Context, query, report string, retrievedCount int) error {
	userID := c.GetInt("user_id")
	_, err := database.GetDB().Exec(
		"INSERT INTO query_history (user_id, query, report, retrieved_count) VALUES (?, ?, ?, ?)",
		userID, query, report, retrievedCount,
	)
	return err
}

// SaveFullQuery 在 SaveQuery 基础上同时保存候选球员 JSON / 辩论过程 JSON / 最终候选 JSON / 淘汰列表 JSON.
// candidates / debate / finalCandidate 均为 JSON 字节切片；nil 表示不写入。
func SaveFullQuery(c *gin.Context, query, report string, retrievedCount int,
	candidatesJSON, debateJSON, finalCandidateJSON, eliminatedJSON []byte) error {
	userID := c.GetInt("user_id")
	if candidatesJSON == nil {
		candidatesJSON = []byte("null")
	}
	if debateJSON == nil {
		debateJSON = []byte("null")
	}
	if finalCandidateJSON == nil {
		finalCandidateJSON = []byte("null")
	}
	if eliminatedJSON == nil {
		eliminatedJSON = []byte("[]")
	}
	_, err := database.GetDB().Exec(
		`INSERT INTO query_history
		   (user_id, query, report, retrieved_count, candidates_json, debate_json, final_candidate_json, eliminated_json)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
		userID, query, report, retrievedCount,
		string(candidatesJSON), string(debateJSON), string(finalCandidateJSON), string(eliminatedJSON),
	)
	return err
}

// parseDebateJSONLines 从 SSE 缓冲里提取 event: result 数据块里的 candidates / debate_messages
// / final_candidate / eliminated 字段，返回 JSON 字节切片（任一字段缺失则返回 nil）。
func parseDebateJSONLines(fullResponse []byte) (candidates, debate, finalCand, eliminated []byte, report string, retrieved int) {
	lines := strings.Split(string(fullResponse), "\n")
	for i, line := range lines {
		if strings.HasPrefix(line, "event: result") {
			for j := i + 1; j < len(lines); j++ {
				if strings.HasPrefix(lines[j], "data: ") {
					dataStr := strings.TrimPrefix(lines[j], "data: ")
					var result struct {
						Report         string          `json:"report"`
						RetrievedCount int             `json:"retrieved_count"`
						Candidates     json.RawMessage `json:"candidates"`
						DebateMessages json.RawMessage `json:"debate_messages"`
						FinalCandidate json.RawMessage `json:"final_candidate"`
						Eliminated     json.RawMessage `json:"eliminated"`
					}
					if jerr := json.Unmarshal([]byte(dataStr), &result); jerr == nil {
						report = result.Report
						retrieved = result.RetrievedCount
						if len(result.Candidates) > 0 && string(result.Candidates) != "null" {
							candidates = []byte(result.Candidates)
						}
						if len(result.DebateMessages) > 0 && string(result.DebateMessages) != "null" {
							debate = []byte(result.DebateMessages)
						}
						if len(result.FinalCandidate) > 0 && string(result.FinalCandidate) != "null" {
							finalCand = []byte(result.FinalCandidate)
						}
						if len(result.Eliminated) > 0 && string(result.Eliminated) != "null" {
							eliminated = []byte(result.Eliminated)
						}
					}
				}
			}
		}
	}
	return
}
