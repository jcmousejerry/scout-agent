package main

import (
	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	"scout-backend/config"
	"scout-backend/database"
	"scout-backend/handlers"
	"scout-backend/middleware"
)

func main() {
	database.Init()

	r := gin.Default()
	r.Use(cors.New(cors.Config{
		AllowOrigins:     []string{"http://localhost:3000"},
		AllowMethods:     []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowHeaders:     []string{"Origin", "Content-Type", "Authorization"},
		AllowCredentials: true,
	}))

	api := r.Group("/api")
	{
		api.POST("/register", handlers.Register)
		api.POST("/login", handlers.Login)

		auth := api.Group("")
		auth.Use(middleware.AuthRequired())
		{
			auth.POST("/scout", handlers.Scout)
			auth.POST("/scout/stream", handlers.ScoutStream)
			auth.POST("/scout/clarify", handlers.ScoutClarify)
			auth.POST("/scout/analyze", handlers.ScoutAnalyze)
			auth.GET("/history", handlers.GetHistory)
			auth.GET("/session/status", handlers.GetSessionStatus)
			auth.GET("/sessions/active", handlers.GetActiveSessions)
			auth.GET("/preferences", handlers.GetPreferences)
			auth.POST("/preferences", handlers.SavePreferences)
		}

		// Match Simulation — no auth (session_id acts as token), SSE-compatible
		// 数据访问端点：由 Go 直接读写 MySQL（比赛模拟持久化统一由 Go 管理）
		data := api.Group("/match-data")
		{
			data.GET("/teams", handlers.MatchDataListTeams)
			data.GET("/teams/:id", handlers.MatchDataTeamDetail)
			data.POST("/seed", handlers.MatchDataSeed)
			data.POST("/match", handlers.MatchDataCreateMatch)
			data.PUT("/match/:session", handlers.MatchDataUpdateState)
			data.GET("/match/:session", handlers.MatchDataGetMatch)
			data.GET("/matches", handlers.MatchDataListMatches)
			data.GET("/match/:session/detail", handlers.MatchDataGetMatchDetail)
		}

		// 模拟逻辑代理：转发给 Python match_sim 服务（:8001）
		api.Any("/match-sim/*path", handlers.MatchSimProxy)
	}

	r.Run(config.ServerPort)
}
