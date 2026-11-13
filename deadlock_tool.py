#!/usr/bin/env python3
"""deadlock_tool.py - fetch and analyze Deadlock stats from the public Deadlock API.

Stdlib only. Works on JSON saved from https://api.deadlock-api.com (or fetched live
when the network allows).

Commands
  links    ACCOUNT_ID [--matches ID ...]        print API URLs to open/save
  fetch    history ACCOUNT_ID -o FILE            download match history
           match MATCH_ID -o FILE                 download per-match metadata (timeline)
           leaderboard REGION HERO_ID -o FILE     hero leaderboard (REGION: Europe, Asia,
                                                  NAmerica, SAmerica, Oceania)
  player   HISTORY.json [filters]                 full play-style report
  compare  HISTORY.json HISTORY.json ... [filters]  side-by-side, first file = "you"
  match    METADATA.json --account ID             timeline report for one match
  ids      HISTORY.json [filters] [-n N]          list match IDs (to fetch metadata)

Filters (player/compare/ids)
  --since YYYY-MM-DD   only games on/after date        --hero NAME|ID
  --ranked | --unranked                                  --all-modes (include non-standard
                                                          game modes; default = standard only)
"""
import argparse, json, statistics as st, sys, urllib.request, datetime as dt
from collections import Counter, defaultdict

API = "https://api.deadlock-api.com"
HEROES = {1: "Infernus", 2: "Seven", 3: "Vindicta", 4: "Lady Geist", 6: "Abrams", 7: "Wraith",
  8: "McGinnis", 10: "Paradox", 11: "Dynamo", 12: "Kelvin", 13: "Haze", 14: "Holliday", 15: "Bebop",
  16: "Calico", 17: "Grey Talon", 18: "Mo & Krill", 19: "Shiv", 20: "Ivy", 21: "Kali", 25: "Warden",
  27: "Yamato", 31: "Lash", 35: "Viscous", 38: "Gunslinger", 39: "The Boss", 47: "Tokamak",
  48: "Wrecker", 49: "Rutger", 50: "Pocket", 51: "Thumper", 52: "Mirage", 53: "Fathom", 54: "Cadence",
  58: "Vyper", 59: "Vandal", 60: "Sinclair", 61: "Trapper", 62: "Raven", 63: "Mina", 64: "Drifter",
  65: "Venator", 66: "Victor", 67: "Paige", 69: "The Doorman", 72: "Billy", 73: "Druid", 74: "Graf",
  75: "Fortuna", 76: "Graves", 77: "Apollo", 78: "Airheart", 79: "Rem", 80: "Silver", 81: "Celeste",
  82: "Opera", 84: "Rat King", 85: "Solomon", 88: "Baba"}
MODES = {1: "Unranked", 2: "Private", 3: "Bots", 4: "Ranked"}
STEAM64 = 76561197960265728

def hero_name(i): return HEROES.get(int(i), f"Hero#{i}")
def hero_id(s):
    if str(s).isdigit(): return int(s)
    for k, v in HEROES.items():
        if v.lower() == str(s).lower(): return k
    sys.exit(f"Unknown hero {s!r}")
def acct(s):
    s = str(s).rstrip("/").split("/")[-1]
    n = int(s); return n - STEAM64 if n > STEAM64 else n
def day(t): return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d")
def pct(x): return "–" if x != x else f"{100*x:.0f}%"

# ---------------- fetching ----------------
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "deadlock_tool/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r: return json.load(r)

def cmd_links(a):
    i = acct(a.account)
    print(f"Match history : {API}/v1/players/{i}/match-history")
    print(f"Steam profile : {API}/v1/players/{i}/steam")
    for m in a.matches or []: print(f"Match {m} timeline: {API}/v1/matches/{m}/metadata")
    print(f"Haze leaderboard NA (example): {API}/v1/leaderboard/NAmerica/13")

def cmd_fetch(a):
    url = {"history": lambda: f"{API}/v1/players/{acct(a.args[0])}/match-history",
           "match": lambda: f"{API}/v1/matches/{a.args[0]}/metadata",
           "leaderboard": lambda: f"{API}/v1/leaderboard/{a.args[0]}" + (f"/{hero_id(a.args[1])}" if len(a.args) > 1 else ""),
           "hero-stats": lambda: f"{API}/v1/analytics/hero-stats?min_average_badge={a.args[0]}"}[a.kind]()
    try:
        data = get(url)
    except Exception as e:
        sys.exit(f"Could not reach the API ({e}).\nOpen this URL in a browser, save/copy the page, and provide the file instead:\n{url}")
    json.dump(data, open(a.output, "w")); print(f"Saved {a.output} from {url}")

def cmd_top(a):
    """Leaderboard -> match histories of the top N players with an unambiguous account ID."""
    import os, time
    hero = hero_id(a.hero) if a.hero and a.hero.lower() != "any" else None
    url = f"{API}/v1/leaderboard/{a.region}" + (f"/{hero}" if hero else "")
    entries = get(url).get("entries", [])
    os.makedirs(a.outdir, exist_ok=True)
    picked, skipped = [], 0
    for pos, e in enumerate(entries, 1):
        ids = e.get("possible_account_ids") or []
        if len(ids) != 1: skipped += 1; continue
        picked.append({"position": pos, "name": e.get("account_name"), "rank": e.get("rank"),
                       "account_id": ids[0], "top_heroes": [hero_name(h) for h in e.get("top_hero_ids") or []]})
        if len(picked) >= a.n: break
    for p in picked:
        path = f"{a.outdir}/{p['account_id']}.json"
        try:
            json.dump(get(f"{API}/v1/players/{p['account_id']}/match-history"), open(path, "w"))
            p["file"] = path; print(f"#{p['position']:>3} {p['name']} ({p['account_id']}) → {path}")
        except Exception as ex:
            p["error"] = str(ex); print(f"#{p['position']:>3} {p['name']}: failed ({ex})")
        time.sleep(a.delay)
    idx = f"{a.outdir}/_index_{a.region}_{hero or 'all'}.json"
    json.dump({"source": url, "fetched": dt.datetime.now(dt.timezone.utc).isoformat(), "skipped_ambiguous": skipped,
               "players": picked}, open(idx, "w"), indent=1)
    print(f"Saved {len(picked)} players (skipped {skipped} with ambiguous IDs). Index: {idx}")

def cmd_pool(a):
    """Aggregate many histories: what heroes do these players play and win on, and who plays most like YOU."""
    import glob, math
    files = [f for pat in a.files for f in glob.glob(pat) if not f.split("/")[-1].startswith("_")]
    me = load_history(a.me, a) if a.me else None
    def shares(g):
        c = Counter(x["hero"] for x in g); n = sum(c.values()) or 1
        return {h: v / n for h, v in c.items()}
    def cos(p, q):
        dot = sum(p[h] * q.get(h, 0) for h in p)
        return dot / (math.sqrt(sum(v*v for v in p.values())) * math.sqrt(sum(v*v for v in q.values())) or 1)
    players, allg = [], []
    for f in files:
        g = load_history(f, a)
        if len(g) < a.min_games: continue
        players.append((f, g)); allg += g
    print(f"{len(players)} players, {len(allg)} games after filters\n")
    per = defaultdict(list)
    for f, g in players:
        for h in set(x["hero"] for x in g): per[h].append(f)
    print(f"{'hero':<14}{'players':>8}{'games':>7}{'WR':>6}{'K/D/A':>15}{'A/K':>6}{'D/10m':>7}{'LH/10m':>8}{'spm':>6}")
    rows = sorted(Counter(x["hero"] for x in allg).items(), key=lambda kv: -kv[1])
    for h, n in rows[:a.top]:
        s = S([x for x in allg if x["hero"] == h])
        print(f"{h:<14}{len(per[h]):>8}{n:>7}{pct(s['wr']):>6}{s['k']:>5.1f}/{s['d']:.1f}/{s['a']:<5.1f}{s['ak']:>6.2f}{s['d10']:>7.2f}{s['lh10']:>8.0f}{s['spm']:>6.0f}")
    if me:
        mine = shares(me)
        sims = sorted(((cos(mine, shares(g)), f, g) for f, g in players), key=lambda t: -t[0])
        print(f"\nPlayers whose hero pool is most like yours (cosine similarity of hero play share):")
        for sim, f, g in sims[:a.similar]:
            s = S(g); top = ", ".join(f"{h} {c}" for h, c in Counter(x['hero'] for x in g).most_common(5))
            print(f"  {sim:.2f}  {f.split('/')[-1][:-5]:>11}  {s['n']:>4} games {pct(s['wr'])}  D/10m {s['d10']:.2f}  A/K {s['ak']:.2f}  | {top}")
        sim_g = [x for _, _, g in sims[:a.similar] for x in g]
        print("\nWhat those similar players play (combined):")
        for h, n in Counter(x["hero"] for x in sim_g).most_common(a.top // 2):
            s = S([x for x in sim_g if x["hero"] == h]); ms = S([x for x in me if x["hero"] == h])
            print(f"  {h:<14} {n:>4} games {pct(s['wr']):>4}  D/10m {s['d10']:.2f}   | you: " + (f"{ms['rec']} {pct(ms['wr'])} D/10m {ms['d10']:.2f}" if ms else "never played"))

# ---------------- match history ----------------
def load_history(path, a):
    data = json.load(open(path))
    rows = data if isinstance(data, list) else data.get("matches", [])
    out = []
    for x in rows:
        if not getattr(a, "all_modes", False) and x.get("game_mode", 1) != 1: continue
        if x.get("match_mode") not in (1, 4): continue
        if getattr(a, "ranked", False) and x["match_mode"] != 4: continue
        if getattr(a, "unranked", False) and x["match_mode"] != 1: continue
        if getattr(a, "since", None) and day(x["start_time"]) < a.since: continue
        if getattr(a, "hero", None) and x["hero_id"] != hero_id(a.hero): continue
        o = x.get("player_match_outcome")
        x["W"] = (o == 1) if o in (1, 2) else x["match_result"] == x["player_team"]
        x["min"] = max(1, x["match_duration_s"]) / 60
        x["spm"] = x["net_worth"] / x["min"]
        x["hero"] = hero_name(x["hero_id"])
        out.append(x)
    out.sort(key=lambda x: -x["start_time"])
    return out

def S(g):
    n = len(g)
    if not n: return None
    w = sum(x["W"] for x in g); f = lambda k: sum(x[k] for x in g) / n
    k, d, a = f("player_kills"), f("player_deaths"), f("player_assists")
    return dict(n=n, w=w, rec=f"{w}-{n-w}", wr=w / n, k=k, d=d, a=a, ak=a / max(.1, k),
        d10=sum(x["player_deaths"] / x["min"] * 10 for x in g) / n, spm=f("spm"),
        lh10=sum(x["last_hits"] / x["min"] * 10 for x in g) / n, den=f("denies"), len=f("min"),
        d8=sum(x["player_deaths"] >= 8 for x in g) / n)

def line(label, s, w=24):
    if not s: return f"{label:<{w}} –"
    return (f"{label:<{w}} {s['n']:>4} {s['rec']:>8} {pct(s['wr']):>4}  {s['k']:.1f}/{s['d']:.1f}/{s['a']:.1f}"
            f"  A/K {s['ak']:.2f}  D/10m {s['d10']:.2f}  8+D {pct(s['d8']):>4}  spm {s['spm']:.0f}"
            f"  LH/10m {s['lh10']:.0f}  len {s['len']:.0f}m")

HEAD = f"{'':<24} {'n':>4} {'W-L':>8} {'WR':>4}  K/D/A          (A/K=assists per kill, D/10m=deaths per 10 min)"
LEN_B = [(0, 28), (28, 34), (34, 40), (40, 999)]
DEATH_B = [(0, 5), (6, 7), (8, 9), (10, 99)]
AK_B = [(0, .75), (.75, 1.25), (1.25, 99)]

def breakdowns(g):
    yield "Wins vs losses", [("Wins", S([x for x in g if x["W"]])), ("Losses", S([x for x in g if not x["W"]]))]
    yield "By deaths", [(f"{lo}-{hi if hi < 99 else '+'} deaths", S([x for x in g if lo <= x["player_deaths"] <= hi])) for lo, hi in DEATH_B]
    yield "By assists per kill (team vs solo play)", [(f"A/K {lo}-{hi if hi < 99 else '+'}", S([x for x in g if lo <= x["player_assists"] / max(1, x["player_kills"]) < hi])) for lo, hi in AK_B]
    yield "By game length", [(f"{lo}-{hi if hi < 999 else '+'} min", S([x for x in g if lo <= x["min"] < hi])) for lo, hi in LEN_B]
    yield "By mode", [(MODES[m], S([x for x in g if x["match_mode"] == m])) for m in (4, 1)]

def cmd_player(a):
    g = load_history(a.files[0], a)
    if not g: sys.exit("No matches after filters.")
    print(f"Account {g[0]['account_id']}  {day(g[-1]['start_time'])} → {day(g[0]['start_time'])}\n{HEAD}")
    print(line("ALL", S(g)))
    for t, rows in breakdowns(g):
        print(f"\n{t}"); [print(line(l, s)) for l, s in rows]
    print("\nHeroes (most played)")
    for h, _ in Counter(x["hero"] for x in g).most_common(a.top): print(line(h, S([x for x in g if x["hero"] == h])))
    print("\nRecent form")
    for lo, hi in [(0, 20), (20, 50), (50, 100), (100, 10**6)]:
        if lo < len(g): print(line(f"games {lo+1}-{min(hi, len(g))}", S(g[lo:hi])))
    seq = sorted(g, key=lambda x: x["start_time"]); sess, cur = [], []
    for x in seq:
        if cur and x["start_time"] - cur[-1]["start_time"] > 3 * 3600: sess.append(cur); cur = []
        cur.append(x)
    sess.append(cur)
    print("\nPosition in session (3h gap = new session)")
    for lo, hi in [(1, 2), (3, 4), (5, 99)]:
        print(line(f"game #{lo}-{hi if hi < 99 else '+'}", S([x for s in sess for i, x in enumerate(s, 1) if lo <= i <= hi])))
    aw = [c for p, c in zip(seq, seq[1:]) if c["start_time"] - p["start_time"] < 3 * 3600 and p["W"]]
    al = [c for p, c in zip(seq, seq[1:]) if c["start_time"] - p["start_time"] < 3 * 3600 and not p["W"]]
    print(line("after a win", S(aw))); print(line("after a loss", S(al)))

def cmd_compare(a):
    sets = [(f.split("/")[-1], load_history(f, a)) for f in a.files]
    names = a.names.split(",") if a.names else [f"P{i}" if i else "YOU" for i in range(len(sets))]
    keys = [("games", "n", "{:.0f}"), ("win rate", "wr", "pct"), ("kills", "k", "{:.1f}"), ("deaths", "d", "{:.1f}"),
            ("assists", "a", "{:.1f}"), ("assists/kill", "ak", "{:.2f}"), ("deaths/10min", "d10", "{:.2f}"),
            ("8+ death games", "d8", "pct"), ("souls/min", "spm", "{:.0f}"), ("last hits/10min", "lh10", "{:.0f}"),
            ("denies", "den", "{:.1f}"), ("avg length", "len", "{:.0f}m")]
    def table(title, sel):
        ss = [S(sel(g)) for _, g in sets]
        print(f"\n{title}\n{'':<18}" + "".join(f"{n:>12}" for n in names))
        for lab, k, fmt in keys:
            cells = ["–" if not s else (pct(s[k]) if fmt == "pct" else fmt.format(s[k])) for s in ss]
            print(f"{lab:<18}" + "".join(f"{c:>12}" for c in cells))
    table("OVERALL", lambda g: g)
    table("WINS", lambda g: [x for x in g if x["W"]])
    table("LOSSES", lambda g: [x for x in g if not x["W"]])
    print("\nWIN RATE BY GAME LENGTH\n" + f"{'':<18}" + "".join(f"{n:>12}" for n in names))
    for lo, hi in LEN_B:
        cells = []
        for _, g in sets:
            s = S([x for x in g if lo <= x["min"] < hi]); cells.append("–" if not s else f"{pct(s['wr'])} ({s['n']})")
        print(f"{lo}-{hi if hi < 999 else '+'} min".ljust(18) + "".join(f"{c:>12}" for c in cells))
    print("\nWIN RATE BY DEATHS\n" + f"{'':<18}" + "".join(f"{n:>12}" for n in names))
    for lo, hi in DEATH_B:
        cells = []
        for _, g in sets:
            s = S([x for x in g if lo <= x["player_deaths"] <= hi]); cells.append("–" if not s else f"{pct(s['wr'])} ({s['n']})")
        print(f"{lo}-{hi if hi < 99 else '+'} deaths".ljust(18) + "".join(f"{c:>12}" for c in cells))
    for (f, g), n in zip(sets, names):
        rb = [x.get("ranked_display_badge") for x in g if x["match_mode"] == 4 and x.get("ranked_display_badge")]
        print(f"{n}: {f}, {len(g)} games, latest ranked badge {rb[0] if rb else '–'}"
              + (f", {day(g[-1]['start_time'])} → {day(g[0]['start_time'])}" if g else ""))

def cmd_ids(a):
    for x in load_history(a.files[0], a)[:a.n]:
        print(x["match_id"], day(x["start_time"]), MODES[x["match_mode"]], x["hero"], "W" if x["W"] else "L",
              f"{x['player_kills']}/{x['player_deaths']}/{x['player_assists']}", f"{API}/v1/matches/{x['match_id']}/metadata")

# ---------------- per-match metadata ----------------
def team_of(v):
    if isinstance(v, int): return v
    return 1 if str(v).endswith("1") else 0

def snap(p, t):
    best = None
    for s in p.get("stats") or []:
        if s.get("time_stamp_s", 0) <= t: best = s
    return best or {}

def cmd_match(a):
    d = json.load(open(a.file)); mi = d.get("match_info", d)
    players = mi["players"]; dur = mi["duration_s"]; win = team_of(mi.get("winning_team", 0))
    me = next((p for p in players if p.get("account_id") == acct(a.account)), None)
    if not me: sys.exit("Account not in this match.")
    my_t = team_of(me.get("team", 0))
    for p in players: p["_t"] = team_of(p.get("team", 0)); p["_h"] = hero_name(p.get("hero_id", 0))
    by_slot = {p.get("player_slot"): p for p in players}
    opp = [p for p in players if p["_t"] != my_t and p.get("assigned_lane") == me.get("assigned_lane")]
    print(f"Match {mi.get('match_id')} {day(mi.get('start_time', 0))}  {dur//60}:{dur%60:02d}  "
          f"{'WIN' if win == my_t else 'LOSS'}  you: {me['_h']}  lane opponents: {', '.join(p['_h'] for p in opp) or '?'}")
    print(f"Final: {me.get('kills')}/{me.get('deaths')}/{me.get('assists')}  souls {me.get('net_worth')}  LH {me.get('last_hits')}  denies {me.get('denies')}")
    marks = [t for t in (300, 600, 900, 1200, 1800, 2400) if t < dur] + [dur]
    def val(p, t, k): return snap(p, t).get(k, 0)
    print(f"\n{'time':>6} {'you souls':>10} {'lane opp':>9} {'team avg':>9} {'enemy avg':>10} {'you LH':>7} {'opp LH':>7}"
          f" {'you K/D/A':>10} {'dmg':>7} {'team lead':>10}")
    for t in marks:
        mine = [p for p in players if p["_t"] == my_t]; theirs = [p for p in players if p["_t"] != my_t]
        avg = lambda g, k: sum(val(p, t, k) for p in g) / max(1, len(g))
        lead = sum(val(p, t, "net_worth") for p in mine) - sum(val(p, t, "net_worth") for p in theirs)
        s = snap(me, t)
        print(f"{t//60:>4}m {s.get('net_worth', 0):>10} {avg(opp, 'net_worth'):>9.0f} {avg(mine, 'net_worth'):>9.0f}"
              f" {avg(theirs, 'net_worth'):>10.0f} {s.get('creep_kills', 0):>7} {avg(opp, 'creep_kills'):>7.0f}"
              f" {s.get('kills',0)}/{s.get('deaths',0)}/{s.get('assists',0):<4} {s.get('player_damage', 0):>7} {lead:>+10}")
    print("\nDeaths:")
    for dd in me.get("death_details") or []:
        k = by_slot.get(dd.get("killer_player_slot")); t = dd.get("game_time_s", 0)
        print(f"  {t//60:>2}:{t%60:02d}  by {k['_h'] if k else '?'}  (dead {dd.get('death_duration_s', '?')}s)")
    tl = sum(dd.get("death_duration_s", 0) for dd in me.get("death_details") or [])
    if tl: print(f"  total time dead: {tl//60}m{tl%60:02d}s ({100*tl/dur:.0f}% of the match)")
    end = snap(me, dur)
    src = {k: end.get(k, 0) for k in ("gold_lane_creep", "gold_lane_creep_orbs", "gold_neutral_creep", "gold_neutral_creep_orbs",
                                      "gold_player", "gold_player_orbs", "gold_boss", "gold_boss_orb", "gold_treasure")}
    tot = sum(src.values()) or 1
    print("\nSoul sources (end):", ", ".join(f"{k.replace('gold_', '')} {v} ({100*v/tot:.0f}%)" for k, v in src.items() if v),
          f"| lost on death {end.get('gold_death_loss', 0)} | denied {end.get('gold_denied', 0)}")
    if end.get("shots_hit") is not None and (end.get("shots_hit", 0) + end.get("shots_missed", 0)):
        print(f"Accuracy {100*end['shots_hit']/(end['shots_hit']+end.get('shots_missed',0)):.0f}%  "
              f"damage {end.get('player_damage', 0)}  taken {end.get('player_damage_taken', 0)}  healing {end.get('player_healing', 0)}")
    names = {}
    if a.items:
        for it in json.load(open(a.items)): names[it.get("id")] = it.get("name")
    buys = [i for i in me.get("items") or [] if i.get("game_time_s", 0) > 0]
    print("\nItem timings:", " | ".join(f"{i['game_time_s']//60}:{i['game_time_s']%60:02d} {names.get(i.get('item_id'), i.get('item_id'))}" for i in buys[:30]))
    print("\nAll players:")
    for p in sorted(players, key=lambda p: (p["_t"] != my_t, -p.get("net_worth", 0))):
        print(f"  {'*' if p is me else ' '} {'ally ' if p['_t'] == my_t else 'enemy'} {p['_h']:<12} lane {p.get('assigned_lane','?')}  "
              f"{p.get('kills')}/{p.get('deaths')}/{p.get('assists')}  souls {p.get('net_worth')}  LH {p.get('last_hits')}  "
              f"@10m {val(p, 600, 'net_worth')}")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("links"); p.add_argument("account"); p.add_argument("--matches", nargs="*"); p.set_defaults(fn=cmd_links)
    p = sp.add_parser("fetch"); p.add_argument("kind", choices=["history", "match", "leaderboard", "hero-stats"]); p.add_argument("args", nargs="+")
    p.add_argument("-o", "--output", required=True); p.set_defaults(fn=cmd_fetch)
    p = sp.add_parser("top", help="fetch histories of the top N leaderboard players")
    p.add_argument("region", choices=["NAmerica", "Europe", "Asia", "SAmerica", "Oceania"]); p.add_argument("--hero", default="any")
    p.add_argument("-n", type=int, default=25); p.add_argument("--outdir", default="data/top"); p.add_argument("--delay", type=float, default=1.5)
    p.set_defaults(fn=cmd_top)
    def filt(p):
        p.add_argument("--since"); p.add_argument("--hero"); p.add_argument("--all-modes", action="store_true")
        m = p.add_mutually_exclusive_group(); m.add_argument("--ranked", action="store_true"); m.add_argument("--unranked", action="store_true")
    p = sp.add_parser("player"); p.add_argument("files", nargs=1); p.add_argument("--top", type=int, default=12); filt(p); p.set_defaults(fn=cmd_player)
    p = sp.add_parser("compare"); p.add_argument("files", nargs="+"); p.add_argument("--names"); filt(p); p.set_defaults(fn=cmd_compare)
    p = sp.add_parser("pool", help="aggregate many players' histories (glob ok), optionally vs --me")
    p.add_argument("files", nargs="+"); p.add_argument("--me"); p.add_argument("--min-games", type=int, default=30)
    p.add_argument("--top", type=int, default=25); p.add_argument("--similar", type=int, default=5); filt(p); p.set_defaults(fn=cmd_pool)
    p = sp.add_parser("ids"); p.add_argument("files", nargs=1); p.add_argument("-n", type=int, default=10); filt(p); p.set_defaults(fn=cmd_ids)
    p = sp.add_parser("match"); p.add_argument("file"); p.add_argument("--account", required=True)
    p.add_argument("--items", help="optional items asset JSON (from /v1/assets/items) for item names"); p.set_defaults(fn=cmd_match)
    a = ap.parse_args(); a.fn(a)

if __name__ == "__main__":
    main()
