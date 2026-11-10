from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

app = FastAPI(title="CORS Homework - GET Allowed / HEAD Blocked")

# 1. ตั้งค่า CORS: ไม่อนุญาต "HEAD"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"], # ตัด "HEAD" ออก
    allow_headers=["*"],
)

@app.get("/foo")
def get_foo():
    return {"message": "GET /foo OK"}

@app.head("/foo")
def head_foo():
    return Response(status_code=200)

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="th">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>CORS: GET ผ่าน · HEAD ถูกบล็อก</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-100 text-slate-800 min-h-screen p-6 flex flex-col items-center justify-center font-sans">
        <div class="max-w-xl w-full bg-white rounded-2xl p-8 shadow-md border border-slate-200 space-y-6">
            
            <div>
                <h1 class="text-2xl font-bold text-slate-900 mb-2">CORS: GET ผ่าน · HEAD ถูกบล็อก</h1>
                <p class="text-sm text-slate-600">
                    หน้าเว็บเรียก FastAPI ที่ <code class="bg-slate-100 text-amber-600 font-mono px-2 py-0.5 rounded border border-slate-200">http://localhost:8098/foo</code> จาก browser
                </p>
                <p class="text-xs text-slate-500 mt-1">
                    กด GET ก่อนเพื่อยืนยันว่า API เปิดอยู่ แล้วกด HEAD เพื่อแสดง CORS error
                </p>
            </div>

            <div class="flex gap-4">
                <button onclick="testGET()" 
                        class="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-sm py-2.5 px-4 rounded-lg transition active:scale-95 shadow-sm">
                    ทดสอบ GET (อนุญาต)
                </button>
                <button onclick="testHEAD()" 
                        class="flex-1 bg-rose-600 hover:bg-rose-700 text-white font-medium text-sm py-2.5 px-4 rounded-lg transition active:scale-95 shadow-sm">
                    ทดสอบ HEAD (บล็อก CORS)
                </button>
            </div>

            <div id="result-box" class="hidden rounded-xl p-5 border space-y-3 transition-all">
                <h3 id="result-title" class="font-bold text-base"></h3>
                <p id="result-error" class="font-mono text-xs font-semibold"></p>
                <p id="result-desc" class="text-xs text-slate-600 leading-relaxed"></p>
                <p id="result-note" class="text-xs text-slate-500 italic pt-2 border-t border-slate-200"></p>
            </div>

        </div>

        <script>
            // เปลี่ยนจาก 127.0.0.1 เป็น localhost เพื่อบังคับให้เกิด Cross-Origin Request
            const API_URL = 'http://localhost:8098/foo';
            
            const box = document.getElementById('result-box');
            const title = document.getElementById('result-title');
            const error = document.getElementById('result-error');
            const desc = document.getElementById('result-desc');
            const note = document.getElementById('result-note');

            async function testGET() {
                try {
                    const res = await fetch(API_URL, { method: 'GET' });
                    if (res.ok) {
                        box.className = "block bg-emerald-50 border-emerald-200 rounded-xl p-5 space-y-2";
                        title.className = "font-bold text-base text-emerald-800";
                        title.innerText = "GET เรียกสำเร็จ (200 OK)";
                        error.innerText = "";
                        desc.innerText = "API อนุญาต HTTP Method GET ตามปกติ เบราว์เซอร์จึงรับข้อมูลสำเร็จ";
                        note.innerText = "";
                    }
                } catch (err) {
                    box.className = "block bg-rose-50 border-rose-200 rounded-xl p-5 space-y-2";
                    title.className = "font-bold text-base text-rose-800";
                    title.innerText = "GET เรียกไม่สำเร็จ";
                    error.innerText = err.name + ": " + err.message;
                    desc.innerText = "ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้ ตรวจสอบว่าเปิด uvicorn หรือยัง";
                    note.innerText = "";
                }
            }

            async function testHEAD() {
                try {
                    const res = await fetch(API_URL, { 
                        method: 'HEAD',
                        headers: { 'X-CORS-Test': 'trigger-preflight' }
                    });
                    
                    if (res.ok) {
                        box.className = "block bg-emerald-50 border-emerald-200 rounded-xl p-5 space-y-2";
                        title.className = "font-bold text-base text-emerald-800";
                        title.innerText = "HEAD เรียกสำเร็จ";
                        error.innerText = "";
                        desc.innerText = "HEAD ได้รับการอนุญาต";
                        note.innerText = "";
                    }
                } catch (err) {
                    box.className = "block bg-rose-50 border-rose-200 rounded-xl p-5 space-y-3";
                    title.className = "font-bold text-base text-rose-800";
                    title.innerText = "HEAD เรียกไม่สำเร็จ";
                    error.className = "font-mono text-xs text-rose-700 bg-rose-100 p-2.5 rounded-lg border border-rose-200";
                    error.innerText = err.name + ": " + err.message;
                    
                    desc.innerText = "ในการทดลองนี้ API ไม่ส่ง CORS headers สำหรับ HEAD จึงถูก browser บล็อก ดูเหตุผลจาก browser เพิ่มเติมใน DevTools -> Console / Network (fetch ไม่เปิดเผยสาเหตุ CORS ให้ JavaScript)";
                    note.innerText = "HEAD อาจได้ HTTP 200 ที่เซิร์ฟเวอร์ แต่ browser ไม่อนุญาตให้หน้าเว็บอ่าน response ข้าม origin ได้";
                }
            }
        </script>
    </body>
    </html>
    """