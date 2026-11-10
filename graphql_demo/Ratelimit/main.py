from fastapi import FastAPI, Request, Response, Form
from fastapi.responses import JSONResponse, HTMLResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# Configure Rate Limiter with Redis storage
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379",
    headers_enabled=True
)

app = FastAPI(title="Rate Limiting Demo")
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# Handler for HTTP 429 Too Many Requests
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "message": "Rate limit exceeded. Please try again later.",
            "limit": str(exc.detail)
        }
    )

app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# 1. Login UI Page (English version)
@app.get("/", response_class=HTMLResponse)
async def login_page():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Login - Rate Limit Test</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: #f0f2f5; margin: 0; }
            .card { background: white; padding: 32px; border-radius: 12px; box-shadow: 0 4px 16px rgba(0,0,0,0.08); width: 340px; text-align: center; }
            h2 { margin-bottom: 20px; color: #202124; font-size: 22px; }
            input { width: 100%; padding: 12px; margin: 8px 0; border: 1px solid #dadce0; border-radius: 6px; box-sizing: border-box; font-size: 14px; }
            button { width: 100%; padding: 12px; background: #1a73e8; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 15px; font-weight: 600; margin-top: 10px; }
            button:hover { background: #1557b0; }
            #result { margin-top: 20px; padding: 12px; border-radius: 6px; font-size: 13px; display: none; word-break: break-word; }
            .success { background: #e6f4ea; color: #137333; border: 1px solid #ceead6; }
            .error { background: #fce8e6; color: #c5221f; border: 1px solid #fad2cf; }
            .count-info { margin-top: 16px; font-size: 12px; color: #5f6368; line-height: 1.4; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Account Login</h2>
            <form id="loginForm">
                <input type="text" id="username" value="admin" placeholder="Username" required>
                <input type="password" id="password" value="1234" placeholder="Password" required>
                <button type="submit" id="submitBtn">Sign In</button>
            </form>
            <div id="result"></div>
            <div class="count-info">
                * Policy: Maximum <strong>5 requests / minute</strong><br>
            </div>
        </div>

        <script>
            let clickCount = 0;
            document.getElementById('loginForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                clickCount++;
                const u = document.getElementById('username').value;
                const p = document.getElementById('password').value;
                const resultDiv = document.getElementById('result');

                const formData = new FormData();
                formData.append('username', u);
                formData.append('password', p);

                try {
                    const res = await fetch('/login', {
                        method: 'POST',
                        body: formData
                    });
                    const data = await res.json();
                    resultDiv.style.display = 'block';

                    if (res.status === 200) {
                        resultDiv.className = 'success';
                        resultDiv.innerHTML = `<strong>Attempt #${clickCount}: Success (200 OK)</strong><br>${data.message}`;
                    } else if (res.status === 429) {
                        resultDiv.className = 'error';
                        resultDiv.innerHTML = `<strong>Attempt #${clickCount}: Blocked! (429 Too Many Requests)</strong><br>${data.message}<br><small>(${data.limit})</small>`;
                    } else {
                        resultDiv.className = 'error';
                        resultDiv.innerHTML = `<strong>Attempt #${clickCount}: Failed (${res.status})</strong><br>${data.detail || data.message}`;
                    }
                } catch (err) {
                    resultDiv.style.display = 'block';
                    resultDiv.className = 'error';
                    resultDiv.innerText = "Failed to connect to the server.";
                }
            });
        </script>
    </body>
    </html>
    """

# 2. Login Endpoint limited to 5 requests per minute
@app.post("/login")
@limiter.limit("5/minute")
async def login(
    request: Request, 
    response: Response,
    username: str = Form(...),
    password: str = Form(...)
):
    if username == "Ayecandy" and password == "1111":
        return {"success": True, "message": "Login successful"}
    return JSONResponse(
        status_code=401,
        content={"success": False, "detail": "Invalid username or password"}
    )
