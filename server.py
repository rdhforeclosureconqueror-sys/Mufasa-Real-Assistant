from fastapi import FastAPI
import httpx

app = FastAPI()

MAAT_API = "https://mufasabrain.onrender.com"

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/ask")
async def ask(payload: dict):
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{MAAT_API}/ask", json=payload)
        return r.json()
