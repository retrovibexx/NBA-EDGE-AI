# NBA Edge AI

NBA-only analytics and prediction dashboard. Uses BALLDONTLIE as the primary data provider, with API credentials stored in Streamlit secrets.

## Core capabilities
- Daily NBA schedule, live/final scores and game status
- Player game logs and rolling projections for points, rebounds, assists, steals, blocks, threes and minutes
- Injury report and projected/confirmed starting lineups (GOAT plan endpoints)
- Sportsbook game odds and player props where provider coverage exists
- Team recent-form, rest, head-to-head, pace, efficiency and injury-impact context
- Monte Carlo game simulations
- Candidate 3–6 leg parlay builder with same-game/player correlation exclusions
- Prediction history, automatic result grading, hit-rate metrics and walk-forward player backtesting
- Source freshness and API health visibility

## Data provider
Recommended: BALLDONTLIE NBA GOAT, currently listed at $39.99/month for NBA. Confirm current terms in your account dashboard before subscribing.

Create an account at https://app.balldontlie.io/ and add NBA GOAT. API docs: https://docs.balldontlie.io/

Trial note: BALLDONTLIE states GOAT trial requests are limited to 5 requests/minute; paid GOAT is listed at 600 requests/minute. The parlay scan may take longer during the trial.

## Configure Streamlit
In Streamlit Community Cloud → App → Settings → Secrets, add:

    BALLDONTLIE_API_KEY = "paste_your_key_here"

Never commit a real API key to GitHub or paste it into chat.

## Run
    pip install -r requirements.txt
    streamlit run app.py

## Model caveats
Projections are estimates from recent box-score distributions. Small samples, injuries, role changes, lineup uncertainty, blowouts and overtime can invalidate them. The parlay builder is a research shortlist, not a guaranteed hit-rate engine. We must evaluate out-of-sample calibration before trusting model probabilities.

## Hosting
Deploy on Streamlit Community Cloud with app.py as the entry point. Add the API key through Streamlit Secrets. SQLite on ephemeral hosting may reset; move to managed Postgres before relying on long-term history.
