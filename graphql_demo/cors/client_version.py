import asyncio
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse

app = FastAPI()

PAGE = """<!doctype html>
<meta charset="utf-8">
<button onclick="streamed()">Stream</button>
<button onclick="allAtOnce()">All at once</button>
<pre id="out"></pre>
<script>
const out = document.getElementById("out");

async function streamed() {
  out.textContent = "";
  const res = await fetch("/live-stream");
  const reader = res.body.getReader();   // read the body piece by piece
  const decoder = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    out.textContent += decoder.decode(value);  // show each piece right away
  }
}

async function allAtOnce() {
  out.textContent = "waiting...";
  const res = await fetch("/live-stream");
  out.textContent = await res.text();    // waits for the WHOLE body
}
</script>
"""


@app.get("/", response_class=HTMLResponse)
def page():
    return PAGE


@app.get("/live-stream")
async def live_stream():
    async def generate():
        try:
            for i in range(1, 11):
                await asyncio.sleep(1)
                print(f"sent row {i}")
                yield f"row {i}\n"
        finally:
            print("cleanup ran")  # runs even if the client leaves halfway

    return StreamingResponse(generate(), media_type="text/plain")