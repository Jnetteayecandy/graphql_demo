from fastapi import FastAPI, Request, HTTPException, Depends
from pydantic import BaseModel
from redis.asyncio import Redis

app = FastAPI()
r = Redis(host="localhost", port=6379, decode_responses=True)

LIMIT = 5       # จำนวนครั้งสูงสุด
WINDOW = 60     # ในเวลา 60 วินาที (1 นาที)

class LoginData(BaseModel):
    username: str
    password: str

@app.get("/ping")
async def ping():
    return {"redis": await r.ping()}

async def rate_limiter(request: Request):
    ip = request.client.host
    key = f"rate:login:{ip}"
    count = await r.incr(key)
    
    if count == 1:
        await r.expire(key, WINDOW)
        
    if count > LIMIT:
        ttl = await r.ttl(key)
        raise HTTPException(
            status_code=429,
            detail=f"Over limit. Try again in {ttl} seconds.",
        )

@app.post("/login", dependencies=[Depends(rate_limiter)])
async def login(data: LoginData):
    if data.username == "admin" and data.password == "1234":
        return {"message": "Login success"}
    raise HTTPException(status_code=401, detail="Invalid username or password")