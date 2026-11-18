# Homework: Cookie

เปลี่ยนระบบ login ของโปรเจค Product Management จาก "เก็บ JWT ไว้ใน localStorage" มาเป็น **เก็บ JWT ไว้ใน Cookie แบบ httponly**
พร้อมหน้าแสดง cookie ที่ browser เก็บไว้ และทดสอบ CORS

## Cookie ที่ backend ตั้งให้ตอน login (`POST /login`)

| Cookie | httponly | JavaScript อ่านได้ไหม | ใช้ทำอะไร |
|---|---|---|---|
| `access_token` | ✅ | ❌ อ่านไม่ได้ | เก็บ JWT ไว้ยืนยันตัวตน browser ส่งไปให้ backend เองทุก request |
| `username` | ❌ | ✅ อ่านได้ | เอาไว้แสดงชื่อบนหน้าเว็บ (ไม่ใช่ข้อมูลลับ) |

ตั้งค่า: `samesite="lax"`, `max_age=1800` (30 นาที เท่ากับอายุของ JWT), `path="/"`

## ทำไมต้อง httponly
- ถ้าเก็บ token ใน `localStorage` → ถ้าเว็บโดน XSS (มีคนแอบใส่ JavaScript อันตราย) สคริปต์นั้นอ่าน token ไปได้ทันที
- ถ้าเก็บใน cookie แบบ `httponly` → JavaScript **อ่านไม่ได้เลย** (`document.cookie` จะไม่เห็น) แต่ browser ยังส่ง cookie ไปให้ backend อัตโนมัติ
- backend จึงไม่ส่ง token กลับใน body แล้ว ส่งแค่ `{"message": ..., "username": ...}`

## สิ่งที่เปลี่ยนในโค้ด

**Backend**
- `product_app/jwt/auth.py`
  - `/login` → `response.set_cookie(...)` 2 อัน
  - `get_token()` → อ่าน token จาก `Cookie(access_token)` (ถ้าไม่มีค่อยดู header `Authorization: Bearer` สำหรับ curl/Postman)
  - `GET /me` → หน้าเว็บใช้ถามว่า "ยัง login อยู่ไหม" หลังกด refresh
  - `/logout` → ใส่ token ใน blacklist + `response.delete_cookie(...)`
- `product_app/cookie_demo.py`
  - `GET /cookies` → ส่งกลับว่า backend ได้รับ cookie อะไรบ้าง (ได้รับ httponly ด้วย เพราะ httponly กันแค่ JavaScript)
  - `GET /foo`, `HEAD /foo` → ใช้ทดสอบ CORS
- `product_app/main.py` → CORS `allow_credentials=True` (ให้ส่ง cookie ข้าม origin ได้), `allow_methods` ทุกอันยกเว้น `HEAD`, `max_age=0`

**Frontend** (`product_app/my-app/app/page.tsx`)
- ทุก request ใช้ `credentials: "include"` → browser แนบ cookie ไปด้วย
- ไม่ใช้ `localStorage` และไม่ใส่ header `Authorization` เองแล้ว
- เปิดหน้าเว็บ/refresh → เรียก `/me` ถ้า cookie ยังอยู่ก็ login ค้างไว้ให้
- BASE_URL เปลี่ยนเป็น `http://localhost:8000` (จาก 127.0.0.1) เพื่อให้ frontend (localhost:3000) กับ backend เป็น **site เดียวกัน** ไม่งั้น cookie `SameSite=Lax` จะไม่ถูกส่ง

## กล่อง 🍪 Cookies the browser is storing
- คอลัมน์ Value = ค่าที่ **backend ได้รับจริง** (จาก `GET /cookies`)
- คอลัมน์ "Can JavaScript read it?" = เช็กว่าชื่อ cookie นั้นอยู่ใน `document.cookie` ไหม
- `access_token` จะขึ้น ❌ (httponly) ส่วน `username` จะขึ้น ✅

## กล่อง 🚫 CORS test
- backend อนุญาตทุก method **ยกเว้น HEAD**
- ปุ่มส่ง header พิเศษ `X-Demo` → browser ต้องส่ง **preflight** (`OPTIONS`) ไปถามก่อน
- `GET /foo` → preflight ผ่าน → ได้ 200
- `HEAD /foo` → preflight ได้ 400 "Disallowed CORS method" → **browser บล็อก** (ดู error ใน DevTools → Console)
- จุดสำคัญ: endpoint `/foo` ฝั่ง server รองรับ HEAD ได้ปกติ (ลอง `curl -I http://localhost:8000/foo` ได้ 200) คนที่บล็อกคือ **browser** ตามกติกา CORS
- `max_age=0` = ห้าม browser จำผล preflight ไว้ ไม่งั้นพอกด GET ผ่านแล้ว browser จะเอาผลนั้นมาใช้กับ HEAD ด้วย (เพราะ HEAD เป็น "simple method") ทำให้ HEAD ไม่ถูกบล็อก

## วิธีโชว์ให้อาจารย์ดู
1. เปิด http://localhost:3000 (**ต้องเป็น localhost ไม่ใช่ 127.0.0.1**) → login
2. กล่อง Cookie → ชี้ให้ดูว่า `access_token` JavaScript อ่านไม่ได้ แต่ backend ได้รับ
3. เปิด DevTools → Console พิมพ์ `document.cookie` → จะเห็นแค่ `username=...` ไม่มี token
4. DevTools → Application (Chrome) / Storage (Safari) → Cookies → เห็นช่อง HttpOnly ติ๊กอยู่ที่ `access_token`
5. กด refresh หน้าเว็บ → ยัง login อยู่ (เพราะ cookie อยู่ใน browser)
6. เพิ่ม/แก้สินค้าได้ปกติ → แปลว่า backend ยืนยันตัวตนจาก cookie
7. กด Logout → cookie หายจากตาราง
8. กด `Call GET /foo` (ผ่าน) แล้ว `Call HEAD /foo` (โดนบล็อก) → โชว์ error CORS ใน Console

## ทดสอบด้วย curl
```bash
curl -c cookies.txt -X POST http://localhost:8000/login -d "username=USER&password=PASS"
```
```bash
cat cookies.txt
```
(บรรทัดที่ขึ้นต้นด้วย `#HttpOnly_` คือ cookie แบบ httponly)
```bash
curl -b cookies.txt http://localhost:8000/me
```
