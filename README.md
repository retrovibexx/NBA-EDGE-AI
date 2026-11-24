# NBA Edge AI

NBA-only analytics and prediction dashboard. Uses BALLDONTLIE as the primary data provider, with API credentials stored in Streamlit secrets.

## Core capabilities
- Daily NBA schedule, live/final scores and game status
- Player game logs and rolling projections for points, rebounds, assists, steals, blocks, threes and minutes
- Injury report and projected/confirmed starting lineups (GOAT plan endpoints)
- Sportsbook game odds and player props where provider coverage exists
- Team recent-form, rest, head-to-head, pace, efficiency and injury-impact context
- Monte Carlo game simulations
- Opponent-aware player matchup analysis, head-to-head sample context and role/minutes trend signals
- Matchup-adjusted player prop estimates with no-vig market shrinkage and sample-size context
- Candidate 3–6 leg parlay builder with same-game/player exclusions and diversification scoring
- Market snapshot journal for tracking your own player-prop line movement over time
- Probability Brier scores for game and player-prop forecasts; CSV exports for prediction history
- Prediction history, automatic result grading, hit-rate metrics and walk-forward player backtesting
- Source freshness and API health visibility

## Data provider
Recommended: BALLDONTLIE NBA GOAT, currently listed at $39.99/month for NBA. Confirm current terms in your account dashboard before subscribing.

Create an account at https://app.balldontlie.io/ and add NBA GOAT. API docs: https://docs.balldontlie.io/

Trial note: BALLDONTLIE states GOAT trial requests are limited to 5 requests/minute; paid GOAT is listed at 600 requests/minute. The parlay scan may take longer during the trial.

## Configure Streamlit
In Streamlit Community Cloud → App → Settings → Secrets, add:

    BALLDONTLIE_API_KEY = "paste_your_key_here"
    BALLDONTLIE_RPM = 5

Keep BALLDONTLIE_RPM at 5 during the GOAT trial. After the paid GOAT subscription is active, change it to 600 to use the published paid rate limit. Never commit a real API key to GitHub or paste it into chat. If you want the hourly GitHub Actions provider check, also add a repository Actions secret named BALLDONTLIE_API_KEY under Settings → Secrets and variables → Actions.

## Automated checks
GitHub Actions runs the unit tests on pushes and pull requests. A separate hourly provider check runs when the repository Actions secret is configured. The Streamlit app refreshes data through provider-specific caches (roughly 90 seconds to 6 hours depending on the feed) and has a manual cache refresh.

## Persistent prediction history (recommended)
The app works with local SQLite by default. For durable history across Streamlit Cloud restarts, create a managed PostgreSQL database (for example, a Supabase Postgres project), copy its connection string, and add this to Streamlit Community Cloud → App → Settings → Secrets:

    DATABASE_URL = "postgresql://USER:PASSWORD@HOST:5432/DATABASE"

The app automatically switches to PostgreSQL when DATABASE_URL is present. Keep the database connection string private and never commit it to GitHub or paste it into chat. If DATABASE_URL is absent, the app uses local SQLite; hosted SQLite can reset on redeploy/restart. Market movement history starts when you capture snapshots in the Odds Movement tab; it is not a provider-supplied historical archive.

## Run
    pip install -r requirements.txt
    streamlit run app.py

## Model caveats
Projections are estimates from recent box-score distributions. Injury adjustments are heuristic weights based on season production and reported status, not official player-value ratings. Small samples, injuries, role changes, lineup uncertainty, blowouts and overtime can invalidate them. The parlay builder is a research shortlist, not a guaranteed hit-rate engine. We must evaluate out-of-sample calibration before trusting model probabilities.

## Hosting
Deploy on Streamlit Community Cloud with app.py as the entry point. Add the API key through Streamlit Secrets. SQLite on ephemeral hosting may reset; move to managed Postgres before relying on long-term history.
