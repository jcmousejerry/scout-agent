package handlers

import (
	"database/sql"
	"encoding/json"
	"log"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"scout-backend/database"
)

// ── Match simulation data-access handlers ──────────────────────────────
// 比赛模拟的持久化由 Go 后端统一管理（写入本地 MySQL）。
// Python match_sim 服务通过 /api/match-data/* 这些内部端点读写数据，
// 不再直接访问 SQLite。JSON 大字段（stats_json/events_json/tactics_json）
// 按字符串透传，Go 不解析其内部结构。

// matchTeamRow 对应 match_sim_teams 表的一行。
type matchTeamRow struct {
	ID               int    `json:"id"`
	Name             string `json:"name"`
	ShortName        string `json:"short_name"`
	League           string `json:"league"`
	Country          string `json:"country"`
	StrengthRating   int    `json:"strength_rating"`
	DefaultFormation string `json:"default_formation"`
}

// matchPlayerRow 对应 match_sim_players 表的一行。
type matchPlayerRow struct {
	ID          int    `json:"id"`
	TeamID      int    `json:"team_id"`
	Name        string `json:"name"`
	Position    string `json:"position"`
	ShirtNumber int    `json:"shirt_number"`
	Age         int    `json:"age"`
	Nationality string `json:"nationality"`
	Rating      int    `json:"rating"`
	StatsJSON   string `json:"stats_json"`
	IsStarter   bool   `json:"is_starter"`
}

// ── 球队 / 球员读取 ──────────────────────────────────────────────────────

// MatchDataListTeams 列出全部球队，按实力评分降序。
func MatchDataListTeams(c *gin.Context) {
	rows, err := database.GetDB().Query(
		`SELECT id, name, short_name, league, country, strength_rating, default_formation
		 FROM match_sim_teams ORDER BY strength_rating DESC`,
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer rows.Close()

	teams := []matchTeamRow{}
	for rows.Next() {
		var t matchTeamRow
		if err := rows.Scan(&t.ID, &t.Name, &t.ShortName, &t.League, &t.Country, &t.StrengthRating, &t.DefaultFormation); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		teams = append(teams, t)
	}
	c.JSON(http.StatusOK, gin.H{"teams": teams})
}

// MatchDataTeamDetail 返回单个球队及其全部球员（首发在前）。
func MatchDataTeamDetail(c *gin.Context) {
	id, err := strconv.Atoi(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid team id"})
		return
	}

	var t matchTeamRow
	err = database.GetDB().QueryRow(
		`SELECT id, name, short_name, league, country, strength_rating, default_formation
		 FROM match_sim_teams WHERE id = ?`, id,
	).Scan(&t.ID, &t.Name, &t.ShortName, &t.League, &t.Country, &t.StrengthRating, &t.DefaultFormation)
	if err == sql.ErrNoRows {
		c.JSON(http.StatusNotFound, gin.H{"error": "team not found"})
		return
	} else if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	players, err := queryTeamPlayers(id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	starters := []matchPlayerRow{}
	subs := []matchPlayerRow{}
	for _, p := range players {
		if p.IsStarter {
			starters = append(starters, p)
		} else {
			subs = append(subs, p)
		}
	}
	c.JSON(http.StatusOK, gin.H{
		"team":        t,
		"starters":    starters,
		"substitutes": subs,
	})
}

// queryTeamPlayers 查询某球队的全部球员，首发在前、评分降序。
func queryTeamPlayers(teamID int) ([]matchPlayerRow, error) {
	rows, err := database.GetDB().Query(
		`SELECT id, team_id, name, position, IFNULL(shirt_number,0), IFNULL(age,0),
		        IFNULL(nationality,''), IFNULL(rating,75), IFNULL(stats_json,'{}'), is_starter
		 FROM match_sim_players WHERE team_id = ?
		 ORDER BY is_starter DESC, rating DESC`, teamID,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	players := []matchPlayerRow{}
	for rows.Next() {
		var p matchPlayerRow
		var isStarter int
		if err := rows.Scan(&p.ID, &p.TeamID, &p.Name, &p.Position, &p.ShirtNumber,
			&p.Age, &p.Nationality, &p.Rating, &p.StatsJSON, &isStarter); err != nil {
			return nil, err
		}
		p.IsStarter = isStarter == 1
		players = append(players, p)
	}
	return players, nil
}

// ── 批量种子写入 ────────────────────────────────────────────────────────

// seedTeamPayload 是 /seed 请求体中单个球队的载荷。
type seedTeamPayload struct {
	Name             string             `json:"name"`
	ShortName        string             `json:"short_name"`
	League           string             `json:"league"`
	Country          string             `json:"country"`
	StrengthRating   int                `json:"strength_rating"`
	DefaultFormation string             `json:"default_formation"`
	Players          []seedPlayerPayload `json:"players"`
}

type seedPlayerPayload struct {
	Name        string `json:"name"`
	Position    string `json:"position"`
	ShirtNumber int    `json:"shirt_number"`
	Age         int    `json:"age"`
	Nationality string `json:"nationality"`
	Rating      int    `json:"rating"`
	StatsJSON   string `json:"stats_json"`
	IsStarter   bool   `json:"is_starter"`
}

// MatchDataSeed 批量 upsert 球队与球员。由 Python match_sim 启动时调用一次。
// 球队按 name 唯一、球员按 (team_id, name) 唯一，存在则更新。
func MatchDataSeed(c *gin.Context) {
	var body struct {
		Teams []seedTeamPayload `json:"teams"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	db := database.GetDB()
	teamCount, playerCount := 0, 0

	for _, t := range body.Teams {
		res, err := db.Exec(
			`INSERT INTO match_sim_teams (name, short_name, league, country, strength_rating, default_formation)
			 VALUES (?, ?, ?, ?, ?, ?)
			 ON DUPLICATE KEY UPDATE
			   short_name=VALUES(short_name), league=VALUES(league), country=VALUES(country),
			   strength_rating=VALUES(strength_rating), default_formation=VALUES(default_formation)`,
			t.Name, t.ShortName, t.League, t.Country, t.StrengthRating, t.DefaultFormation,
		)
		if err != nil {
			log.Printf("[MatchData] seed team %q failed: %v", t.Name, err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "seed team failed: " + t.Name})
			return
		}
		// 取得 team_id（新建用 LastInsertId，已存在用按名查询）
		teamID, _ := res.LastInsertId()
		if teamID == 0 {
			_ = db.QueryRow("SELECT id FROM match_sim_teams WHERE name = ?", t.Name).Scan(&teamID)
		}
		teamCount++

		for _, p := range t.Players {
			isStarter := 0
			if p.IsStarter {
				isStarter = 1
			}
			_, err := db.Exec(
				`INSERT INTO match_sim_players (team_id, name, position, shirt_number, age, nationality, rating, stats_json, is_starter)
				 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
				 ON DUPLICATE KEY UPDATE
				   position=VALUES(position), shirt_number=VALUES(shirt_number), age=VALUES(age),
				   nationality=VALUES(nationality), rating=VALUES(rating), stats_json=VALUES(stats_json), is_starter=VALUES(is_starter)`,
				teamID, p.Name, p.Position, p.ShirtNumber, p.Age, p.Nationality, p.Rating, p.StatsJSON, isStarter,
			)
			if err != nil {
				log.Printf("[MatchData] seed player %q failed: %v", p.Name, err)
				c.JSON(http.StatusInternalServerError, gin.H{"error": "seed player failed: " + p.Name})
				return
			}
			playerCount++
		}
	}

	log.Printf("[MatchData] seed done: %d teams, %d players", teamCount, playerCount)
	c.JSON(http.StatusOK, gin.H{"ok": true, "teams": teamCount, "players": playerCount})
}

// ── 比赛记录写入 / 读取 ──────────────────────────────────────────────────

// MatchDataCreateMatch 创建一条比赛记录，返回 match_id。
// 对应 Python match_engine.init() 中的 create_match_record。
func MatchDataCreateMatch(c *gin.Context) {
	var req struct {
		SessionID     string `json:"session_id"`
		HomeTeamID    int    `json:"home_team_id"`
		AwayTeamID    int    `json:"away_team_id"`
		HomeTeamName  string `json:"home_team_name"`
		AwayTeamName  string `json:"away_team_name"`
		HomeFormation string `json:"home_formation"`
		AwayFormation string `json:"away_formation"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if req.SessionID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "session_id is required"})
		return
	}

	res, err := database.GetDB().Exec(
		`INSERT INTO match_sim_matches
		   (session_id, home_team_id, away_team_id, home_team_name, away_team_name, home_formation, away_formation)
		 VALUES (?, ?, ?, ?, ?, ?, ?)`,
		req.SessionID, req.HomeTeamID, req.AwayTeamID, req.HomeTeamName, req.AwayTeamName, req.HomeFormation, req.AwayFormation,
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	matchID, _ := res.LastInsertId()
	c.JSON(http.StatusOK, gin.H{"match_id": matchID})
}

// MatchDataUpdateState 更新比赛状态（热路径：每个 tick 调用一次）。
// 对应 Python match_engine._save_state() 中的 update_match_state。
// finished_at 仅在 match_status='finished' 时写入，与原 SQLite 行为一致。
func MatchDataUpdateState(c *gin.Context) {
	sessionID := c.Param("session")
	if sessionID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "session is required"})
		return
	}

	var req struct {
		HomeScore    int    `json:"home_score"`
		AwayScore    int    `json:"away_score"`
		MatchStatus  string `json:"match_status"`
		MatchMinute  int    `json:"match_minute"`
		StatsJSON    string `json:"stats_json"`
		EventsJSON   string `json:"events_json"`
		TacticsJSON  string `json:"tactics_json"`
		LineupJSON   string `json:"lineup_json"`
		Winner       string `json:"winner"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// finished_at 仅在比赛结束时写入，与原 SQLite 行为一致（MySQL 用 NOW()）。
	finishedAtExpr := "NULL"
	if req.MatchStatus == "finished" {
		finishedAtExpr = "NOW()"
	}

	args := []interface{}{
		req.HomeScore, req.AwayScore, req.MatchStatus, req.MatchMinute,
		req.StatsJSON, req.EventsJSON, req.TacticsJSON, req.LineupJSON,
		req.Winner, sessionID,
	}

	_, err := database.GetDB().Exec(
		`UPDATE match_sim_matches SET
		   home_score=?, away_score=?, match_status=?, match_minute=?,
		   stats_json=?, events_json=?, tactics_json=?, lineup_json=?, winner=?, finished_at=`+finishedAtExpr+`
		 WHERE session_id=?`,
		args...,
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"ok": true})
}

// MatchDataGetMatch 按 session_id 取比赛记录（含全部 JSON 大字段）。
// 对应 Python get_match_by_session，用于已结束比赛在内存中已清除时读取最终状态。
func MatchDataGetMatch(c *gin.Context) {
	sessionID := c.Param("session")
	if sessionID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "session is required"})
		return
	}

	var (
		id             int
		sid            string
		homeTeamID     int
		awayTeamID     int
		homeTeamName   string
		awayTeamName   string
		homeScore      int
		awayScore      int
		matchStatus    string
		matchMinute    int
		homeFormation  string
		awayFormation  string
		statsJSON      sql.NullString
		eventsJSON     sql.NullString
		tacticsJSON    sql.NullString
		winner         sql.NullString
		createdAt      sql.NullString
		finishedAt     sql.NullString
	)
	err := database.GetDB().QueryRow(
		`SELECT id, session_id, home_team_id, away_team_id, home_team_name, away_team_name,
		        home_score, away_score, match_status, match_minute, home_formation, away_formation,
		        stats_json, events_json, tactics_json, winner, created_at, finished_at
		 FROM match_sim_matches WHERE session_id = ?`, sessionID,
	).Scan(&id, &sid, &homeTeamID, &awayTeamID, &homeTeamName, &awayTeamName,
		&homeScore, &awayScore, &matchStatus, &matchMinute, &homeFormation, &awayFormation,
		&statsJSON, &eventsJSON, &tacticsJSON, &winner, &createdAt, &finishedAt)
	if err == sql.ErrNoRows {
		c.JSON(http.StatusNotFound, gin.H{"error": "match not found"})
		return
	} else if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	match := gin.H{
		"id":              id,
		"session_id":      sid,
		"home_team_id":    homeTeamID,
		"away_team_id":    awayTeamID,
		"home_team_name":  homeTeamName,
		"away_team_name":  awayTeamName,
		"home_score":      homeScore,
		"away_score":      awayScore,
		"match_status":    matchStatus,
		"match_minute":    matchMinute,
		"home_formation":  homeFormation,
		"away_formation":  awayFormation,
		"stats_json":      statsJSON.String,
		"events_json":     eventsJSON.String,
		"tactics_json":    tacticsJSON.String,
		"winner":          winner.String,
		"created_at":      createdAt.String,
		"finished_at":     finishedAt.String,
	}
	c.JSON(http.StatusOK, gin.H{"match": match})
}

// ── 历史比赛列表 ──

func MatchDataListMatches(c *gin.Context) {
	rows, err := database.GetDB().Query(
		`SELECT session_id, home_team_name, away_team_name, home_score, away_score,
		        match_status, match_minute, created_at, finished_at
		 FROM match_sim_matches ORDER BY COALESCE(finished_at, created_at) DESC LIMIT 50`,
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer rows.Close()
	type ml struct {
		SessionID    string  `json:"session_id"`
		HomeTeamName string  `json:"home_team_name"`
		AwayTeamName string  `json:"away_team_name"`
		HomeScore    int     `json:"home_score"`
		AwayScore    int     `json:"away_score"`
		MatchStatus  string  `json:"match_status"`
		MatchMinute  int     `json:"match_minute"`
		CreatedAt    *string `json:"created_at"`
		FinishedAt   *string `json:"finished_at"`
	}
	mm := []ml{}
	for rows.Next() {
		var m ml
		if err := rows.Scan(&m.SessionID, &m.HomeTeamName, &m.AwayTeamName,
			&m.HomeScore, &m.AwayScore, &m.MatchStatus, &m.MatchMinute,
			&m.CreatedAt, &m.FinishedAt); err != nil {
			log.Printf("[MatchData] scan: %v", err)
			continue
		}
		mm = append(mm, m)
	}
	c.JSON(http.StatusOK, gin.H{"matches": mm})
}

// ── 历史比赛详情 ──

func MatchDataGetMatchDetail(c *gin.Context) {
	sessionID := c.Param("session")
	if sessionID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "session required"})
		return
	}
	var sid, home, away, hf, af, st string
	var hid, aid, hs, as, mm int
	var win sql.NullString
	var sj, ej, tj, lj, ca, fa sql.NullString
	err := database.GetDB().QueryRow(
		`SELECT session_id, home_team_id, away_team_id, home_team_name, away_team_name,
		        home_score, away_score, match_status, match_minute, home_formation, away_formation,
		        stats_json, events_json, tactics_json, lineup_json, winner, created_at, finished_at
		 FROM match_sim_matches WHERE session_id = ?`, sessionID,
	).Scan(&sid, &hid, &aid, &home, &away, &hs, &as, &st, &mm, &hf, &af,
		&sj, &ej, &tj, &lj, &win, &ca, &fa)
	if err == sql.ErrNoRows {
		c.JSON(http.StatusNotFound, gin.H{"error": "not found"})
		return
	} else if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	var sI, eI, tI, lI interface{}
	if sj.Valid { json.Unmarshal([]byte(sj.String), &sI) }
	if ej.Valid { json.Unmarshal([]byte(ej.String), &eI) }
	if tj.Valid { json.Unmarshal([]byte(tj.String), &tI) }
	if lj.Valid {
		json.Unmarshal([]byte(lj.String), &lI)
	} else {
		// 旧比赛没有 lineup_json，从球员表构建阵容快照
		lI = buildLineupFromPlayers(hid, aid)
	}
	c.JSON(http.StatusOK, gin.H{"match": gin.H{
		"session_id": sid, "home_team_name": home, "away_team_name": away,
		"home_score": hs, "away_score": as, "match_status": st, "match_minute": mm,
		"home_formation": hf, "away_formation": af,
		"stats": sI, "events": eI, "tactical_adjustments": tI, "lineup": lI,
		"winner": win.String, "created_at": ca.String, "finished_at": fa.String,
	}})
}

// buildLineupFromPlayers 从球员表读取球队的首发+替补，构造阵容快照
func buildLineupFromPlayers(homeTeamID, awayTeamID int) gin.H {
	buildTeam := func(teamID int) (starters, bench []gin.H) {
		rows, err := database.GetDB().Query(
			`SELECT name, position, shirt_number, rating, is_starter
			 FROM match_sim_players WHERE team_id = ?
			 ORDER BY is_starter DESC, rating DESC`, teamID,
		)
		if err != nil {
			return
		}
		defer rows.Close()
		for rows.Next() {
			var name, pos string
			var num, rating, isStarter int
			if err := rows.Scan(&name, &pos, &num, &rating, &isStarter); err != nil {
				continue
			}
			p := gin.H{"name": name, "position": pos, "shirt_number": num, "rating": rating}
			if isStarter == 1 {
				starters = append(starters, p)
			} else {
				bench = append(bench, p)
			}
		}
		return
	}
	hStarters, hBench := buildTeam(homeTeamID)
	aStarters, aBench := buildTeam(awayTeamID)
	return gin.H{
		"active_players_home":      hStarters,
		"bench_players_home":       hBench,
		"active_players_away":      aStarters,
		"bench_players_away":       aBench,
		"home_substitutions_used":  0,
		"away_substitutions_used":  0,
	}
}
