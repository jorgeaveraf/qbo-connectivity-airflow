"""Read-only notification ledger webhook mock; no real n8n or Slack calls."""

from os import environ

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI()


class LookupRequest(BaseModel):
    client_id: str
    environment: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook/automation/notification-ledger/last-sent/v1")
def last_sent(
    lookup: LookupRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, str | None]:
    if x_api_key != "local-router-webhook-key":
        raise HTTPException(status_code=401, detail="Invalid local key")
    if lookup.environment not in {"sandbox", "prod"}:
        raise HTTPException(status_code=400, detail="Invalid environment")
    last = environ.get("MOCK_LAST_NOTIFIED_AT")
    return {
        "result_type": "notification_ledger.last_sent.v1",
        "last_notified_at": (
            last
            if last and lookup.client_id == environ.get(
                "MOCK_CLIENT_ID", "477751f2-1142-4283-a3c0-387f8aa45fbd"
            ) and lookup.environment == "sandbox"
            else None
        )
    }
