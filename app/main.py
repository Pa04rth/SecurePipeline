import os

from fastapi import FastAPI, Header, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        # Fixes ZAP 10049: API responses must declare no-store
        response.headers.setdefault("Cache-Control", "no-store")
        # Fixes ZAP 90005 (Spectre site-isolation family)
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        # Defensive: prevent MIME-sniffing + clickjacking even on error pages
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response


app = FastAPI()
app.add_middleware(SecurityHeadersMiddleware)


@app.get("/items/{item_id}")
def get_item(item_id: str):
    return {"item_id": item_id}


@app.post("/items/")
def create_item():
    return {"message": "Item created"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/whoami")
def whoami(x_api_key: str | None = Header(default=None)):
    expected = os.environ.get("APP_API_KEY")
    if not expected:
        raise HTTPException(status_code=500, detail="server not configured")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="bad api key")
    return {"authenticated": True}
