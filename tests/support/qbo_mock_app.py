"""Local-only QBO read mock used by Docker integration tests."""

from os import environ

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI()
CLIENT_ID = "070b2e37-aa28-4911-b2b2-e493678d38f5"


def require_local_key(x_api_key: str | None) -> None:
    if x_api_key != environ.get("MOCK_QBO_API_KEY", "local-qbo-read-key"):
        raise HTTPException(status_code=401, detail="Invalid local test API key")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/clients")
def list_clients(
    summary: bool = False,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> list[dict[str, object]]:
    require_local_key(x_api_key)
    if not summary:
        raise HTTPException(status_code=400, detail="summary=true is required")
    return [
        {
            "id": CLIENT_ID,
            "status": "active",
            "environments": ["sandbox"],
        }
    ]


@app.get("/clients/{client_id}")
def client_detail(
    client_id: str,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, object]:
    require_local_key(x_api_key)
    if client_id != CLIENT_ID:
        raise HTTPException(status_code=404, detail="Unknown local test target")
    return {
        "id": CLIENT_ID,
        "status": "active",
        "credentials": [
            {
                "environment": "sandbox",
                "is_connected": environ.get("MOCK_PREVIOUS_CONNECTED", "true") == "true",
                "connection_checked_at": "2026-10-20T12:00:00Z",
            }
        ],
    }


@app.get("/qbo/{client_id}/companyinfo", response_model=None)
def company_info(
    client_id: str,
    environment: str,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, str] | JSONResponse:
    require_local_key(x_api_key)
    if client_id != CLIENT_ID or environment != "sandbox":
        raise HTTPException(status_code=404, detail="Unknown local test target")
    result = environ.get("MOCK_COMPANYINFO_RESULT", "connected")
    if result == "invalid_grant":
        return JSONResponse(
            status_code=401,
            content={
                "code": 401,
                "details": {"provider": "intuit", "oauth_error": "invalid_grant"},
            },
        )
    if result != "connected":
        raise HTTPException(status_code=503, detail="Simulated QBO connectivity failure")
    return {"CompanyName": "Local Integration Test"}
