import asyncio
import secrets
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

RESERVATION_SECONDS = 30
CLEANUP_INTERVAL_SECONDS = 1


@dataclass
class Product:
    id: int
    name: str
    available: int
    sold: int = 0


@dataclass
class Reservation:
    product_id: int
    amount: int
    expires_at: float


products: Dict[int, Product] = {
    1: Product(id=1, name="Limited Sneakers", available=10),
}
reservations: Dict[str, Reservation] = {}
inventory_lock = asyncio.Lock()


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    quantity: int = Field(gt=0, le=100_000)


class StockAddition(BaseModel):
    product_id: int = Field(gt=0)
    amount: int = Field(gt=0, le=100_000)


class ReservationRequest(BaseModel):
    product_id: int = Field(gt=0)
    amount: int = Field(gt=0, le=1_000)


class Confirmation(BaseModel):
    reservation_token: str = Field(min_length=1, max_length=100)


def release_expired_reservations(now: float) -> None:
    expired_tokens = [
        token
        for token, reservation in reservations.items()
        if now >= reservation.expires_at
    ]
    for token in expired_tokens:
        reservation = reservations.pop(token)
        product = products.get(reservation.product_id)
        if product is not None:
            product.available += reservation.amount


def product_view(product: Product) -> dict:
    reserved = sum(
        reservation.amount
        for reservation in reservations.values()
        if reservation.product_id == product.id
    )
    return {
        "id": product.id,
        "name": product.name,
        "available": product.available,
        "reserved": reserved,
        "sold": product.sold,
    }


async def cleanup_expired_reservations() -> None:
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        async with inventory_lock:
            release_expired_reservations(time.monotonic())


@asynccontextmanager
async def reservation_lifespan(_app) -> AsyncIterator[None]:
    cleanup_task = asyncio.create_task(cleanup_expired_reservations())
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


router = APIRouter(prefix="/reservation", lifespan=reservation_lifespan)


@router.get("/products")
async def list_products() -> List[dict]:
    async with inventory_lock:
        release_expired_reservations(time.monotonic())
        return [product_view(product) for product in products.values()]


@router.post("/products", status_code=201)
async def add_product(data: ProductCreate) -> dict:
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Product name is required")

    async with inventory_lock:
        if any(
            product.name.casefold() == name.casefold()
            for product in products.values()
        ):
            raise HTTPException(status_code=409, detail="Product name already exists")

        product_id = max(products, default=0) + 1
        product = Product(id=product_id, name=name, available=data.quantity)
        products[product_id] = product
        return product_view(product)


@router.post("/products/add-stock")
async def add_stock(data: StockAddition) -> dict:
    async with inventory_lock:
        release_expired_reservations(time.monotonic())
        product = products.get(data.product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")

        product.available += data.amount
        return product_view(product)


@router.post("/reserve", status_code=201)
async def reserve_product(data: ReservationRequest) -> dict:
    async with inventory_lock:
        now = time.monotonic()
        release_expired_reservations(now)

        product = products.get(data.product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")
        if data.amount > product.available:
            raise HTTPException(
                status_code=409,
                detail=f"Not enough stock. Available: {product.available}",
            )

        token = secrets.token_urlsafe(24)
        product.available -= data.amount
        reservations[token] = Reservation(
            product_id=product.id,
            amount=data.amount,
            expires_at=now + RESERVATION_SECONDS,
        )
        return {
            "message": f"Reserved {data.amount} item(s) for {RESERVATION_SECONDS} seconds",
            "reservation_token": token,
            "product_id": product.id,
            "product_name": product.name,
            "amount": data.amount,
            "expires_in": RESERVATION_SECONDS,
            "available": product.available,
        }


@router.post("/confirm")
async def confirm_purchase(data: Confirmation) -> dict:
    async with inventory_lock:
        release_expired_reservations(time.monotonic())
        reservation = reservations.pop(data.reservation_token, None)
        if reservation is None:
            raise HTTPException(
                status_code=409,
                detail="Invalid or expired reservation token",
            )

        product = products.get(reservation.product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")
        product.sold += reservation.amount
        return {
            "message": "Purchase confirmed",
            "product_id": product.id,
            "amount": reservation.amount,
        }


RESERVATION_UI = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Inventory &amp; Quantity Reservation</title>
    <script src="https://cdn.tailwindcss.com"></script>
  </head>
  <body class="min-h-screen bg-slate-100 p-5 text-slate-800 sm:p-8">
    <main class="mx-auto max-w-4xl space-y-5">
      <header class="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 class="text-2xl font-bold text-slate-900">Inventory reservation</h1>
          <p class="mt-1 text-sm text-slate-600">Reservations hold stock for 30 seconds.</p>
        </div>
        <a href="/" class="text-sm font-medium text-indigo-700 hover:underline">Home</a>
      </header>

      <div id="alert" role="status" aria-live="polite" class="hidden rounded-lg border p-3 text-sm"></div>

      <section class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 class="font-semibold">Add product</h2>
        <form id="product-form" class="mt-3 grid gap-3 sm:grid-cols-[1fr_10rem_auto]">
          <input id="new-name" required maxlength="100" placeholder="Product name"
                 class="rounded-lg border border-slate-300 px-3 py-2 text-sm">
          <input id="new-quantity" required type="number" min="1" value="10" aria-label="Initial stock"
                 class="rounded-lg border border-slate-300 px-3 py-2 text-sm">
          <button class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700">Add product</button>
        </form>
      </section>

      <section id="stock-form-wrap" class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 class="font-semibold">Add stock</h2>
        <form id="stock-form" class="mt-3 grid gap-3 sm:grid-cols-[1fr_10rem_auto]">
          <select id="stock-product" required class="rounded-lg border border-slate-300 px-3 py-2 text-sm"></select>
          <input id="stock-amount" required type="number" min="1" value="1" aria-label="Stock amount"
                 class="rounded-lg border border-slate-300 px-3 py-2 text-sm">
          <button class="rounded-lg bg-slate-800 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700">Add stock</button>
        </form>
      </section>

      <section id="active-wrap" class="hidden rounded-2xl border border-amber-200 bg-amber-50 p-5">
        <h2 class="font-semibold text-amber-900">Active reservations</h2>
        <div id="active-list" class="mt-3 space-y-2"></div>
      </section>

      <section>
        <h2 class="mb-3 font-semibold">Products</h2>
        <div id="products" class="grid gap-4 md:grid-cols-2"></div>
      </section>
    </main>

    <script>
      let reservationList = [];
      let productIds = '';

      function escapeHtml(value) {
        const element = document.createElement('span');
        element.textContent = value;
        return element.innerHTML;
      }

      function showAlert(message, type) {
        const element = document.getElementById('alert');
        element.textContent = message;
        element.className = 'rounded-lg border p-3 text-sm ' +
          (type === 'error'
            ? 'border-rose-200 bg-rose-50 text-rose-800'
            : 'border-emerald-200 bg-emerald-50 text-emerald-800');
      }

      async function requestJson(path, options) {
        const response = await fetch('/reservation' + path, options);
        const data = await response.json();
        if (!response.ok) {
          const detail = Array.isArray(data.detail)
            ? data.detail.map(item => item.msg).join(', ')
            : (data.detail || 'Request failed');
          throw new Error(detail);
        }
        return data;
      }

      function renderProductCards(list) {
        const container = document.getElementById('products');
        const ids = list.map(product => product.id).join(',');
        if (ids !== productIds) {
          productIds = ids;
          container.innerHTML = list.length
            ? list.map(product => `
              <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <h3 class="font-semibold text-slate-900">${escapeHtml(product.name)}</h3>
                <div class="my-4 grid grid-cols-3 gap-2 text-center">
                  <div class="rounded-lg bg-slate-50 p-2"><span class="block text-xs text-slate-500">Available</span><strong id="available-${product.id}" class="text-lg">${product.available}</strong></div>
                  <div class="rounded-lg bg-amber-50 p-2"><span class="block text-xs text-slate-500">Reserved</span><strong id="reserved-${product.id}" class="text-lg text-amber-700">${product.reserved}</strong></div>
                  <div class="rounded-lg bg-emerald-50 p-2"><span class="block text-xs text-slate-500">Sold</span><strong id="sold-${product.id}" class="text-lg text-emerald-700">${product.sold}</strong></div>
                </div>
                <form class="flex gap-2" onsubmit="reserveProduct(event, ${product.id})">
                  <input id="amount-${product.id}" type="number" min="1" value="1" aria-label="Quantity to reserve"
                         class="w-24 rounded-lg border border-slate-300 px-3 py-2 text-sm">
                  <button class="flex-1 rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-700">Reserve for 30s</button>
                </form>
              </article>`).join('')
            : '<p class="text-sm text-slate-500">No products yet. Add one above.</p>';

          const select = document.getElementById('stock-product');
          const previousValue = select.value;
          select.innerHTML = list.map(product =>
            `<option value="${product.id}">${escapeHtml(product.name)}</option>`
          ).join('');
          if (list.some(product => String(product.id) === previousValue)) {
            select.value = previousValue;
          }
        }
        list.forEach(product => {
          document.getElementById('available-' + product.id).textContent = product.available;
          document.getElementById('reserved-' + product.id).textContent = product.reserved;
          document.getElementById('sold-' + product.id).textContent = product.sold;
        });
      }

      async function refreshProducts() {
        try {
          renderProductCards(await requestJson('/products'));
        } catch (error) {
          showAlert(error.message, 'error');
        }
      }

      document.getElementById('product-form').addEventListener('submit', async event => {
        event.preventDefault();
        const name = document.getElementById('new-name');
        const quantity = document.getElementById('new-quantity');
        try {
          const product = await requestJson('/products', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name.value.trim(), quantity: Number(quantity.value) })
          });
          name.value = '';
          showAlert('Added ' + product.name + ' with ' + product.available + ' item(s).', 'success');
          await refreshProducts();
        } catch (error) {
          showAlert(error.message, 'error');
        }
      });

      document.getElementById('stock-form').addEventListener('submit', async event => {
        event.preventDefault();
        try {
          await requestJson('/products/add-stock', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              product_id: Number(document.getElementById('stock-product').value),
              amount: Number(document.getElementById('stock-amount').value)
            })
          });
          showAlert('Stock added successfully.', 'success');
          await refreshProducts();
        } catch (error) {
          showAlert(error.message, 'error');
        }
      });

      async function reserveProduct(event, productId) {
        event.preventDefault();
        try {
          const data = await requestJson('/reserve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              product_id: productId,
              amount: Number(document.getElementById('amount-' + productId).value)
            })
          });
          reservationList.push({
            token: data.reservation_token,
            productName: data.product_name,
            amount: data.amount,
            expiresAt: Date.now() + data.expires_in * 1000
          });
          renderReservations();
          showAlert('Reserved. Confirm the purchase before the timer expires.', 'success');
          await refreshProducts();
        } catch (error) {
          showAlert(error.message, 'error');
        }
      }

      async function confirmReservation(token) {
        try {
          const result = await requestJson('/confirm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reservation_token: token })
          });
          reservationList = reservationList.filter(item => item.token !== token);
          renderReservations();
          showAlert('Purchase confirmed for ' + result.amount + ' item(s).', 'success');
          await refreshProducts();
        } catch (error) {
          showAlert(error.message, 'error');
          await refreshProducts();
        }
      }

      function renderReservations() {
        const now = Date.now();
        const expiredCount = reservationList.filter(item => item.expiresAt <= now).length;
        reservationList = reservationList.filter(item => item.expiresAt > now);
        const wrapper = document.getElementById('active-wrap');
        const list = document.getElementById('active-list');
        wrapper.classList.toggle('hidden', reservationList.length === 0);
        list.innerHTML = reservationList.map(item => `
          <div class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-200 bg-white p-3">
            <span class="text-sm font-medium">${escapeHtml(item.productName)} &times; ${item.amount}</span>
            <span id="timer-${item.token}" class="font-mono font-bold text-amber-800"></span>
            <button type="button" onclick="confirmReservation('${item.token}')"
                    class="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-700">Confirm purchase</button>
          </div>`).join('');
        reservationList.forEach(item => {
          const timer = document.getElementById('timer-' + item.token);
          if (timer) {
            timer.textContent = Math.max(0, Math.ceil((item.expiresAt - now) / 1000)) + 's';
          }
        });
        if (expiredCount) {
          showAlert('A reservation expired and its stock has been returned.', 'error');
          refreshProducts();
        }
      }

      refreshProducts();
      setInterval(refreshProducts, 2000);
      setInterval(renderReservations, 250);
    </script>
  </body>
</html>
"""


@router.get("/ui", response_class=HTMLResponse)
async def reservation_ui() -> str:
    return RESERVATION_UI
