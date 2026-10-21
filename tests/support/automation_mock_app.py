"""Local-only status sink; it never calls QBO Gateway or a database."""

from fastapi import FastAPI, Header, HTTPException

app = FastAPI()
CLIENT_ID = "070b2e37-aa28-4911-b2b2-e493678d38f5"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.put("/v1/connections/{client_id}/status")
def publish_status(
    client_id: str,
    payload: dict[str, object],
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, str]:
    if x_api_key != "local-automation-key":
        raise HTTPException(status_code=401, detail="Invalid local test API key")
    if client_id != CLIENT_ID or payload.get("environment") != "sandbox":
        raise HTTPException(status_code=404, detail="Unknown local test target")
    if payload.get("is_connected") is not True:
        raise HTTPException(status_code=400, detail="Expected a successful local check")
    return {"status": "accepted"}
