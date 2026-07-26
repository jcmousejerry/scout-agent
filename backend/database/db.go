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

	// ── Match simulation tables (持久化由 Go 统一管理，原 SQLite 已迁移至此) ──
	matchTablesSQL := []string{
		`CREATE TABLE IF NOT EXISTS match_sim_teams (
			id INT AUTO_INCREMENT PRIMARY KEY,
			name VARCHAR(255) NOT NULL UNIQUE,
			short_name VARCHAR(64) NOT NULL,
			league VARCHAR(128) NOT NULL,
			country VARCHAR(128) NOT NULL,
			strength_rating INT DEFAULT 80,
			default_formation VARCHAR(32) NOT NULL DEFAULT '4-3-3'
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;`,
		`CREATE TABLE IF NOT EXISTS match_sim_players (
			id INT AUTO_INCREMENT PRIMARY KEY,
			team_id INT NOT NULL,
			name VARCHAR(255) NOT NULL,
			position VARCHAR(16) NOT NULL,
			shirt_number INT NULL,
			age INT NULL,
			nationality VARCHAR(64) NULL,
			rating INT DEFAULT 75,
			stats_json LONGTEXT NULL,
			is_starter TINYINT DEFAULT 1,
			FOREIGN KEY (team_id) REFERENCES match_sim_teams(id),
			UNIQUE KEY uk_team_player (team_id, name)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;`,
		`CREATE TABLE IF NOT EXISTS match_sim_matches (
			id INT AUTO_INCREMENT PRIMARY KEY,
			session_id VARCHAR(64) NOT NULL UNIQUE,
			home_team_id INT NOT NULL,
			away_team_id INT NOT NULL,
			home_team_name VARCHAR(255) NOT NULL,
			away_team_name VARCHAR(255) NOT NULL,
			home_score INT DEFAULT 0,
			away_score INT DEFAULT 0,
			match_status VARCHAR(32) DEFAULT 'created',
			match_minute INT DEFAULT 0,
			home_formation VARCHAR(32) DEFAULT '4-3-3',
			away_formation VARCHAR(32) DEFAULT '4-3-3',
			stats_json LONGTEXT NULL,
			events_json LONGTEXT NULL,
			tactics_json LONGTEXT NULL,
			lineup_json LONGTEXT NULL,
			winner VARCHAR(255) NULL,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			finished_at TIMESTAMP NULL,
			FOREIGN KEY (home_team_id) REFERENCES match_sim_teams(id),
			FOREIGN KEY (away_team_id) REFERENCES match_sim_teams(id)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;`,
	}
	for _, sql := range matchTablesSQL {
		if _, err := DB.Exec(sql); err != nil {
			log.Printf("Warning: failed to create match_sim table: %v", err)
		}
	}
		// ── 为已有 match_sim_matches 表补加 lineup_json 列（向前兼容）──
		var colExists int
		if err := DB.QueryRow(
			`SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
			 WHERE TABLE_SCHEMA = ? AND TABLE_NAME = 'match_sim_matches' AND COLUMN_NAME = 'lineup_json'`,
			config.DBName,
		).Scan(&colExists); err != nil {
			log.Printf("Info: check lineup_json column: %v", err)
		} else if colExists == 0 {
			if _, err := DB.Exec("ALTER TABLE match_sim_matches ADD COLUMN lineup_json LONGTEXT NULL"); err != nil {
				log.Printf("Warning: add lineup_json column failed: %v", err)
			} else {
				log.Println("schema migration: added lineup_json column")
			}
		}

	log.Println("match_sim tables ready (teams, players, matches)")
	log.Println("schema migrations applied")
}

func GetDB() *sql.DB {
	return DB
}
