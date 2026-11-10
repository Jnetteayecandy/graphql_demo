import asyncio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

@app.get("/")
def hello():
    return {"message": "Hello, World!"}

@app.get("/normal")
async def normal():
    lines = []
    for i in range(1, 6):
        lines.append(f"Line {i}\n")
        await asyncio.sleep(1)
        lines.append(f"Line {i} after sleep\n")
    return {"data": lines}

@app.get("/stream")
async def stream():
    async def generate():
        for i in range(1, 6):
            yield f"Line {i}\n"
            await asyncio.sleep(1)
            yield f"Line {i} after sleep\n"
    return StreamingResponse(generate(), media_type="text/plain")

# ข้อความตัวอย่างสำหรับทดสอบ Chat Streaming
SENTENCE = "Hello! This is a simulated real-time streaming response from FastAPI."

@app.get("/chat")
async def chat():
    async def generate():
        for word in SENTENCE.split():
            yield word + " "
            await asyncio.sleep(0.5)
    return StreamingResponse(generate(), media_type="text/plain")

@app.get("/progress")
async def progress():
    async def generate():
        for percent in range(1, 101):
            yield f"data: {percent}%\n\n"
            await asyncio.sleep(0.1)  # ปรับเวลาให้รันเสร็จใน 10 วินาที
        yield "data: done\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")