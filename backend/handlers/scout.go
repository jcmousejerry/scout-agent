package handlers

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
	"scout-backend/config"
	"scout-backend/database"
	"scout-backend/models"
)

func Scout(c *gin.Context) {
	var req models.ScoutRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{Error: err.Error()})
		return
	}
	log.Printf("[Scout] Received query: %s", req.Query)

	body, _ := json.Marshal(req)
	resp, err := http.Post(
		config.AgentAPIBaseURL+config.ScoutEndpoint,
		"application/json",
		bytes.NewReader(body),
	)
	if err != nil {
		log.Printf("[Scout] Agent call failed: %v", err)
		c.JSON(http.StatusInternalServerError, models.ErrorResponse{Error: fmt.Sprintf("agent call failed: %v", err)})
		return
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)
	var scoutResp models.ScoutResponse
	if err := json.Unmarshal(respBody, &scoutResp); err != nil {
		log.Printf("[Scout] Failed to parse agent response: %v", err)
		c.JSON(http.StatusInternalServerError, models.ErrorResponse{Error: "failed to parse agent response"})
		return
	}

	log.Printf("[Scout] Response: retrieved_count=%d, report_len=%d", scoutResp.RetrievedCount, len(scoutResp.Report))

	if err := SaveQuery(c, scoutResp.Query, scoutResp.Report, scoutResp.RetrievedCount); err != nil {
		log.Printf("[Scout] Failed to save query history: %v", err)
	}

	c.JSON(http.StatusOK, scoutResp)
}

func ScoutStream(c *gin.Context) {
	var req models.ScoutRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{Error: err.Error()})
		return
	}
	log.Printf("[ScoutStream] Received query: %s", req.Query)

	body, _ := json.Marshal(req)
	log.Printf("[ScoutStream] Connecting to agent at %s%s ...", config.AgentAPIBaseURL, config.ScoutStreamEndpoint)
	agentResp, err := http.Post(
		config.AgentAPIBaseURL+config.ScoutStreamEndpoint,
		"application/json",
		bytes.NewReader(body),
	)
	if err != nil {
		log.Printf("[ScoutStream] Agent connection failed: %v", err)
		c.JSON(http.StatusInternalServerError, models.ErrorResponse{Error: fmt.Sprintf("agent call failed: %v", err)})
		return
	}
	defer agentResp.Body.Close()
	log.Printf("[ScoutStream] Connected to agent, streaming response...")

	c.Header("Content-Type", "text/event-stream")
	c.Header("Cache-Control", "no-cache")
	c.Header("Connection", "keep-alive")

	fullResponse := bytes.Buffer{}
	buf := make([]byte, 1024)
	var total int64
	for {
		n, err := agentResp.Body.Read(buf)
		if n > 0 {
			wn, werr := c.Writer.Write(buf[:n])
			fullResponse.Write(buf[:n])
			total += int64(wn)
			c.Writer.Flush()
			if werr != nil {
				log.Printf("[ScoutStream] Write error after %d bytes: %v", total, werr)
				return
			}
		}
		if err != nil {
			if err == io.EOF {
				break
			}
			log.Printf("[ScoutStream] Read error after %d bytes: %v", total, err)
			break
		}
	}
	log.Printf("[ScoutStream] Stream completed, total %d bytes", total)

	var finalReport string
	var retrievedCount int
	lines := bytes.Split(fullResponse.Bytes(), []byte("\n"))
	for i, line := range lines {
		if bytes.HasPrefix(line, []byte("event: result")) {
			for j := i + 1; j < len(lines); j++ {
				if bytes.HasPrefix(lines[j], []byte("data: ")) {
					dataStr := bytes.TrimPrefix(lines[j], []byte("data: "))
					var result struct {
						Query          string `json:"query"`
						Report         string `json:"report"`
						RetrievedCount int    `json:"retrieved_count"`
					}
					if err := json.Unmarshal(dataStr, &result); err == nil {
						finalReport = result.Report
						retrievedCount = result.RetrievedCount
					}
				}
			}
		}
	}

	if finalReport != "" {
		if err := SaveQuery(c, req.Query, finalReport, retrievedCount); err != nil {
			log.Printf("[ScoutStream] Failed to save query history: %v", err)
		}
	}
}

func ScoutClarify(c *gin.Context) {
	var req models.ClarifyRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{Error: err.Error()})
		return
	}
	queryPreview := truncateChinese(req.Query, 50)
	log.Printf("[ScoutClarify] query=%s, session=%s", queryPreview, req.SessionID)

	body, _ := json.Marshal(req)
	agentURL := config.AgentAPIBaseURL + "/api/scout/"
	if req.SessionID == "" {
		agentURL += "start"
	} else {
		agentURL += "answer"
	}

	resp, err := http.Post(agentURL, "application/json", bytes.NewReader(body))
	if err != nil {
		log.Printf("[ScoutClarify] Agent call failed: %v", err)
		c.JSON(http.StatusInternalServerError, models.ErrorResponse{Error: fmt.Sprintf("agent call failed: %v", err)})
		return
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)
	var clarifyResp models.ClarifyResponse
	if err := json.Unmarshal(respBody, &clarifyResp); err != nil {
		log.Printf("[ScoutClarify] Failed to parse: %v", err)
		c.JSON(http.StatusInternalServerError, models.ErrorResponse{Error: "failed to parse agent response"})
		return
	}

	clarifyResp.Answers = req.Answers

	if clarifyResp.ClarificationDone && req.Answers != nil {
		userID := c.GetInt("user_id")
		saveUserPreferences(userID, req.Answers)
	}

	c.JSON(http.StatusOK, clarifyResp)
}

func ScoutAnalyze(c *gin.Context) {
	var req models.AnalyzeRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{Error: err.Error()})
		return
	}
	log.Printf("[ScoutAnalyze] session=%s", req.SessionID)

	// 从 ai_agent 反查用户原始查询文本，用于归档历史记录
	queryText := req.SessionID
	if qr, qerr := http.Get(config.AgentAPIBaseURL + "/api/scout/session_query?session_id=" + req.SessionID); qerr == nil {
		if qr.StatusCode == http.StatusOK {
			var sq struct {
				Query     string `json:"query"`
				SessionID string `json:"session_id"`
			}
			body, _ := io.ReadAll(qr.Body)
			if jerr := json.Unmarshal(body, &sq); jerr == nil && sq.Query != "" {
				queryText = sq.Query
			}
		}
		qr.Body.Close()
	}

	// 读取用户偏好记忆（自然语言段落），注入到 analyze 请求中
	userID := c.GetInt("user_id")
	var memory string
	_ = database.GetDB().QueryRow(
		"SELECT pref_value FROM user_preferences WHERE user_id = ? AND pref_key = 'memory'",
		userID,
	).Scan(&memory)
	if memory != "" {
		req.PreferencesMemory = memory
	}

	body, _ := json.Marshal(req)
	agentResp, err := http.Post(
		config.AgentAPIBaseURL+"/api/scout/analyze",
		"application/json",
		bytes.NewReader(body),
	)
	if err != nil {
		log.Printf("[ScoutAnalyze] Agent call failed: %v", err)
		c.JSON(http.StatusInternalServerError, models.ErrorResponse{Error: fmt.Sprintf("agent call failed: %v", err)})
		return
	}

	if agentResp.StatusCode != http.StatusOK {
		errBody, _ := io.ReadAll(agentResp.Body)
		agentResp.Body.Close()
		log.Printf("[ScoutAnalyze] Agent returned status %d: %s", agentResp.StatusCode, string(errBody))
		c.JSON(http.StatusBadGateway, models.ErrorResponse{Error: fmt.Sprintf("agent returned status %d", agentResp.StatusCode)})
		return
	}

	c.Header("Content-Type", "text/event-stream")
	c.Header("Cache-Control", "no-cache")
	c.Header("Connection", "keep-alive")
	c.Header("X-Accel-Buffering", "no")

	defer agentResp.Body.Close()

	// 在 sessions 表中创建一条记录（递增持久化）
	sessionInsertSQL := `INSERT INTO sessions (user_id, session_id, original_query, status)
		VALUES (?, ?, ?, 'running')
		ON DUPLICATE KEY UPDATE status='running'`
	database.GetDB().Exec(sessionInsertSQL, userID, req.SessionID, queryText)

	// 用于逐行解析 SSE 事件并递增持久化
	sseScanner := bufio.NewScanner(agentResp.Body)
	sseScanner.Buffer(make([]byte, 0, 2*1024*1024), 2*1024*1024)

	// 中间状态容器（积累所有候选 / 辩论消息）
	var candidatesAccum []json.RawMessage
	var debateAccum []json.RawMessage

	// disconnected 标记前端是否已断开；断开后不再转发 SSE 给前端，
	// 但仍继续读取 ai_agent 流并持久化到 DB，确保分析完成。
	disconnected := false

	for sseScanner.Scan() {
		line := sseScanner.Text() + "\n"

		if !disconnected {
			if _, werr := c.Writer.Write([]byte(line)); werr != nil {
				log.Printf("[ScoutAnalyze] Frontend disconnected (continuing server-side processing): %v", werr)
				disconnected = true
			} else {
				c.Writer.Flush()
			}
		}

		trimmed := strings.TrimSpace(sseScanner.Text())
		if trimmed == "" || strings.HasPrefix(trimmed, ":") {
			continue
		}

		// 解析 event: xxx
		if strings.HasPrefix(trimmed, "event: ") {
			evt := strings.TrimPrefix(trimmed, "event: ")
			// 读取下一行（data: ...）
			if sseScanner.Scan() {
				dataLine := strings.TrimSpace(sseScanner.Text())
				line2 := dataLine + "\n"

				if !disconnected {
					c.Writer.Write([]byte(line2))
					c.Writer.Flush()
				}

				if !strings.HasPrefix(dataLine, "data: ") {
					continue
				}
				dataStr := strings.TrimPrefix(dataLine, "data: ")
				switch evt {
				case "candidate":
					var candData struct {
						Candidate       json.RawMessage   `json:"candidate"`
						Index           int               `json:"index"`
						Total           int               `json:"total"`
						CandidatesSoFar []json.RawMessage `json:"candidates_so_far"`
					}
					if jerr := json.Unmarshal([]byte(dataStr), &candData); jerr == nil {
						candidatesAccum = candData.CandidatesSoFar
						// 持久化到 sessions
						if len(candidatesAccum) > 0 {
							b, _ := json.Marshal(candidatesAccum)
							database.GetDB().Exec(
								`UPDATE sessions SET candidates_json=? WHERE session_id=?`,
								string(b), req.SessionID,
							)
						}
					}

				case "debate_done":
					var msgData struct {
						SpeakerKey string          `json:"speaker_key"`
						Speaker    string          `json:"speaker"`
						Content    string          `json:"content"`
						Round      int             `json:"round"`
						Type       string          `json:"type"`
						MsgID      string          `json:"msg_id"`
						Eliminated json.RawMessage `json:"eliminated,omitempty"`
					}
					if json.Unmarshal([]byte(dataStr), &msgData) == nil {
						msgBytes, _ := json.Marshal(msgData)
						debateAccum = append(debateAccum, msgBytes)
						b, _ := json.Marshal(debateAccum)
						if shouldPersistEliminated(msgData.Type, msgData.Eliminated) {
							database.GetDB().Exec(
								`UPDATE sessions SET debate_json=?, eliminated_json=? WHERE session_id=?`,
								string(b), string(msgData.Eliminated), req.SessionID,
							)
						} else {
							// 普通专家发言不含 eliminated。只能更新辩论消息，不能把
							// 已经持久化的淘汰名单覆盖成 NULL。
							database.GetDB().Exec(
								`UPDATE sessions SET debate_json=? WHERE session_id=?`,
								string(b), req.SessionID,
							)
						}
					}

				case "result":
					var resultData struct {
						Report         string          `json:"report"`
						RetrievedCount int             `json:"retrieved_count"`
						FinalCandidate json.RawMessage `json:"final_candidate"`
						Eliminated     json.RawMessage `json:"eliminated"`
						DebateMessages json.RawMessage `json:"debate_messages"`
					}
					if json.Unmarshal([]byte(dataStr), &resultData) == nil {
						candB, _ := json.Marshal(candidatesAccum)
						debateB, _ := json.Marshal(debateAccum)
						database.GetDB().Exec(
							`UPDATE sessions SET candidates_json=?, debate_json=?,
							 final_candidate_json=?, final_report=?, eliminated_json=?,
							 status='completed'
							 WHERE session_id=?`,
							string(candB), string(debateB),
							string(resultData.FinalCandidate), resultData.Report,
							string(resultData.Eliminated),
							req.SessionID,
						)
						// 同时写入 query_history 供历史查询
						SaveFullQuery(c, queryText, resultData.Report, resultData.RetrievedCount,
							candB, debateB, resultData.FinalCandidate, resultData.Eliminated)
					}
				}
			}
		}
	}
	if err := sseScanner.Err(); err != nil {
		log.Printf("[ScoutAnalyze] SSE scan error: %v", err)
	}

	if disconnected {
		log.Printf("[ScoutAnalyze] Analysis completed for session %s (frontend was disconnected)", req.SessionID)
	}
}

func shouldPersistEliminated(messageType string, raw json.RawMessage) bool {
	if messageType != "elimination" {
		return false
	}
	trimmed := bytes.TrimSpace(raw)
	if len(trimmed) == 0 || trimmed[0] != '[' {
		return false
	}
	var values []json.RawMessage
	return json.Unmarshal(trimmed, &values) == nil
}

func saveUserPreferences(userID int, answers map[string]string) {
	// 将用户偏好构建为自然语言段落，存入单条 memory 记录
	// 后续 LLM 可直接读取作为上下文，无需解析键值对
	memory := buildMemoryFromAnswers(answers)
	if memory == "" {
		return
	}
	_, err := database.GetDB().Exec(
		`INSERT INTO user_preferences (user_id, pref_key, pref_value)
		 VALUES (?, 'memory', ?)
		 ON DUPLICATE KEY UPDATE pref_value = VALUES(pref_value), updated_at = NOW()`,
		userID, memory,
	)
	if err != nil {
		log.Printf("[Preferences] Failed to save memory: %v", err)
	} else {
		log.Printf("[Preferences] Memory saved for user %d: %s", userID, truncateChinese(memory, 120))
	}
}

// buildMemoryFromAnswers 将用户澄清环节的选项（前端传过来的已是中文 label）组装为自然语言段落。
func buildMemoryFromAnswers(answers map[string]string) string {
	labelMap := map[string]string{
		"q1": "战术角色偏好",
		"q2": "引援策略偏好",
		"q3": "年龄与经验偏好",
	}
	var parts []string
	for _, qID := range []string{"q1", "q2", "q3"} {
		val, ok := answers[qID]
		if !ok {
			continue
		}
		parts = append(parts, labelMap[qID]+"："+val)
	}
	if len(parts) == 0 {
		return ""
	}
	return "用户的历史偏好：\n" + strings.Join(parts, "\n")
}

func truncateChinese(s string, maxChars int) string {
	runes := []rune(s)
	if len(runes) > maxChars {
		return string(runes[:maxChars])
	}
	return s
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
