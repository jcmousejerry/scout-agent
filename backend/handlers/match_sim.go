package handlers

import (
	"bytes"
	"fmt"
	"io"
	"log"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
)

const matchSimBase = "http://localhost:8001"

// MatchSimProxy is a catch-all Gin handler that proxies all /api/match-sim/*path
// requests to the Python match_sim server running on port 8001.
//
// Gin route: auth.Any("/match-sim/*path", handlers.MatchSimProxy)
//   - path will be something like "/teams", "/match/xxx/events", etc.
//   - The full URL becomes http://localhost:8001/match-sim/<path>
func MatchSimProxy(c *gin.Context) {
	targetPath := c.Param("path") // e.g. "/teams" or "/match/abc123/events"
	proxyURL := matchSimBase + "/match-sim" + targetPath
	if c.Request.URL.RawQuery != "" {
		proxyURL += "?" + c.Request.URL.RawQuery
	}

	log.Printf("[MatchSim] Proxying %s %s", c.Request.Method, proxyURL)

	// Read request body
	var bodyBytes []byte
	if c.Request.Body != nil {
		bodyBytes, _ = io.ReadAll(c.Request.Body)
	}

	// Create proxy request
	proxyReq, err := http.NewRequest(c.Request.Method, proxyURL, bytes.NewReader(bodyBytes))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("proxy request failed: %v", err)})
		return
	}

	// Forward headers
	proxyReq.Header.Set("Content-Type", c.GetHeader("Content-Type"))
	if c.GetHeader("Accept") != "" {
		proxyReq.Header.Set("Accept", c.GetHeader("Accept"))
	}
	if c.GetHeader("Authorization") != "" {
		proxyReq.Header.Set("Authorization", c.GetHeader("Authorization"))
	}

	client := &http.Client{}
	resp, err := client.Do(proxyReq)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": fmt.Sprintf("upstream connection failed: %v", err)})
		return
	}
	defer resp.Body.Close()

	// Detect SSE streaming by content-type in the upstream response
	contentType := resp.Header.Get("Content-Type")
	if strings.Contains(contentType, "text/event-stream") {
		c.Status(resp.StatusCode)
		c.Header("Content-Type", "text/event-stream")
		c.Header("Cache-Control", "no-cache")
		c.Header("Connection", "keep-alive")
		c.Header("X-Accel-Buffering", "no")

		buf := make([]byte, 4096)
		for {
			n, err := resp.Body.Read(buf)
			if n > 0 {
				if _, writeErr := c.Writer.Write(buf[:n]); writeErr != nil {
					break
				}
				c.Writer.Flush()
			}
			if err != nil {
				break
			}
		}
		return
	}

	// Normal JSON response
	respBody, _ := io.ReadAll(resp.Body)
	c.Data(resp.StatusCode, contentType, respBody)
}
