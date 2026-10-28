"""API authentication and the small server-rendered portal."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

import jwt
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pwdlib import PasswordHash
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import User


API_ISSUER = "grafana-iframe-api"
API_AUDIENCE = "grafana-iframe-api"
GRAFANA_ISSUER = "grafana-iframe-poc"
GRAFANA_AUDIENCE = "grafana-iframe-poc"
API_SECRET = Path("/run/api-secrets/jwt-secret").read_text(
    encoding="utf-8"
).strip()
PRIVATE_KEY = Path("/run/jwt-private/jwt-private.pem").read_bytes()

app = FastAPI(title="Grafana iframe PoC API")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
bearer = HTTPBearer()
hasher = PasswordHash.recommended()
PORTAL_COOKIE = "portal_access_token"
API_TOKEN_LIFETIME = timedelta(minutes=30)
GRAFANA_TOKEN_LIFETIME = timedelta(minutes=15)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    business_role: str
    company_id: str


class GrafanaTokenResponse(BaseModel):
    token: str
    grafana_base_url: str


def get_session():
    with SessionLocal() as session:
        yield session


def authenticate_user(session: Session, username: str, password: str) -> User | None:
    user = session.scalar(select(User).where(User.username == username))
    if user is None or not hasher.verify(password, user.password_hash):
        return None
    return user


def create_api_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": user.id,
            "iss": API_ISSUER,
            "aud": API_AUDIENCE,
            "iat": now,
            "nbf": now,
            "exp": now + API_TOKEN_LIFETIME,
        },
        API_SECRET,
        algorithm="HS256",
    )


def decode_api_token(token: str) -> dict:
    return jwt.decode(
        token,
        API_SECRET,
        algorithms=["HS256"],
        issuer=API_ISSUER,
        audience=API_AUDIENCE,
        options={"require": ["sub", "iss", "aud", "exp", "iat", "nbf"]},
    )


def create_grafana_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": user.id,
            "username": user.username,
            "email": user.email,
            "company_id": user.company_id,
            "jti": uuid4().hex,
            "iss": GRAFANA_ISSUER,
            "aud": GRAFANA_AUDIENCE,
            "iat": now,
            "nbf": now,
            "exp": now + GRAFANA_TOKEN_LIFETIME,
        },
        PRIVATE_KEY,
        algorithm="RS256",
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    session: Session = Depends(get_session),
) -> User:
    try:
        claims = decode_api_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid API token") from exc
    user = session.get(User, claims["sub"])
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@app.get("/health")
def health(session: Session = Depends(get_session)) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, session: Session = Depends(get_session)) -> TokenResponse:
    user = authenticate_user(session, body.username, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(access_token=create_api_token(user))


@app.get("/users/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(user, from_attributes=True)


@app.post("/auth/grafana-token", response_model=GrafanaTokenResponse)
def grafana_token(user: User = Depends(get_current_user)) -> GrafanaTokenResponse:
    return GrafanaTokenResponse(
        token=create_grafana_token(user),
        grafana_base_url=os.environ.get("GRAFANA_BASE_URL", "http://localhost:3001"),
    )


def require_portal_origin(request: Request) -> None:
    expected = f"{request.url.scheme}://{request.headers['host']}"
    if request.headers.get("origin") != expected:
        raise HTTPException(status_code=403, detail="Недопустимый Origin")


def portal_user(request: Request, session: Session) -> User | None:
    token = request.cookies.get(PORTAL_COOKIE)
    if not token:
        return None
    try:
        claims = decode_api_token(token)
    except jwt.PyJWTError:
        return None
    return session.get(User, claims["sub"])


def no_store(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/", include_in_schema=False)
def portal_root() -> RedirectResponse:
    return no_store(RedirectResponse("/portal", status_code=303))


@app.get("/portal/login", include_in_schema=False)
def portal_login_page(request: Request) -> Response:
    return no_store(templates.TemplateResponse(request, "login.html"))


@app.post("/portal/login", include_in_schema=False)
async def portal_login(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    require_portal_origin(request)
    form = await request.form()
    username = str(form.get("username", ""))
    password = str(form.get("password", ""))
    user = authenticate_user(session, username, password)
    if user is None:
        response = templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Неверный логин или пароль", "username": username},
            status_code=401,
        )
        return no_store(response)
    response = RedirectResponse("/portal", status_code=303)
    response.set_cookie(
        PORTAL_COOKIE,
        create_api_token(user),
        max_age=int(API_TOKEN_LIFETIME.total_seconds()),
        path="/portal",
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return no_store(response)


@app.get("/portal", include_in_schema=False)
def portal_profile(
    request: Request, session: Session = Depends(get_session)
) -> Response:
    user = portal_user(request, session)
    if user is None:
        return no_store(RedirectResponse("/portal/login", status_code=303))
    return no_store(
        templates.TemplateResponse(request, "profile.html", {"user": user})
    )


@app.get("/portal/monitoring", include_in_schema=False)
def portal_monitoring(
    request: Request, session: Session = Depends(get_session)
) -> Response:
    user = portal_user(request, session)
    if user is None:
        return no_store(RedirectResponse("/portal/login", status_code=303))
    grafana_base = os.environ.get("GRAFANA_BASE_URL", "http://localhost:3001")
    iframe_src = (
        f"{grafana_base.rstrip('/')}/d/adkxztz/company-overview?"
        f"{urlencode({'auth_token': create_grafana_token(user), 'kiosk': '1'})}"
    )
    response = templates.TemplateResponse(
        request,
        "monitoring.html",
        {"user": user, "iframe_src": iframe_src},
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    return no_store(response)


@app.post("/portal/logout", include_in_schema=False)
def portal_logout(request: Request) -> Response:
    require_portal_origin(request)
    response = RedirectResponse("/portal/login", status_code=303)
    response.delete_cookie(PORTAL_COOKIE, path="/portal")
    return no_store(response)
