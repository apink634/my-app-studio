"""APP-003: a server-enforced member/admin boundary.

Hiding the "Admin" link is only cosmetic. Every request below is checked on the
server, and the role is read from the database each time (see ``app.security``).
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app import security

router = APIRouter()


@router.get("/api/admin")
def api_admin(user: dict = Depends(security.require_admin)) -> dict[str, str]:
    """401 for anonymous visitors, 403 for members, 200 for admins."""
    return {"message": "Welcome, curator.", "username": user["username"]}


@router.get("/admin", include_in_schema=False)
def admin_page(request: Request):
    """Redirect anonymous visitors; refuse members; show the page to admins."""
    user = security.authenticate(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    allowed = user["role"] == "admin"
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={"user": user, "allowed": allowed},
        status_code=200 if allowed else 403,
    )
