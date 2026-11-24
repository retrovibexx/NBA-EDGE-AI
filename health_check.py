import os
from datetime import date
import requests

KEY=os.getenv("BALLDONTLIE_API_KEY","")
if not KEY:
    print("BALLDONTLIE_API_KEY secret not configured; scheduled provider check skipped.")
    raise SystemExit(0)
BASE="https://api.balldontlie.io"
HEAD={"Authorization":KEY}
checks=[
    ("/v1/games",{"dates[]":date.today().isoformat(),"per_page":1},"schedule"),
    ("/v1/player_injuries",{"per_page":1},"injuries"),
    ("/v2/odds",{"dates[]":date.today().isoformat(),"per_page":1},"odds"),
]
for path,params,label in checks:
    response=requests.get(BASE+path,headers=HEAD,params=params,timeout=25)
    if response.status_code==401:
        raise SystemExit(f"{label} endpoint unauthorized; verify NBA plan and API key.")
    response.raise_for_status()
    payload=response.json()
    print(f"{label}: OK ({len(payload.get('data',[]))} sample records)")
print("NBA Edge AI scheduled provider health check passed.")
