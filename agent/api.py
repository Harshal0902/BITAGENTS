from fastapi import FastAPI
from agent_core import ComputeVaultEngine

app = FastAPI()
engine = ComputeVaultEngine()


@app.get("/")
def home():
    return {"status": "running"}


@app.post("/cycle")
def cycle():
    return engine.run_cycle()


@app.get("/state")
def state():
    return {
        "vault_id": engine.vault.vault_id,
        "capital": engine.vault.capital,
        "pnl": engine.vault.pnl_pct,
        "positions": engine.vault.positions
    }