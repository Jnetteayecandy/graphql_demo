"""
Cookie + CORS demo endpoints (Week: Cookie)

GET  /cookies  -> shows which cookies the browser actually sent to the backend
GET  /foo      -> allowed by CORS
HEAD /foo      -> the endpoint itself works, but CORS (main.py) does not allow
                  the HEAD method, so the browser blocks it
"""

from fastapi import APIRouter, Request

router = APIRouter(tags=["cookie demo"])


@router.get("/cookies")
async def read_cookies(request: Request):
    # request.cookies = every cookie the browser attached to this request,
    # INCLUDING httponly ones (only JavaScript is blocked from httponly cookies,
    # the server always receives them).
    return {"cookies": request.cookies}


@router.api_route("/foo", methods=["GET", "HEAD"])
async def foo(request: Request):
    return {"message": f"{request.method} /foo OK"}
