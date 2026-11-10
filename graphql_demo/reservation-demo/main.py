import asyncio
import itertools
import time
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

RESERVATION_SECONDS = 30
lock = asyncio.Lock()

# "product table" (in-memory): id -> row
products: dict[int, dict] = {
    1: {"id": 1, "name": "Limited Sneakers", "quantity": 10, "sold": 0},
}
next_id = itertools.count(2)

# token -> {"product_id": int, "amount": int, "expires_at": float}
reservations: dict[str, dict] = {}


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    quantity: int = Field(gt=0, le=100000)


class ReserveRequest(BaseModel):
    product_id: int
    amount: int = Field(gt=0, le=1000)


class Confirmation(BaseModel):
    reservation_token: str = Field(min_length=1, max_length=100)


def release_expired_reservations(now: float):
    """Rollback: return quantity of expired reservations to the product table."""
    expired = [t for t, r in reservations.items() if now >= r["expires_at"]]
    for token in expired:
        r = reservations.pop(token)
        products[r["product_id"]]["quantity"] += r["amount"]


async def cleanup_loop():
    """Background job so rollback happens even if nobody calls the API."""
    while True:
        await asyncio.sleep(1)
        async with lock:
            release_expired_reservations(time.monotonic())


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(cleanup_loop())
    yield
    task.cancel()


app = FastAPI(title="Quantity Reservation", lifespan=lifespan)


def product_view(p: dict) -> dict:
    reserved = sum(
        r["amount"] for r in reservations.values() if r["product_id"] == p["id"]
    )
    return {
        "id": p["id"],
        "name": p["name"],
        "quantity": p["quantity"],
        "reserved": reserved,
        "sold": p["sold"],
    }


@app.get("/products")
async def list_products():
    async with lock:
        release_expired_reservations(time.monotonic())
        return [product_view(p) for p in products.values()]


@app.post("/products", status_code=201)
async def add_product(data: ProductCreate):
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Product name is required")

    async with lock:
        if any(p["name"].lower() == name.lower() for p in products.values()):
            raise HTTPException(status_code=409, detail="Product name already exists")

        pid = next(next_id)
        products[pid] = {"id": pid, "name": name, "quantity": data.quantity, "sold": 0}
        return product_view(products[pid])


@app.post("/reserve", status_code=201)
async def reserve_product(data: ReserveRequest):
    async with lock:
        now = time.monotonic()
        release_expired_reservations(now)

        product = products.get(data.product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")

        if data.amount > product["quantity"]:
            raise HTTPException(
                status_code=409,
                detail=f"Not enough stock. Remaining: {product['quantity']}",
            )

        token = secrets.token_urlsafe(24)
        product["quantity"] -= data.amount  # update product table
        reservations[token] = {
            "product_id": product["id"],
            "amount": data.amount,
            "expires_at": now + RESERVATION_SECONDS,
        }
        return {
            "message": f"Reserved {data.amount} item(s) for {RESERVATION_SECONDS} seconds",
            "reservation_token": token,
            "product_id": product["id"],
            "product_name": product["name"],
            "amount": data.amount,
            "expires_in": RESERVATION_SECONDS,
            "quantity_left": product["quantity"],
        }


@app.post("/confirm")
async def confirm_purchase(data: Confirmation):
    async with lock:
        release_expired_reservations(time.monotonic())

        reservation = reservations.get(data.reservation_token)
        if reservation is None:
            raise HTTPException(
                status_code=409, detail="Invalid or expired reservation token"
            )

        # quantity was already deducted at reserve time, so just finalize
        product = products[reservation["product_id"]]
        product["sold"] += reservation["amount"]
        del reservations[data.reservation_token]
        return {
            "message": "Purchase confirmed",
            "product_id": product["id"],
            "amount": reservation["amount"],
        }


INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Quantity Reservation Demo</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 text-slate-800 min-h-screen p-6">
<div class="max-w-xl mx-auto space-y-4">

    <div class="text-center">
        <h1 class="text-2xl font-bold text-slate-900">Reservation Demo</h1>
        <p class="text-xs text-slate-500 mt-1 uppercase tracking-wider font-medium">Real-time Inventory Reservation System</p>
    </div>

    <!-- Alert -->
    <div id="alert" class="hidden p-3 rounded-lg text-xs font-medium text-center"></div>

    <!-- Add product -->
    <div class="bg-white rounded-2xl p-4 shadow-sm border border-gray-200">
        <h2 class="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-3">Add Product</h2>
        <div class="flex gap-2">
            <input id="new-name" type="text" placeholder="Product name" maxlength="100"
                   class="flex-1 min-w-0 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-600">
            <input id="new-qty" type="number" value="10" min="1"
                   class="w-24 border border-gray-300 rounded-lg px-2 py-2 text-sm text-center focus:outline-none focus:border-indigo-600">
            <button onclick="handleAddProduct()"
                    class="bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm px-4 rounded-lg transition active:scale-95">
                Add
            </button>
        </div>
    </div>

    <!-- Active reservations -->
    <div id="active-wrap" class="hidden bg-amber-50/70 border border-amber-200 p-4 rounded-2xl">
        <h2 class="text-xs font-semibold text-amber-800 uppercase tracking-wider mb-3">Active Reservations</h2>
        <div id="active-list" class="space-y-2"></div>
    </div>

    <!-- Product list -->
    <div id="products" class="space-y-4"></div>
</div>

<script>
    let reservationList = [];  // {token, productName, amount, expiresAt}

    function esc(s) {
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    function showAlert(msg, type) {
        const el = document.getElementById('alert');
        if (type === 'clear') { el.className = 'hidden'; return; }
        el.innerText = msg;
        el.className = 'p-3 rounded-lg text-xs font-medium text-center border ' +
            (type === 'error'
                ? 'bg-rose-50 text-rose-700 border-rose-200'
                : 'bg-emerald-50 text-emerald-700 border-emerald-200');
    }

    function errorMessage(data, fallback) {
        if (!data || !data.detail) return fallback;
        if (Array.isArray(data.detail)) return data.detail.map(d => d.msg).join(', ');
        return data.detail;
    }

    async function fetchProducts() {
        try {
            const res = await fetch('/products');
            const list = await res.json();
            const box = document.getElementById('products');
            const ids = list.map(p => p.id).join(',');

            // re-render cards only when the set of products changes (keeps typed amounts)
            if (box.dataset.ids !== ids) {
                box.dataset.ids = ids;
                if (list.length === 0) {
                    box.innerHTML = '<p class="text-center text-sm text-slate-500">No products yet. Add one above.</p>';
                } else {
                    box.innerHTML = list.map(p => `
                        <div class="bg-white rounded-2xl p-4 shadow-sm border border-gray-200">
                            <h3 class="text-lg font-bold text-slate-900 mb-3">${esc(p.name)}</h3>
                            <div class="grid grid-cols-3 gap-3 mb-4 text-center">
                                <div class="bg-slate-50 p-2 rounded-xl border border-gray-100">
                                    <span class="block text-xs text-slate-500">Available</span>
                                    <span id="stock-${p.id}" class="text-xl font-bold">0</span>
                                </div>
                                <div class="bg-slate-50 p-2 rounded-xl border border-gray-100">
                                    <span class="block text-xs text-slate-500">Reserved</span>
                                    <span id="reserved-${p.id}" class="text-xl font-bold text-amber-600">0</span>
                                </div>
                                <div class="bg-slate-50 p-2 rounded-xl border border-gray-100">
                                    <span class="block text-xs text-slate-500">Sold</span>
                                    <span id="sold-${p.id}" class="text-xl font-bold text-emerald-600">0</span>
                                </div>
                            </div>
                            <div class="flex gap-2">
                                <input id="amt-${p.id}" type="number" value="1" min="1"
                                       class="w-20 border border-gray-300 text-center rounded-lg px-2 py-2 text-sm font-semibold focus:outline-none focus:border-indigo-600">
                                <button onclick="handleReserve(${p.id})"
                                        class="flex-1 bg-slate-900 hover:bg-slate-800 text-white font-medium text-sm py-2 px-4 rounded-lg transition active:scale-95">
                                    Reserve (30s Hold)
                                </button>
                            </div>
                        </div>`).join('');
                }
            }

            list.forEach(p => {
                document.getElementById('stock-' + p.id).innerText = p.quantity;
                document.getElementById('reserved-' + p.id).innerText = p.reserved;
                document.getElementById('sold-' + p.id).innerText = p.sold;
            });
        } catch (err) {
            console.error('Fetch error:', err);
        }
    }

    async function handleAddProduct() {
        const nameEl = document.getElementById('new-name');
        const qtyEl = document.getElementById('new-qty');
        showAlert('', 'clear');
        try {
            const res = await fetch('/products', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ name: nameEl.value.trim(), quantity: parseInt(qtyEl.value) })
            });
            const data = await res.json();
            if (!res.ok) {
                showAlert(errorMessage(data, 'Failed to add product'), 'error');
                return;
            }
            nameEl.value = '';
            showAlert('Added "' + data.name + '" with ' + data.quantity + ' item(s).', 'success');
            fetchProducts();
        } catch (err) {
            showAlert('Connection error', 'error');
        }
    }

    async function handleReserve(productId) {
        const amount = parseInt(document.getElementById('amt-' + productId).value);
        showAlert('', 'clear');
        try {
            const res = await fetch('/reserve', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ product_id: productId, amount: amount })
            });
            const data = await res.json();
            if (!res.ok) {
                showAlert(errorMessage(data, 'Failed to reserve item'), 'error');
                return;
            }
            reservationList.push({
                token: data.reservation_token,
                productName: data.product_name,
                amount: data.amount,
                expiresAt: Date.now() + data.expires_in * 1000
            });
            renderReservations(true);
            showAlert('Reserved. Confirm before the timer expires.', 'success');
            fetchProducts();
        } catch (err) {
            showAlert('Connection error', 'error');
        }
    }

    async function handleConfirm(token) {
        try {
            const res = await fetch('/confirm', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ reservation_token: token })
            });
            const data = await res.json();
            showAlert(res.ok ? 'Purchase confirmed successfully.' : errorMessage(data, 'Confirmation failed'),
                      res.ok ? 'success' : 'error');
            reservationList = reservationList.filter(r => r.token !== token);
            renderReservations(true);
            fetchProducts();
        } catch (err) {
            showAlert('Confirmation error', 'error');
        }
    }

    function renderReservations(force) {
        const now = Date.now();
        const before = reservationList.length;
        reservationList = reservationList.filter(r => r.expiresAt > now);
        const expiredSome = reservationList.length !== before;
        if (expiredSome) {
            showAlert('A reservation expired. Items returned to available stock.', 'error');
            fetchProducts();
        }

        const wrap = document.getElementById('active-wrap');
        const list = document.getElementById('active-list');
        wrap.classList.toggle('hidden', reservationList.length === 0);

        if (force || expiredSome) {
            list.innerHTML = reservationList.map(r => `
                <div class="bg-white border border-amber-200 rounded-xl p-3">
                    <div class="flex justify-between items-center mb-2">
                        <span class="text-sm font-semibold text-slate-900">${esc(r.productName)} x ${r.amount}</span>
                        <span id="timer-${r.token}" class="font-mono font-bold text-amber-900"></span>
                    </div>
                    <button onclick="handleConfirm('${r.token}')"
                            class="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-sm py-2 rounded-lg transition active:scale-95">
                        Confirm Purchase
                    </button>
                </div>`).join('');
        }
        reservationList.forEach(r => {
            const t = document.getElementById('timer-' + r.token);
            if (t) t.innerText = Math.max(0, Math.ceil((r.expiresAt - now) / 1000)) + 's';
        });
    }

    setInterval(fetchProducts, 1000);
    setInterval(() => renderReservations(false), 500);
    fetchProducts();
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML