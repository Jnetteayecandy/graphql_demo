# Homework: Streaming (ส่ง 11 พ.ย.)

เพิ่มฟีเจอร์ **Streaming** เข้าไปในโปรเจค Product Management (FastAPI + SQLAlchemy + JWT + Next.js)
โค้ดหลักอยู่ที่ `product_app/streaming.py` และเชื่อมเข้ากับ `product_app/main.py`

## ไอเดีย
ร้านค้ามีหลายคนช่วยกันจัดการสินค้า → เมื่อมีคนเพิ่ม/แก้/ลบสินค้า หน้าเว็บของทุกคนต้องอัปเดตทันทีโดยไม่ต้องกด refresh
และสามารถ export สินค้าทั้งหมดเป็นไฟล์ CSV ได้แม้จะมีข้อมูลเยอะมาก

## Endpoints ที่เพิ่ม

| Method | Path | ประเภท Streaming | อธิบาย |
|---|---|---|---|
| GET | `/stream/events` | Server-Sent Events (`text/event-stream`) | Live feed: แจ้งทุก client เมื่อมีการ create/update/delete สินค้าหรือหมวดหมู่ |
| GET | `/stream/products?delay=0.5` | NDJSON (`application/x-ndjson`) | ส่งสินค้าทีละชิ้น (async generator) หน้าเว็บแสดงผลทีละรายการพร้อม progress bar |
| GET | `/stream/products/export.csv` | `StreamingResponse` (sync generator) | ดาวน์โหลด CSV ทีละแถว ไม่ต้องโหลดข้อมูลทั้งหมดไว้ใน memory (`yield_per`) |

## เชื่อมกับหัวข้อที่เรียนมาแล้ว
- **CRUD + SQLAlchemy + Many-to-Many**: ข้อมูลที่ stream มาจาก DB เดิม (products / categories)
- **JWT Auth**: เฉพาะคนที่ login แล้วถึงแก้ข้อมูลได้ และชื่อผู้ใช้จาก token จะโชว์ใน live feed เช่น `alice created product "iPhone"`
- **CORS**: frontend Next.js (`localhost:3000`) เรียก stream ได้ผ่าน CORS middleware เดิม
- **Async / Pydantic**: ใช้ `async def`, `asyncio.Queue`, async generator

## หลักการทำงานของ SSE
```
[User A] PUT /products/1 (JWT) ──► main.py ──► broker.publish("product_updated", ...)
                                                     │
                     ┌───────────────────────────────┼──────────────────────┐
                     ▼                               ▼                      ▼
             queue ของ client 1              queue ของ client 2       queue ของ client 3
                     │                               │                      │
         GET /stream/events (EventSource)  ...   ...  ◄── yield "event: ...\ndata: {...}\n\n"
```
- ทุก client ที่เปิด `/stream/events` จะได้ `asyncio.Queue` ของตัวเอง
- ถ้าไม่มี event 15 วินาที server ส่ง `: ping` (heartbeat) เพื่อไม่ให้ connection หลุด
- เมื่อ client ปิดหน้า → `request.is_disconnected()` → ลบ queue ออก

## วิธีรัน
```bash
# จากโฟลเดอร์ root ของ repo
uvicorn product_app.main:app --reload
```
```bash
cd product_app/my-app
pnpm install
pnpm dev
```
เปิด http://localhost:3000 **สองแท็บ** → login → แก้ไขสินค้าในแท็บหนึ่ง แล้วดูอีกแท็บอัปเดตเองในกล่อง *Live Activity*

## ทดสอบด้วย curl
```bash
curl -N http://127.0.0.1:8000/stream/events
```
```bash
curl -N "http://127.0.0.1:8000/stream/products?delay=1"
```
```bash
curl -o products.csv http://127.0.0.1:8000/stream/products/export.csv
```
(`-N` = ปิด buffer ของ curl เพื่อให้เห็นข้อมูลทีละก้อน)
