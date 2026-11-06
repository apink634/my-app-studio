"""APP-002: signup, login, a private dashboard and logout.

The prepared helpers in ``app.security`` do the sensitive work (password hashing,
signed session cookies, CSRF checks, throttling, server-side revocation). This
module only connects them to JSON API routes and to HTML forms.
"""

import re

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from app import security
from app.schemas import LoginInput, PublicUser, SignupInput

router = APIRouter()

USERNAME_PATTERN = re.compile(r"[a-z0-9_]{3,32}")
SIGNUP_HELP = (
    "Use 3 to 32 letters, numbers or underscores for the username, "
    "and at least 15 characters for the password."
)


def _header_token(request: Request) -> str | None:
    """Read the CSRF token an API client sends in a header."""
    return request.headers.get("x-csrf-token")


def _public(user: dict) -> dict[str, str]:
    """Return only the fields that are safe to show; never a hash or session id."""
    return {key: user[key] for key in ("id", "username", "role")}


# ---------------------------------------------------------------- JSON API


@router.get("/api/csrf")
def api_csrf(request: Request, response: Response) -> dict[str, str]:
    """Start a pre-login session and hand back its CSRF token."""
    return {"csrf_token": security.csrf_token(request, response)}


@router.post("/api/signup", status_code=201, response_model=PublicUser)
def api_signup(body: SignupInput, request: Request) -> dict[str, str]:
    """Create a member. The body model rejects a role or any extra field."""
    security.require_csrf(request, _header_token(request))
    security.limit_signup(request)
    return security.signup(request.app.state.settings, body.username, body.password)


@router.post("/api/login", response_model=PublicUser)
def api_login(body: LoginInput, request: Request, response: Response) -> dict[str, str]:
    """Check the credentials and set the signed, HttpOnly session cookie."""
    security.require_csrf(request, _header_token(request))
    return security.login(request, response, body.username, body.password)


@router.get("/api/me", response_model=PublicUser)
def api_me(user: dict = Depends(security.require_user)) -> dict[str, str]:
    """401 until the visitor logs in, then their own public details."""
    return _public(user)


@router.post("/api/logout")
def api_logout(request: Request, response: Response) -> dict[str, str]:
    """Revoke the session on the server, so a copied cookie stops working."""
    security.require_csrf(request, _header_token(request))
    security.logout(request, response)
    return {"status": "logged out"}


# ------------------------------------------------------------- HTML forms


def _page(request: Request, name: str, status: int = 200, **context):
    """Render a form page with a CSRF token and any pre-login session cookie."""
    holder = Response()
    token = security.csrf_token(request, holder)
    page = request.app.state.templates.TemplateResponse(
        request=request,
        name=name,
        context={"csrf_token": token, **context},
        status_code=status,
    )
    for cookie in holder.headers.getlist("set-cookie"):
        page.headers.append("set-cookie", cookie)
    return page


def _kept_username(value: str) -> str:
    """Keep only a valid, normalized username in a re-shown form; never a password."""
    candidate = value.strip().lower()
    return candidate if USERNAME_PATTERN.fullmatch(candidate) else ""


@router.get("/signup", include_in_schema=False)
def signup_form(request: Request):
    """Show the signup form."""
    return _page(request, "signup.html")


@router.post("/signup", include_in_schema=False)
def signup_submit(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    csrf_token: str = Form(""),
):
    """Create a member from the form, or show what went wrong."""
    security.require_csrf(request, csrf_token)
    kept = _kept_username(username)
    try:
        security.limit_signup(request)
        security.signup(request.app.state.settings, username, password)
    except HTTPException as error:
        return _page(
            request, "signup.html", error.status_code, error=error.detail, username=kept
        )
    except ValidationError:
        return _page(request, "signup.html", 422, error=SIGNUP_HELP, username=kept)
    return RedirectResponse("/login", status_code=303)


@router.get("/login", include_in_schema=False)
def login_form(request: Request):
    """Show the login form."""
    return _page(request, "login.html")


@router.post("/login", include_in_schema=False)
def login_submit(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    csrf_token: str = Form(""),
):
    """Log in from the form and go to the dashboard, or show a generic error."""
    security.require_csrf(request, csrf_token)
    kept = _kept_username(username)
    redirect = RedirectResponse("/dashboard", status_code=303)
    try:
        credentials = LoginInput(username=username, password=password)
        security.login(request, redirect, credentials.username, credentials.password)
    except ValidationError:
        return _page(
            request,
            "login.html",
            401,
            error="The username or password is incorrect.",
            username=kept,
        )
    except HTTPException as error:
        return _page(
            request, "login.html", error.status_code, error=error.detail, username=kept
        )
    return redirect


@router.get("/dashboard", include_in_schema=False)
def dashboard(request: Request):
    """The private page: anonymous visitors are sent to the login page."""
    user = security.authenticate(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return _page(request, "dashboard.html", user=user)


@router.post("/logout", include_in_schema=False)
def logout_submit(request: Request, csrf_token: str = Form("")):
    """Revoke the session from the dashboard's Log out button."""
    security.require_csrf(request, csrf_token)
    redirect = RedirectResponse("/", status_code=303)
    security.logout(request, redirect)
    return redirect
