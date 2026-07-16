package handlers

import (
	"encoding/json"
	"net/http"

	"github.com/gin-gonic/gin"
	"scout-backend/database"
	"scout-backend/models"
)

func GetPreferences(c *gin.Context) {
	userID := c.GetInt("user_id")

	var memory string
	err := database.GetDB().QueryRow(
		"SELECT pref_value FROM user_preferences WHERE user_id = ? AND pref_key = 'memory'",
		userID,
	).Scan(&memory)

	prefs := make(map[string]string)
	if err == nil {
		prefs["memory"] = memory
	}

	c.JSON(http.StatusOK, models.PreferenceResponse{Preferences: prefs})
}

func SavePreferences(c *gin.Context) {
	userID := c.GetInt("user_id")
	var req models.PreferenceRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{Error: err.Error()})
		return
	}

	for key, value := range req.Preferences {
		_, err := database.GetDB().Exec(
			`INSERT INTO user_preferences (user_id, pref_key, pref_value)
			 VALUES (?, ?, ?)
			 ON DUPLICATE KEY UPDATE pref_value = VALUES(pref_value), updated_at = NOW()`,
			userID, key, value,
		)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to save preference: " + key})
			return
		}
	}

	c.JSON(http.StatusOK, gin.H{"ok": true})
}

func extractPreferencesFromAnswers(answers map[string]string) map[string]string {
	prefLabels := map[string]string{
		"position":      "偏好位置",
		"age_range":     "偏好年龄范围",
		"attributes":    "看重特质",
		"budget":        "预算范围",
		"league":        "偏好联赛",
		"style":         "战术风格",
		"experience":    "经验要求",
		"potential":     "潜力要求",
	}

	prefs := make(map[string]string)
	for k, v := range answers {
		if label, ok := prefLabels[k]; ok {
			prefs[label] = v
		} else {
			prefs[k] = v
		}
	}
	if len(prefs) == 0 {
		data, _ := json.Marshal(answers)
		prefs["clarification_answers"] = string(data)
	}
	return prefs
}
