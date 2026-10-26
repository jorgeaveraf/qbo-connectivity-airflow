"""Local-only status sink; it never calls QBO Gateway or a database."""

from fastapi import FastAPI, Header, HTTPException

app = FastAPI()
CLIENT_ID = "070b2e37-aa28-4911-b2b2-e493678d38f5"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/jobs", status_code=202)
def publish_job(
    payload: dict[str, object],
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, str]:
    if x_api_key != "local-automation-key":
        raise HTTPException(status_code=401, detail="Invalid local test API key")
    body = payload.get("payload")
    if payload.get("kind") != "qbo.connection_checked.v1" or not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Unexpected job kind")
    if body.get("client_id") != CLIENT_ID or body.get("environment") != "sandbox":
        raise HTTPException(status_code=404, detail="Unknown local test target")
    if not isinstance(body.get("is_connected"), bool):
        raise HTTPException(status_code=400, detail="Expected a boolean status")
    print(f"mock_status_published={body['is_connected']}", flush=True)
    return {"status": "accepted"}
