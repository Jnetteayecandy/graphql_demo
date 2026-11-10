import json
import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# กำหนด Base Directory
BASE_DIR = Path(__file__).resolve().parent

# ตั้งค่า Rate Limiter บังคับเขียนลง Redis Storage
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379")

# ตรวจสอบการเชื่อมต่อกับ Redis ล่วงหน้า
try:
    import redis
    r = redis.from_url(REDIS_URL)
    r.ping()
    print("✅ Successfully connected to Redis Storage!")
except Exception as e:
    print(f"❌ Failed to connect to Redis at {REDIS_URL}: {e}", file=sys.stderr)
    print("👉 Please make sure Redis server is running (`brew services start redis`) and `redis` package is installed.", file=sys.stderr)

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=REDIS_URL,
    strategy="fixed-window",
    headers_enabled=True
)

app = FastAPI(title="Jinja App with Redis Rate Limiting")
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# Handler จัดการกรณี Rate Limit เกิน (HTTP 429 Too Many Requests)
@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    accept_header = request.headers.get("accept", "")
    if "application/json" in accept_header or request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "message": "Rate limit exceeded. Maximum 5 login requests per minute.",
                "limit": str(exc.detail)
            }
        )
    return HTMLResponse(
        status_code=429,
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>429 Too Many Requests</title>
            <style>
                body {{ font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: #fdf2f2; margin: 0; }}
                .box {{ background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); text-align: center; max-width: 400px; }}
                h2 {{ color: #e53e3e; }}
                p {{ color: #4a5568; line-height: 1.5; }}
                a {{ display: inline-block; margin-top: 15px; padding: 10px 18px; background: #3182ce; color: white; text-decoration: none; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="box">
                <h2>429 - เข้าสู่ระบบบ่อยเกินไป</h2>
                <p>คุณพยายามเข้าสู่ระบบเกินโควต้าที่กำหนด (ไม่เกิน 5 ครั้งต่อนาที)</p>
                <p><small>Storage: Redis | {exc.detail}</small></p>
                <a href="/login">กลับไปยังหน้าเข้าสู่ระบบ</a>
            </div>
        </body>
        </html>
        """
    )

# Static & Templates
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

DATA_FILE = BASE_DIR / "items.json"

# Helper สำหรับ Authentication
def get_current_user(request: Request) -> Optional[str]:
    return request.cookies.get("user_session")

def load_items():
    if not os.path.exists(DATA_FILE):
        initial_data = [
            {"id": 1, "name": "Apple", "amount": 5, "status": "OK"},
            {"id": 2, "name": "Banana", "amount": 6, "status": "OK"},
            {"id": 3, "name": "Carrot", "amount": 7, "status": "OK"}
        ]
        save_items(initial_data)
        return initial_data
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_items(items):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

# 1. หน้าแรก (Root)
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return RedirectResponse(url="/dashboard", status_code=303)

# 2. หน้า Login UI
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={}
    )

# 3. Endpoint Login พร้อม Rate Limit 5 ครั้งต่อนาที
@app.post("/login")
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...)
):
    valid_users = {
        "Ayecandy": "1111",
        "admin": "1234"
    }

    is_authenticated = (username in valid_users and valid_users[username] == password)
    is_json = "application/json" in request.headers.get("accept", "") or request.headers.get("x-requested-with") == "XMLHttpRequest"

    if is_authenticated:
        if is_json:
            res = JSONResponse(
                content={
                    "success": True,
                    "message": "เข้าสู่ระบบสำเร็จ!",
                    "redirect": "/dashboard"
                }
            )
            res.set_cookie(key="user_session", value=username, httponly=True, max_age=3600)
            return res
        else:
            redirect_res = RedirectResponse(url="/dashboard", status_code=303)
            redirect_res.set_cookie(key="user_session", value=username, httponly=True, max_age=3600)
            return redirect_res

    if is_json:
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "message": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง กรุณาลองใหม่อีกครั้ง"
            }
        )
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"}
    )

# 4. ออกจากระบบ (Logout)
@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="user_session")
    return response

# 5. หน้า Jinja Dashboard
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, edit_id: Optional[int] = None):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    items = load_items()
    edit_item = None
    if edit_id:
        edit_item = next((item for item in items if item["id"] == edit_id), None)
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={"items": items, "edit_item": edit_item, "user": user}
    )

# เพิ่มไอเทมใหม่
@app.post("/items")
async def add_item(
    request: Request,
    name: str = Form(...), 
    amount: int = Form(...), 
    status: str = Form(...)
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    items = load_items()
    new_id = max([item["id"] for item in items], default=0) + 1
    items.append({
        "id": new_id, 
        "name": name, 
        "amount": amount, 
        "status": status
    })
    save_items(items)
    return RedirectResponse(url="/dashboard", status_code=303)

# อัปเดตข้อมูลไอเทม
@app.post("/items/edit/{item_id}")
async def update_item(
    request: Request,
    item_id: int,
    name: str = Form(...),
    amount: int = Form(...),
    status: str = Form(...)
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    items = load_items()
    for item in items:
        if item["id"] == item_id:
            item["name"] = name
            item["amount"] = amount
            item["status"] = status
            break
    save_items(items)
    return RedirectResponse(url="/dashboard", status_code=303)

# ลบไอเทม
@app.get("/items/delete/{item_id}")
async def delete_item(request: Request, item_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    items = load_items()
    items = [item for item in items if item["id"] != item_id]
    save_items(items)
    return RedirectResponse(url="/dashboard", status_code=303)