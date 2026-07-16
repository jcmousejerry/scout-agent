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
	}

	r.Run(config.ServerPort)
}
