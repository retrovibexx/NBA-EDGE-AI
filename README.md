# NBA Edge AI

A free-to-run NBA prediction dashboard for game winners and player stat projections. Built with Python and Streamlit.

## Features
- NBA schedule and scoreboard refresh
- Team and player data ingestion through the open-source `nba_api` client
- Game win-probability estimates and Monte Carlo simulations
- Player points, rebounds, assists, steals, blocks, and minutes projections when source data is available
- Recent form, home/away, rest, head-to-head, and matchup context
- Injury-data freshness warnings; unknown status is never treated as healthy
- 3–6 leg parlay research board with correlation warnings
- Prediction history and grading

## Important limitations
This project uses free public data sources. NBA Stats endpoints are unofficial, can throttle or block cloud-hosted requests, and are not guaranteed to be continuously available. Injury and lineup data may be incomplete or delayed. The app labels missing/stale inputs and does not guarantee betting results. Model confidence is an estimate, not a guaranteed real-world probability.

## Run locally
Python 3.10+

```bash
pip install -r requirements.txt
streamlit run app.py
```

No paid API key is required. Data is cached locally in `data/nba_edge.db`.

## Deploy
Deploy the repository as a Streamlit Community Cloud app and set the main file to `app.py`. The GitHub Actions workflow can refresh cached data on a schedule, but scheduled cloud jobs may be subject to provider limits. The dashboard also includes a manual refresh.

## Data attribution
NBA statistics are retrieved from NBA.com endpoints via [`nba_api`](https://github.com/swar/nba_api). Use is subject to NBA.com terms. This is an independent analytics project and is not affiliated with the NBA.