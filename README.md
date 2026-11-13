# deadlock-stats

Personal Deadlock stats tools built on the free, unofficial [Deadlock API](https://deadlock-api.com). Not affiliated with Valve.

## 1. Stats website (works on iPad/iPhone)

**https://notachance69.github.io/deadlock-stats/**

Enter an account ID (the number in a tracklock.gg URL) or paste a whole tracklock link. The page loads the match history straight from the API and shows:
- overview: win rate, KDA, recent form, souls/min
- play-style insights: deaths, team vs solo play, farm, game length, ranked vs unranked
- per-hero table and full match history (tap a column header to sort)
- exports: CSV (matches, heroes), raw JSON, and a "Copy summary for Claude" button

## 2. Fetch data with GitHub Actions

**Actions → Fetch Deadlock data → Run workflow** (works from the GitHub iOS app):

| kind | id | saves to |
|---|---|---|
| `history` | account ID or tracklock URL (set `recent_timelines` to also grab the last N ranked match timelines) | `data/history/<account>.json` |
| `match` | match ID(s), comma-separated | `data/matches/<match>.json` |
| `leaderboard` | region (`NAmerica`, `Europe`, …) + `hero` | `data/leaderboards/<region>_<hero>.json` |

## 3. Analysis script

`deadlock_tool.py` uses only the Python standard library:

```bash
python3 deadlock_tool.py player data/history/122627581.json --hero Haze --ranked --since 2026-01-01
python3 deadlock_tool.py compare data/history/122627581.json data/history/278919272.json --names Me,Pro --hero Haze --ranked
python3 deadlock_tool.py ids data/history/122627581.json --ranked -n 5
python3 deadlock_tool.py match data/matches/131993110.json --account 122627581
python3 deadlock_tool.py fetch history 122627581 -o me.json   # if your network can reach the API
```

Run `python3 deadlock_tool.py -h` for every command and filter.

### Notes
- Comparisons are only fair within the same period (the game economy has changed; e.g. denies dropped from about 8-11 to about 2 per game between 2024 and 2026). Use `--since`.
- Only standard game mode is included by default; add `--all-modes` to include others.
- The match history only covers games the API has collected.
