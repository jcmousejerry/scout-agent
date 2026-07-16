package database

import (
	"database/sql"
	"fmt"
	"log"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"scout-backend/config"
)

var DB *sql.DB

func Init() {
	dsn := fmt.Sprintf("%s:%s@tcp(%s:%s)/%s?charset=utf8mb4&parseTime=true&loc=Local",
		config.DBUser, config.DBPassword, config.DBHost, config.DBPort, config.DBName)

	var err error
	DB, err = sql.Open("mysql", dsn)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}

	DB.SetMaxOpenConns(25)
	DB.SetMaxIdleConns(10)
	DB.SetConnMaxLifetime(5 * time.Minute)

	if err = DB.Ping(); err != nil {
		log.Fatalf("Failed to ping database: %v", err)
	}
	log.Println("Database connected successfully")

	createTables()
}

func createTables() {
	prefsSQL := `CREATE TABLE IF NOT EXISTS user_preferences (
		id INT AUTO_INCREMENT PRIMARY KEY,
		user_id INT NOT NULL,
		pref_key VARCHAR(255) NOT NULL,
		pref_value TEXT NOT NULL,
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
		FOREIGN KEY (user_id) REFERENCES users(id),
		UNIQUE KEY uk_user_pref (user_id, pref_key)
	) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;`
	if _, err := DB.Exec(prefsSQL); err != nil {
		log.Printf("Warning: failed to create user_preferences table: %v", err)
	} else {
		log.Println("user_preferences table ready")
	}

	// 给 query_history 增加新字段（MySQL 8.0 不支持 ADD COLUMN IF NOT EXISTS，需先查 INFORMATION_SCHEMA）
	columnsToAdd := []struct {
		name string
		typ  string
	}{
		{"candidates_json", "LONGTEXT"},
		{"debate_json", "LONGTEXT"},
		{"final_candidate_json", "LONGTEXT"},
		{"eliminated_json", "LONGTEXT"},
	}
	for _, col := range columnsToAdd {
		var exists int
		err := DB.QueryRow(
			`SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
			 WHERE TABLE_SCHEMA = ? AND TABLE_NAME = 'query_history' AND COLUMN_NAME = ?`,
			config.DBName, col.name,
		).Scan(&exists)
		if err != nil {
			log.Printf("Info: check column %s -> %v", col.name, err)
			continue
		}
		if exists == 0 {
			alterSQL := fmt.Sprintf("ALTER TABLE query_history ADD COLUMN %s %s NULL", col.name, col.typ)
			if _, err := DB.Exec(alterSQL); err != nil {
				log.Printf("Info: alter query_history add %s -> %v", col.name, err)
			} else {
				log.Printf("schema migration: added column %s", col.name)
			}
		}
	}
	// 递增持久化会话表（存储每次分析各个阶段的中间状态）
	sessionSQL := `CREATE TABLE IF NOT EXISTS sessions (
		id INT AUTO_INCREMENT PRIMARY KEY,
		user_id INT NOT NULL,
		session_id VARCHAR(64) NOT NULL UNIQUE,
		original_query TEXT NOT NULL,
		candidates_json LONGTEXT NULL,
		debate_json LONGTEXT NULL,
		final_candidate_json LONGTEXT NULL,
		final_report LONGTEXT NULL,
		eliminated_json LONGTEXT NULL,
		status VARCHAR(20) DEFAULT 'running',
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
		FOREIGN KEY (user_id) REFERENCES users(id)
	) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;`
	if _, err := DB.Exec(sessionSQL); err != nil {
		log.Printf("Warning: failed to create sessions table: %v", err)
	} else {
		log.Println("sessions table ready")
	}
	log.Println("schema migrations applied")
}

func GetDB() *sql.DB {
	return DB
}
