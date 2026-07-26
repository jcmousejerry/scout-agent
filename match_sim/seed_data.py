"""Seed data for 20+ top club teams with player data."""
import json
from database import init_db, insert_team, insert_player, flush_seed


def seed_all():
    """Initialize database and insert all team/player data.

    球队/球员数据先累积到 database 模块的内存缓冲区，最后由 flush_seed()
    批量 POST 给 Go 后端写入 MySQL（match_sim_teams / match_sim_players）。
    """
    init_db()
    _seed_teams()
    result = flush_seed()
    print(f"Database seeded successfully via Go: "
          f"{result.get('teams', 0)} teams, {result.get('players', 0)} players")


def _seed_teams():
    # ─── Premier League ────────────────────────────────────────────────
    mci = insert_team("Manchester City", "MCI", "Premier League", "England", 90, "4-3-3")
    _players_mci(mci)

    ars = insert_team("Arsenal", "ARS", "Premier League", "England", 87, "4-3-3")
    _players_ars(ars)

    liv = insert_team("Liverpool", "LIV", "Premier League", "England", 88, "4-3-3")
    _players_liv(liv)

    mun = insert_team("Manchester United", "MUN", "Premier League", "England", 84, "4-2-3-1")
    _players_mun(mun)

    che = insert_team("Chelsea", "CHE", "Premier League", "England", 83, "4-2-3-1")
    _players_che(che)

    tot = insert_team("Tottenham Hotspur", "TOT", "Premier League", "England", 82, "4-3-3")
    _players_tot(tot)

    # ─── La Liga ───────────────────────────────────────────────────────
    rma = insert_team("Real Madrid", "RMA", "La Liga", "Spain", 91, "4-3-3")
    _players_rma(rma)

    fcb = insert_team("Barcelona", "FCB", "La Liga", "Spain", 86, "4-3-3")
    _players_fcb(fcb)

    atm = insert_team("Atletico Madrid", "ATM", "La Liga", "Spain", 84, "3-5-2")
    _players_atm(atm)

    # ─── Bundesliga ────────────────────────────────────────────────────
    bay = insert_team("Bayern Munich", "BAY", "Bundesliga", "Germany", 89, "4-2-3-1")
    _players_bay(bay)

    bvb = insert_team("Borussia Dortmund", "BVB", "Bundesliga", "Germany", 83, "4-3-3")
    _players_bvb(bvb)

    lev = insert_team("Bayer Leverkusen", "LEV", "Bundesliga", "Germany", 85, "3-4-3")
    _players_lev(lev)

    # ─── Serie A ───────────────────────────────────────────────────────
    int = insert_team("Inter Milan", "INT", "Serie A", "Italy", 86, "3-5-2")
    _players_int(int)

    acm = insert_team("AC Milan", "ACM", "Serie A", "Italy", 83, "4-3-3")
    _players_acm(acm)

    juv = insert_team("Juventus", "JUV", "Serie A", "Italy", 82, "3-5-2")
    _players_juv(juv)

    nap = insert_team("Napoli", "NAP", "Serie A", "Italy", 84, "4-3-3")
    _players_nap(nap)

    # ─── Ligue 1 ───────────────────────────────────────────────────────
    psg = insert_team("Paris Saint-Germain", "PSG", "Ligue 1", "France", 87, "4-3-3")
    _players_psg(psg)

    # ─── Other European ────────────────────────────────────────────────
    aja = insert_team("Ajax", "AJA", "Eredivisie", "Netherlands", 80, "4-3-3")
    _players_aja(aja)

    ben = insert_team("Benfica", "BEN", "Primeira Liga", "Portugal", 81, "4-2-3-1")
    _players_ben(ben)

    por = insert_team("Porto", "POR", "Primeira Liga", "Portugal", 80, "4-4-2")
    _players_por(por)

    cel = insert_team("Celtic", "CEL", "Scottish Premiership", "Scotland", 78, "4-3-3")
    _players_cel(cel)


# ═══════════════════════════════════════════════════════════════════════
# Player data for each team
# ═══════════════════════════════════════════════════════════════════════

def _player(team_id, name, pos, num, age, nat, rating, **stats):
    insert_player(team_id, name, pos, num, age, nat, rating, stats, 1)

def _sub(team_id, name, pos, num, age, nat, rating, **stats):
    insert_player(team_id, name, pos, num, age, nat, rating, stats, 0)


# ─── Manchester City ──────────────────────────────────────────────────
def _players_mci(t):
    p = lambda n, pos, num, age, r: _player(t, n, pos, num, age, "England", r, pace=80, shooting=78, passing=82, defense=70, stamina=85)
    s = lambda n, pos, num, age, r: _sub(t, n, pos, num, age, "England", r, pace=75, shooting=70, passing=75, defense=65, stamina=78)
    p("Ederson", "GK", 31, 31, 88); p("Ruben Dias", "CB", 3, 27, 89); p("John Stones", "CB", 5, 30, 86)
    p("Josko Gvardiol", "LB", 24, 23, 85); p("Kyle Walker", "RB", 2, 34, 83)
    p("Rodri", "CDM", 16, 28, 91); p("Kevin De Bruyne", "CM", 17, 33, 91); p("Bernardo Silva", "CM", 20, 30, 88)
    p("Phil Foden", "LW", 47, 24, 87); p("Jack Grealish", "RW", 10, 29, 84); p("Erling Haaland", "ST", 9, 24, 91)
    s("Stefan Ortega", "GK", 18, 32, 80); s("Nathan Ake", "CB", 6, 29, 84)
    s("Manuel Akanji", "CB", 25, 29, 83); s("Rico Lewis", "RB", 82, 20, 78)
    s("Mateo Kovacic", "CM", 8, 30, 82); s("Matheus Nunes", "CM", 27, 26, 80)
    s("Julian Alvarez", "ST", 19, 24, 85); s("Jeremy Doku", "LW", 11, 22, 83)
    s("Oscar Bobb", "RW", 52, 21, 76); s("Sergio Gomez", "LB", 21, 24, 77)

# ─── Real Madrid ──────────────────────────────────────────────────────
def _players_rma(t):
    p = lambda n, pos, num, age, r: _player(t, n, pos, num, age, "Spain", r)
    s = lambda n, pos, num, age, r: _sub(t, n, pos, num, age, "Spain", r)
    p("Thibaut Courtois", "GK", 1, 32, 90); p("Antonio Rudiger", "CB", 22, 31, 87)
    p("David Alaba", "CB", 4, 32, 85); p("Ferland Mendy", "LB", 23, 29, 83)
    p("Dani Carvajal", "RB", 2, 33, 85); p("Aurelien Tchouameni", "CDM", 18, 24, 86)
    p("Jude Bellingham", "CM", 5, 21, 90); p("Eduardo Camavinga", "CM", 12, 22, 85)
    p("Vinicius Junior", "LW", 7, 24, 90); p("Rodrygo", "RW", 11, 23, 86)
    p("Kylian Mbappe", "ST", 9, 26, 92)
    s("Andriy Lunin", "GK", 13, 25, 80); s("Eder Militao", "CB", 3, 26, 86)
    s("Nacho", "CB", 6, 34, 80); s("Lucas Vazquez", "RB", 17, 33, 79)
    s("Federico Valverde", "CM", 8, 26, 88); s("Luka Modric", "CM", 10, 39, 86)
    s("Toni Kroos", "CM", 14, 34, 88); s("Brahim Diaz", "CAM", 21, 25, 82)
    s("Joselu", "ST", 14, 34, 80); s("Arda Guler", "CAM", 24, 19, 78)

# ─── Bayern Munich ────────────────────────────────────────────────────
def _players_bay(t):
    p = lambda n, pos, num, age, r: _player(t, n, pos, num, age, "Germany", r)
    s = lambda n, pos, num, age, r: _sub(t, n, pos, num, age, "Germany", r)
    p("Manuel Neuer", "GK", 1, 38, 87); p("Dayot Upamecano", "CB", 2, 26, 86)
    p("Kim Min-jae", "CB", 3, 28, 85); p("Alphonso Davies", "LB", 19, 24, 86)
    p("Joshua Kimmich", "RB", 6, 29, 89); p("Leon Goretzka", "CDM", 8, 29, 85)
    p("Jamal Musiala", "CM", 42, 21, 87); p("Thomas Muller", "CAM", 25, 35, 85)
    p("Leroy Sane", "LW", 10, 28, 86); p("Serge Gnabry", "RW", 7, 29, 84)
    p("Harry Kane", "ST", 9, 31, 91)
    s("Sven Ulreich", "GK", 26, 36, 78); s("Matthijs de Ligt", "CB", 4, 25, 86)
    s("Eric Dier", "CB", 15, 30, 79); s("Raphael Guerreiro", "LB", 22, 31, 82)
    s("Konrad Laimer", "CM", 27, 27, 83); s("Aleksandar Pavlovic", "CM", 45, 20, 76)
    s("Kingsley Coman", "LW", 11, 28, 85); s("Mathys Tel", "ST", 39, 19, 79)
    s("Bryan Zaragoza", "RW", 17, 23, 78); s("Frans Kratzig", "LB", 40, 21, 74)

# ─── Barcelona ────────────────────────────────────────────────────────
def _players_fcb(t):
    p = lambda n, pos, num, age, r: _player(t, n, pos, num, age, "Spain", r)
    s = lambda n, pos, num, age, r: _sub(t, n, pos, num, age, "Spain", r)
    p("Marc-Andre ter Stegen", "GK", 1, 32, 88); p("Ronald Araujo", "CB", 4, 25, 87)
    p("Andreas Christensen", "CB", 15, 28, 84); p("Alejandro Balde", "LB", 3, 21, 83)
    p("Jules Kounde", "RB", 23, 26, 85); p("Pedri", "CM", 8, 22, 88)
    p("Frenkie de Jong", "CM", 21, 27, 87); p("Ilkay Gundogan", "CM", 22, 34, 86)
    p("Lamine Yamal", "LW", 27, 17, 82); p("Raphinha", "RW", 11, 28, 84)
    p("Robert Lewandowski", "ST", 9, 36, 89)
    s("Inaki Pena", "GK", 13, 25, 78); s("Pau Cubarsi", "CB", 2, 17, 76)
    s("Inigo Martinez", "CB", 5, 33, 81); s("Joao Cancelo", "RB", 2, 30, 85)
    s("Gavi", "CM", 6, 20, 84); s("Fermin Lopez", "CAM", 16, 21, 78)
    s("Joao Felix", "LW", 14, 25, 84); s("Ferran Torres", "ST", 7, 24, 82)
    s("Vitor Roque", "ST", 19, 19, 77); s("Marcos Alonso", "LB", 17, 33, 78)

# ─── Liverpool ────────────────────────────────────────────────────────
def _players_liv(t):
    p = lambda n, pos, num, age, r: _player(t, n, pos, num, age, "England", r)
    s = lambda n, pos, num, age, r: _sub(t, n, pos, num, age, "England", r)
    p("Alisson", "GK", 1, 32, 89); p("Virgil van Dijk", "CB", 4, 33, 89)
    p("Ibrahima Konate", "CB", 5, 25, 85); p("Andy Robertson", "LB", 26, 30, 86)
    p("Trent Alexander-Arnold", "RB", 66, 26, 88); p("Alexis Mac Allister", "CM", 10, 26, 86)
    p("Dominik Szoboszlai", "CM", 8, 24, 85); p("Curtis Jones", "CM", 17, 23, 82)
    p("Luis Diaz", "LW", 7, 27, 85); p("Mohamed Salah", "RW", 11, 32, 89)
    p("Darwin Nunez", "ST", 9, 25, 84)
    s("Caoimhin Kelleher", "GK", 62, 26, 79); s("Joe Gomez", "CB", 2, 27, 82)
    s("Jarell Quansah", "CB", 78, 21, 76); s("Kostas Tsimikas", "LB", 21, 28, 80)
    s("Wataru Endo", "CDM", 3, 31, 81); s("Harvey Elliott", "CM", 19, 21, 80)
    s("Ryan Gravenberch", "CM", 38, 22, 81); s("Cody Gakpo", "LW", 18, 25, 83)
    s("Diogo Jota", "ST", 20, 28, 85); s("Ben Doak", "RW", 50, 19, 74)

# ─── PSG ──────────────────────────────────────────────────────────────
def _players_psg(t):
    p = lambda n, pos, num, age, r: _player(t, n, pos, num, age, "France", r)
    s = lambda n, pos, num, age, r: _sub(t, n, pos, num, age, "France", r)
    p("Gianluigi Donnarumma", "GK", 99, 25, 88); p("Marquinhos", "CB", 5, 30, 87)
    p("Milan Skriniar", "CB", 37, 29, 85); p("Nuno Mendes", "LB", 25, 22, 83)
    p("Achraf Hakimi", "RB", 2, 26, 86); p("Warren Zaire-Emery", "CM", 33, 18, 82)
    p("Vitinha", "CM", 17, 24, 84); p("Fabian Ruiz", "CM", 8, 28, 83)
    p("Kylian Mbappe", "LW", 7, 26, 92); p("Ousmane Dembele", "RW", 10, 27, 85)
    p("Randal Kolo Muani", "ST", 9, 26, 84)
    s("Keylor Navas", "GK", 1, 38, 80); s("Lucas Beraldo", "CB", 35, 21, 76)
    s("Danilo Pereira", "CDM", 15, 33, 81); s("Lucas Hernandez", "LB", 21, 28, 83)
    s("Manuel Ugarte", "CDM", 4, 23, 82); s("Lee Kang-in", "CAM", 19, 23, 80)
    s("Bradley Barcola", "LW", 29, 22, 80); s("Goncalo Ramos", "ST", 23, 23, 82)
    s("Marco Asensio", "RW", 11, 28, 83); s("Nordi Mukiele", "RB", 26, 27, 80)

# ─── Inter Milan ──────────────────────────────────────────────────────
def _players_int(t):
    p = lambda n, pos, num, age, r: _player(t, n, pos, num, age, "Italy", r)
    s = lambda n, pos, num, age, r: _sub(t, n, pos, num, age, "Italy", r)
    p("Yann Sommer", "GK", 1, 36, 86); p("Francesco Acerbi", "CB", 15, 36, 84)
    p("Alessandro Bastoni", "CB", 95, 25, 86); p("Stefan de Vrij", "CB", 6, 32, 83)
    p("Federico Dimarco", "LM", 32, 27, 85); p("Denzel Dumfries", "RM", 2, 28, 84)
    p("Nicolo Barella", "CM", 23, 27, 87); p("Hakan Calhanoglu", "CDM", 20, 30, 86)
    p("Henrikh Mkhitaryan", "CM", 22, 35, 83); p("Lautaro Martinez", "ST", 10, 27, 88)
    p("Marcus Thuram", "ST", 9, 27, 85)
    s("Emil Audero", "GK", 77, 27, 78); s("Matteo Darmian", "CB", 36, 35, 81)
    s("Yann Bisseck", "CB", 31, 24, 78); s("Carlos Augusto", "LM", 30, 25, 81)
    s("Davide Frattesi", "CM", 16, 25, 83); s("Kristjan Asllani", "CDM", 21, 22, 78)
    s("Alexis Sanchez", "ST", 70, 36, 80); s("Marko Arnautovic", "ST", 8, 35, 80)
    s("Tajon Buchanan", "RM", 17, 25, 79); s("Stefano Sensi", "CM", 5, 29, 78)

# ─── Arsenal ──────────────────────────────────────────────────────────
def _players_ars(t):
    p = lambda n, pos, num, age, r: _player(t, n, pos, num, age, "England", r)
    s = lambda n, pos, num, age, r: _sub(t, n, pos, num, age, "England", r)
    p("David Raya", "GK", 22, 29, 85); p("William Saliba", "CB", 2, 23, 87)
    p("Gabriel Magalhaes", "CB", 6, 27, 86); p("Oleksandr Zinchenko", "LB", 35, 28, 84)
    p("Ben White", "RB", 4, 27, 85); p("Declan Rice", "CDM", 41, 25, 88)
    p("Martin Odegaard", "CM", 8, 26, 87); p("Kai Havertz", "CM", 29, 25, 84)
    p("Gabriel Martinelli", "LW", 11, 23, 85); p("Bukayo Saka", "RW", 7, 23, 87)
    p("Gabriel Jesus", "ST", 9, 27, 86)
    s("Aaron Ramsdale", "GK", 1, 26, 83); s("Jakub Kiwior", "CB", 15, 24, 79)
    s("Takehiro Tomiyasu", "RB", 18, 26, 82); s("Jurrien Timber", "LB", 12, 23, 82)
    s("Thomas Partey", "CDM", 5, 31, 84); s("Jorginho", "CM", 20, 33, 82)
    s("Emile Smith Rowe", "CAM", 10, 24, 81); s("Leandro Trossard", "LW", 19, 30, 84)
    s("Eddie Nketiah", "ST", 14, 25, 81); s("Reiss Nelson", "RW", 24, 25, 78)

# ─── Manchester United ────────────────────────────────────────────────
def _players_mun(t):
    p = lambda n, pos, num, age, r: _player(t, n, pos, num, age, "England", r)
    s = lambda n, pos, num, age, r: _sub(t, n, pos, num, age, "England", r)
    p("Andre Onana", "GK", 24, 28, 85); p("Lisandro Martinez", "CB", 6, 26, 85)
    p("Raphael Varane", "CB", 19, 31, 86); p("Luke Shaw", "LB", 23, 29, 84)
    p("Diogo Dalot", "RB", 20, 25, 82); p("Casemiro", "CDM", 18, 32, 86)
    p("Bruno Fernandes", "CM", 8, 30, 87); p("Mason Mount", "CM", 7, 25, 83)
    p("Marcus Rashford", "LW", 10, 27, 85); p("Alejandro Garnacho", "RW", 17, 20, 81)
    p("Rasmus Hojlund", "ST", 11, 21, 82)
    s("Altay Bayindir", "GK", 1, 26, 78); s("Harry Maguire", "CB", 5, 31, 82)
    s("Victor Lindelof", "CB", 2, 30, 80); s("Aaron Wan-Bissaka", "RB", 29, 27, 81)
    s("Sofyan Amrabat", "CDM", 4, 28, 81); s("Scott McTominay", "CM", 39, 28, 83)
    s("Christian Eriksen", "CM", 14, 32, 84); s("Antony", "RW", 21, 24, 80)
    s("Anthony Martial", "ST", 9, 29, 82); s("Amad Diallo", "RW", 16, 22, 77)

# ─── Chelsea ──────────────────────────────────────────────────────────
def _players_che(t):
    p = lambda n, pos, num, age, r: _player(t, n, pos, num, age, "England", r)
    s = lambda n, pos, num, age, r: _sub(t, n, pos, num, age, "England", r)
    p("Robert Sanchez", "GK", 1, 27, 82); p("Thiago Silva", "CB", 6, 40, 86)
    p("Levi Colwill", "CB", 26, 21, 81); p("Ben Chilwell", "LB", 21, 28, 84)
    p("Reece James", "RB", 24, 25, 85); p("Moises Caicedo", "CDM", 25, 23, 85)
    p("Enzo Fernandez", "CM", 8, 23, 86); p("Conor Gallagher", "CM", 23, 24, 84)
    p("Raheem Sterling", "LW", 7, 30, 84); p("Cole Palmer", "RW", 20, 22, 85)
    p("Nicolas Jackson", "ST", 15, 23, 81)
    s("Djordje Petrovic", "GK", 28, 25, 79); s("Axel Disasi", "CB", 2, 26, 82)
    s("Benoit Badiashile", "CB", 5, 23, 81); s("Malo Gusto", "RB", 27, 21, 81)
    s("Romeo Lavia", "CDM", 45, 20, 79); s("Mykhailo Mudryk", "LW", 10, 23, 80)
    s("Christopher Nkunku", "CAM", 18, 27, 85); s("Armando Broja", "ST", 19, 23, 79)
    s("Noni Madueke", "RW", 11, 22, 80); s("Carney Chukwuemeka", "CM", 17, 21, 77)

# ─── Atletico Madrid ──────────────────────────────────────────────────
def _players_atm(t):
    p = lambda n, pos, num, age, r: _player(t, n, pos, num, age, "Spain", r)
    s = lambda n, pos, num, age, r: _sub(t, n, pos, num, age, "Spain", r)
    p("Jan Oblak", "GK", 13, 31, 89); p("Jose Gimenez", "CB", 2, 29, 86)
    p("Stefan Savic", "CB", 15, 33, 83); p("Mario Hermoso", "CB", 22, 29, 83)
    p("Samuel Lino", "LM", 12, 24, 82); p("Nahuel Molina", "RM", 16, 26, 83)
    p("Koke", "CM", 6, 32, 85); p("Rodrigo De Paul", "CM", 5, 30, 84)
    p("Pablo Barrios", "CDM", 24, 21, 80); p("Antoine Griezmann", "ST", 7, 33, 87)
    p("Alvaro Morata", "ST", 19, 32, 84)
    s("Ivo Grbic", "GK", 1, 28, 78); s("Axel Witsel", "CB", 20, 35, 82)
    s("Reinildo", "LB", 23, 30, 81); s("Cesar Azpilicueta", "RB", 3, 35, 81)
    s("Saul Niguez", "CM", 8, 30, 83); s("Marcos Llorente", "RM", 14, 29, 84)
    s("Angel Correa", "ST", 10, 29, 83); s("Memphis Depay", "ST", 9, 30, 82)
    s("Javi Galan", "LM", 17, 30, 79); s("Rodrigo Riquelme", "CM", 25, 24, 79)

# ─── Borussia Dortmund ────────────────────────────────────────────────
def _players_bvb(t):
    p = lambda n, pos, num, age, r: _player(t, n, pos, num, age, "Germany", r)
    s = lambda n, pos, num, age, r: _sub(t, n, pos, num, age, "Germany", r)
    p("Gregor Kobel", "GK", 1, 27, 86); p("Mats Hummels", "CB", 15, 36, 85)
    p("Nico Schlotterbeck", "CB", 4, 25, 85); p("Julian Ryerson", "LB", 26, 27, 81)
    p("Marius Wolf", "RB", 17, 29, 80); p("Emre Can", "CDM", 23, 30, 84)
    p("Marco Reus", "CM", 11, 35, 85); p("Julian Brandt", "CM", 19, 28, 84)
    p("Karim Adeyemi", "LW", 27, 22, 82); p("Donyell Malen", "RW", 21, 25, 83)
    p("Sebastien Haller", "ST", 14, 30, 83)
    s("Alexander Meyer", "GK", 33, 33, 77); s("Niklas Sule", "CB", 2, 29, 84)
    s("Ramy Bensebaini", "LB", 3, 29, 80); s("Salih Ozcan", "CDM", 6, 26, 80)
    s("Felix Nmecha", "CM", 8, 24, 81); s("Marcel Sabitzer", "CM", 20, 30, 83)
    s("Jamie Bynoe-Gittens", "LW", 43, 20, 77); s("Youssoufa Moukoko", "ST", 18, 20, 80)
    s("Giovanni Reyna", "CAM", 7, 22, 81); s("Niklas Schmidt", "CM", 32, 26, 77)

# ─── Bayer Leverkusen ─────────────────────────────────────────────────
def _players_lev(t):
    p = lambda n, pos, num, age, r: _player(t, n, pos, num, age, "Germany", r)
    s = lambda n, pos, num, age, r: _sub(t, n, pos, num, age, "Germany", r)
    p("Lukas Hradecky", "GK", 1, 35, 84); p("Jonathan Tah", "CB", 4, 28, 86)
    p("Edmond Tapsoba", "CB", 12, 25, 85); p("Odilon Kossounou", "CB", 6, 23, 82)
    p("Alex Grimaldo", "LM", 20, 29, 87); p("Jeremie Frimpong", "RM", 30, 24, 86)
    p("Granit Xhaka", "CDM", 34, 32, 85); p("Florian Wirtz", "CM", 10, 21, 87)
    p("Exequiel Palacios", "CM", 25, 26, 84); p("Moussa Diaby", "LW", 19, 25, 85)
    p("Victor Boniface", "ST", 22, 24, 84)
    s("Matej Kovar", "GK", 17, 24, 78); s("Piero Hincapie", "CB", 3, 22, 82)
    s("Arthur", "RB", 13, 21, 76); s("Robert Andrich", "CDM", 8, 30, 82)
    s("Jonas Hofmann", "CM", 7, 32, 83); s("Nadiem Amiri", "CM", 11, 28, 81)
    s("Adam Hlozek", "ST", 23, 22, 81); s("Patrik Schick", "ST", 14, 28, 83)
    s("Nathan Tella", "RW", 21, 25, 79); s("Amine Adli", "LW", 27, 24, 80)

# ─── AC Milan ─────────────────────────────────────────────────────────
def _players_acm(t):
    p = lambda n, pos, num, age, r: _player(t, n, pos, num, age, "Italy", r)
    s = lambda n, pos, num, age, r: _sub(t, n, pos, num, age, "Italy", r)
    p("Mike Maignan", "GK", 16, 29, 88); p("Fikayo Tomori", "CB", 23, 27, 85)
    p("Theo Hernandez", "LB", 19, 27, 86); p("Davide Calabria", "RB", 2, 28, 82)
    p("Malick Thiaw", "CB", 28, 23, 82); p("Ismael Bennacer", "CDM", 4, 27, 84)
    p("Ruben Loftus-Cheek", "CM", 8, 28, 83); p("Tijjani Reijnders", "CM", 14, 26, 83)
    p("Rafael Leao", "LW", 10, 25, 87); p("Christian Pulisic", "RW", 11, 26, 84)
    p("Olivier Giroud", "ST", 9, 38, 85)
    s("Marco Sportiello", "GK", 57, 32, 78); s("Pierre Kalulu", "CB", 20, 24, 82)
    s("Simon Kjaer", "CB", 24, 35, 81); s("Alessandro Florenzi", "RB", 25, 33, 80)
    s("Yacine Adli", "CM", 7, 24, 80); s("Tommaso Pobega", "CM", 32, 25, 80)
    s("Samuel Chukwueze", "RW", 21, 25, 82); s("Luka Jovic", "ST", 15, 27, 81)
    s("Noah Okafor", "LW", 17, 24, 80); s("Yunus Musah", "CM", 80, 22, 79)

# ─── Juventus ─────────────────────────────────────────────────────────
def _players_juv(t):
    p = lambda n, pos, num, age, r: _player(t, n, pos, num, age, "Italy", r)
    s = lambda n, pos, num, age, r: _sub(t, n, pos, num, age, "Italy", r)
    p("Wojciech Szczesny", "GK", 1, 34, 85); p("Gleison Bremer", "CB", 3, 27, 86)
    p("Federico Gatti", "CB", 4, 26, 82); p("Danilo", "CB", 6, 33, 84)
    p("Andrea Cambiaso", "LM", 27, 24, 81); p("Weston McKennie", "RM", 16, 26, 82)
    p("Manuel Locatelli", "CDM", 5, 26, 84); p("Adrien Rabiot", "CM", 25, 29, 85)
    p("Federico Chiesa", "LM", 7, 27, 85); p("Dusan Vlahovic", "ST", 9, 24, 85)
    p("Kenan Yildiz", "CAM", 10, 19, 78)
    s("Carlo Pinsoglio", "GK", 23, 34, 76); s("Daniele Rugani", "CB", 24, 30, 80)
    s("Alex Sandro", "LB", 12, 33, 80); s("Mattia De Sciglio", "RB", 2, 32, 78)
    s("Fabio Miretti", "CM", 20, 21, 79); s("Nicolo Fagioli", "CM", 21, 23, 80)
    s("Samuel Iling-Junior", "LM", 17, 21, 77); s("Moise Kean", "ST", 18, 24, 80)
    s("Arkadiusz Milik", "ST", 14, 30, 82); s("Timothy Weah", "RM", 22, 24, 79)

# ─── Napoli ───────────────────────────────────────────────────────────
def _players_nap(t):
    p = lambda n, pos, num, age, r: _player(t, n, pos, num, age, "Italy", r)
    s = lambda n, pos, num, age, r: _sub(t, n, pos, num, age, "Italy", r)
    p("Alex Meret", "GK", 1, 27, 83); p("Giovanni Di Lorenzo", "CB", 22, 31, 85)
    p("Amir Rrahmani", "CB", 13, 30, 84); p("Mathias Olivera", "LB", 17, 27, 81)
    p("Mario Rui", "RB", 6, 33, 82); p("Stanislav Lobotka", "CDM", 68, 30, 85)
    p("Zambo Anguissa", "CM", 99, 29, 84); p("Piotr Zielinski", "CM", 20, 30, 85)
    p("Khvicha Kvaratskhelia", "LW", 77, 23, 86); p("Matteo Politano", "RW", 21, 31, 83)
    p("Victor Osimhen", "ST", 9, 26, 88)
    s("Pierluigi Gollini", "GK", 14, 29, 78); s("Juan Jesus", "CB", 5, 33, 80)
    s("Natan", "CB", 3, 23, 79); s("Pasquale Mazzocchi", "RB", 30, 29, 78)
    s("Jens Cajuste", "CDM", 24, 25, 80); s("Giacomo Raspadori", "ST", 18, 24, 82)
    s("Giovanni Simeone", "ST", 83, 29, 81); s("Cyril Ngonge", "LW", 26, 24, 79)
    s("Lindy Hysaj", "LB", 23, 30, 78); s("Alessandro Zanoli", "RB", 59, 24, 76)

# ─── Tottenham Hotspur ────────────────────────────────────────────────
def _players_tot(t):
    p = lambda n, pos, num, age, r: _player(t, n, pos, num, age, "England", r)
    s = lambda n, pos, num, age, r: _sub(t, n, pos, num, age, "England", r)
    p("Guglielmo Vicario", "GK", 13, 28, 84); p("Cristian Romero", "CB", 17, 26, 86)
    p("Micky van de Ven", "CB", 37, 23, 84); p("Destiny Udogie", "LB", 38, 22, 82)
    p("Pedro Porro", "RB", 23, 25, 83); p("Yves Bissouma", "CDM", 8, 28, 84)
    p("James Maddison", "CM", 10, 28, 86); p("Pape Matar Sarr", "CM", 29, 22, 82)
    p("Son Heung-min", "LW", 7, 32, 88); p("Dejan Kulusevski", "RW", 21, 24, 84)
    p("Richarlison", "ST", 9, 27, 83)
    s("Fraser Forster", "GK", 20, 36, 78); s("Ben Davies", "CB", 33, 31, 80)
    s("Emerson Royal", "RB", 12, 25, 81); s("Pierre-Emile Hojbjerg", "CDM", 5, 29, 83)
    s("Rodrigo Bentancur", "CM", 30, 27, 84); s("Giovani Lo Celso", "CM", 18, 28, 82)
    s("Brennan Johnson", "RW", 22, 23, 81); s("Timo Werner", "LW", 16, 28, 82)
    s("Alejo Veliz", "ST", 36, 21, 77); s("Oliver Skipp", "CM", 4, 24, 79)


# ─── Ajax ─────────────────────────────────────────────────────────────
def _players_aja(t):
    p = lambda n, pos, num, age, r: _player(t, n, pos, num, age, "Netherlands", r)
    s = lambda n, pos, num, age, r: _sub(t, n, pos, num, age, "Netherlands", r)
    p("Djamin Ramaj", "GK", 1, 23, 76); p("Jorrel Hato", "CB", 4, 18, 80)
    p("Devyne Rensch", "RB", 2, 21, 78); p("Anton Gaaei", "LB", 28, 22, 76)
    p("Jordan Henderson", "CM", 6, 34, 80); p("Kenneth Taylor", "CM", 8, 22, 79)
    p("Steven Berghuis", "RW", 7, 33, 80); p("Christian Rasmussen", "LW", 11, 21, 76)
    p("Branco van den Boomen", "CDM", 23, 28, 78); p("Chuba Akpom", "ST", 9, 28, 80)
    p("Wout Weghorst", "ST", 19, 32, 79)
    s("Remko Pasveer", "GK", 31, 40, 75); s("Josip Sutalo", "CB", 3, 24, 79)
    s("Youri Baas", "LB", 5, 21, 74); s("Givairo Read", "RB", 17, 18, 73)
    s("Sivert Mannsverk", "CM", 24, 22, 75); s("Kristian Hlynsson", "CM", 10, 19, 75)
    s("Bergs Wouter", "CAM", 21, 24, 76); s("Amourricho van Axel Dongen", "LW", 43, 19, 74)
    s("Julian Berbrugge", "RW", 27, 22, 75); s("George Basset", "ST", 16, 18, 73)

# ─── Benfica ──────────────────────────────────────────────────────────
def _players_ben(t):
    p = lambda n, pos, num, age, r: _player(t, n, pos, num, age, "Portugal", r)
    s = lambda n, pos, num, age, r: _sub(t, n, pos, num, age, "Portugal", r)
    p("Anatoliy Trubin", "GK", 1, 23, 82); p("Nicolas Otamendi", "CB", 30, 36, 82)
    p("Antonio Silva", "CB", 4, 21, 82); p("Alexander Bah", "RB", 6, 27, 80)
    p("Alvaro Carreras", "LB", 3, 21, 79); p("Orkun Kokcu", "CM", 8, 23, 83)
    p("Fredrik Aursnes", "CDM", 5, 28, 80); p("Rafa Silva", "CAM", 27, 31, 84)
    p("Angel Di Maria", "RW", 11, 36, 82); p("Kerem Akturkoglu", "LW", 17, 26, 80)
    p("Vangelis Pavlidis", "ST", 9, 26, 82)
    s("Samuel Soares", "GK", 24, 22, 75); s("Tomas Araujo", "CB", 13, 22, 78)
    s("Jan-Niklas Beste", "LB", 28, 25, 77); s("Bah Ndour", "CM", 17, 21, 75)
    s("Leandro Barreiro", "CM", 16, 24, 78); s("Renato Sanches", "CM", 29, 27, 80)
    s("Arthur Cabral", "ST", 19, 26, 80); s("Caspar Tengstedt", "ST", 21, 24, 78)
    s("Goncalo Ramos", "ST", 88, 23, 83); s("David Jurasek", "LB", 2, 24, 77)

# ─── Porto ────────────────────────────────────────────────────────────
def _players_por(t):
    p = lambda n, pos, num, age, r: _player(t, n, pos, num, age, "Portugal", r)
    s = lambda n, pos, num, age, r: _sub(t, n, pos, num, age, "Portugal", r)
    p("Diogo Costa", "GK", 1, 25, 84); p("Pepe", "CB", 3, 41, 80)
    p("Otavio Ndomba", "CB", 4, 24, 79); p("Ze Pedro", "LB", 5, 21, 77)
    p("Martim Fernandes", "RB", 2, 19, 78); p("Alan Varela", "CDM", 6, 23, 81)
    p("Stephen Eustaquio", "CM", 8, 28, 80); p("Nicolas Gonzalez", "RW", 7, 26, 82)
    p("Galeno", "LW", 11, 26, 82); p("Francisco Conceicao", "CAM", 10, 21, 80)
    p("Samu Aghehowa", "ST", 9, 21, 82)
    s("Rafael Ramos", "GK", 12, 30, 75); s("Tiago Djalo", "CB", 24, 24, 78)
    s("Wendell", "LB", 16, 31, 78); s("Joao Mario", "RB", 18, 31, 79)
    s("Mateus Uribe", "CM", 14, 33, 79); s("Vasco Sousa", "CM", 17, 21, 75)
    s("Pepê", "RW", 27, 27, 78); s("Danny Loader", "ST", 19, 25, 77)
    s("Andre Franco", "CAM", 8, 26, 79); s("Deniz Gul", "ST", 21, 22, 75)

# ─── Celtic ───────────────────────────────────────────────────────────
def _players_cel(t):
    p = lambda n, pos, num, age, r: _player(t, n, pos, num, age, "Scotland", r)
    s = lambda n, pos, num, age, r: _sub(t, n, pos, num, age, "Scotland", r)
    p("Kasper Schmeichel", "GK", 1, 38, 79); p("Cameron Carter-Vickers", "CB", 4, 28, 79)
    p("Scales Auston", "CB", 5, 26, 75); p("Alex Valle", "LB", 3, 21, 75)
    p("Alistair Johnston", "RB", 2, 26, 78); p("Callum McGregor", "CM", 8, 31, 80)
    p("Arne Engels", "CM", 7, 21, 78); p("Reo Hatate", "CM", 41, 27, 79)
    p("Nicolas Kuhn", "RW", 11, 24, 78); p("Daizen Maeda", "LW", 38, 27, 79)
    p("Kyogo Furuhashi", "ST", 10, 30, 80)
    s("Viliam Sinbo", "GK", 29, 24, 73); s("Stephen Welsh", "CB", 6, 25, 74)
    s("Greg Taylor", "LB", 16, 28, 77); s("Anthony Ralston", "RB", 17, 27, 76)
    s("Paulo Bernardo", "CM", 28, 22, 75); s("Luke McCowan", "CM", 18, 26, 75)
    s("James Forrest", "RW", 49, 33, 76); s("Adam Idah", "ST", 9, 23, 77)
    s("Yang Hyun-jun", "LW", 22, 23, 75); s("Ku-rhee Oh", "ST", 19, 33, 76)


if __name__ == "__main__":
    seed_all()