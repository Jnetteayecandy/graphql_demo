"""
Streaming (Week: Streaming)
===========================

This router adds three kinds of streaming to the product project:

1. GET /stream/products/export.csv
   -> StreamingResponse that sends a CSV file one row at a time
      (the file is never fully loaded into memory).

2. GET /stream/products
   -> NDJSON (newline-delimited JSON) stream. Products are sent one by one
      with a small delay so the client can render them as they arrive.

3. GET /stream/events
   -> Server-Sent Events (SSE). A live activity feed: every time someone
      creates / updates / deletes a product or category (protected by JWT),
      all connected browsers receive the event in real time.
"""

import asyncio
import csv
import io
import json
from datetime import datetime, timezone
from typing import AsyncIterator, Iterator

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .database import get_db
from .models import ProductDB

router = APIRouter(prefix="/stream", tags=["streaming"])


# ---------------------------------------------------------------------------
# Event broker (publish / subscribe) used by the SSE endpoint
# ---------------------------------------------------------------------------
class EventBroker:
    """Keeps one asyncio.Queue per connected client."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    @property
    def client_count(self) -> int:
        return len(self._subscribers)

    def publish(self, event_type: str, data: dict) -> None:
        """Send an event to every connected client (called from async endpoints)."""
        message = {
            "type": event_type,
            "data": data,
            "time": datetime.now(timezone.utc).isoformat(),
        }
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                # Slow client: drop the event instead of blocking everyone else
                pass


broker = EventBroker()


def product_to_dict(product: ProductDB) -> dict:
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "price": product.price,
        "categories": [{"id": c.id, "name": c.name} for c in product.categories],
    }


# ---------------------------------------------------------------------------
# 1) CSV export - StreamingResponse with a normal (sync) generator
# ---------------------------------------------------------------------------
@router.get("/products/export.csv")
def export_products_csv(db: Session = Depends(get_db)):
    def generate_csv() -> Iterator[str]:
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        def flush() -> str:
            value = buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
            return value

        writer.writerow(["id", "name", "description", "price", "categories"])
        yield flush()

        # yield_per -> SQLAlchemy fetches rows in batches instead of all at once
        for product in db.query(ProductDB).order_by(ProductDB.id).yield_per(50):
            writer.writerow([
                product.id,
                product.name,
                product.description,
                product.price,
                "|".join(c.name for c in product.categories),
            ])
            yield flush()

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="products.csv"'},
    )


# ---------------------------------------------------------------------------
# 2) NDJSON stream - StreamingResponse with an async generator
# ---------------------------------------------------------------------------
@router.get("/products")
async def stream_products(
    delay: float = Query(0.5, ge=0, le=5, description="Seconds between each product"),
    db: Session = Depends(get_db),
):
    products = [product_to_dict(p) for p in db.query(ProductDB).order_by(ProductDB.id).all()]

    async def generate() -> AsyncIterator[str]:
        yield json.dumps({"type": "start", "total": len(products)}) + "\n"
        for index, product in enumerate(products, start=1):
            await asyncio.sleep(delay)  # simulate slow work (e.g. heavy query / AI)
            yield json.dumps({"type": "product", "index": index, "product": product}) + "\n"
        yield json.dumps({"type": "end"}) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


# ---------------------------------------------------------------------------
# 3) Server-Sent Events - live activity feed
# ---------------------------------------------------------------------------
def sse_format(event_type: str, data: dict) -> str:
    """SSE wire format:  event: <type>\\ndata: <json>\\n\\n"""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


@router.get("/events")
async def stream_events(request: Request):
    queue = broker.subscribe()

    async def event_generator() -> AsyncIterator[str]:
        try:
            yield sse_format("connected", {
                "message": "Connected to live product feed",
                "clients": broker.client_count,
            })
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=15)
                    yield sse_format(message["type"], message)
                except asyncio.TimeoutError:
                    # Comment line = heartbeat, keeps the connection alive
                    yield ": ping\n\n"
        finally:
            broker.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
