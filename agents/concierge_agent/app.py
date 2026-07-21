"""
FastAPI entrypoint for the concierge agent.

Endpoints:
  GET  /health           - liveness
  POST /invocations      - Server-Sent Events stream of the agent response
      body: { "prompt": str, "user_id": str, "session_id": str }
"""

import json
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from concierge import Concierge
from config import config
from mcp_direct import call_mcp_tool

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("agent-app")

concierge = Concierge()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await concierge.start()
    yield
    await concierge.stop()


app = FastAPI(title="Travel Concierge Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "model": config.MODEL_DEPLOYMENT, "vic": config.ENABLE_VIC}


# --- UI support endpoints (call MCP/Cosmos directly, no LLM) -----------------
@app.get("/api/cart/{user_id}")
async def get_cart(user_id: str):
    return await call_mcp_tool(config.CART_MCP_URL, "cart_view_cart", {"user_id": user_id})


@app.get("/api/itinerary/{user_id}")
async def get_itinerary(user_id: str):
    items = await concierge.cosmos.get_itinerary(user_id) if concierge.cosmos else []
    return {"user_id": user_id, "items": items}


@app.delete("/api/itinerary/{user_id}")
async def clear_itinerary(user_id: str):
    removed = await concierge.cosmos.clear_itinerary(user_id) if concierge.cosmos else 0
    return {"user_id": user_id, "removed": removed}


@app.get("/api/vic/iframe-config/{user_id}")
async def vic_iframe_config(user_id: str):
    if not config.ENABLE_VIC:
        return {"enabled": False}
    return await call_mcp_tool(config.CART_MCP_URL, "cart_get_vic_iframe_config", {"user_id": user_id})


@app.post("/api/vic/onboard-card")
async def vic_onboard_card(request: Request):
    """Card data goes straight to the (mock) tokenization tool — never to the model."""
    if not config.ENABLE_VIC:
        return {"success": False, "error": "VIC integration disabled"}
    body = await request.json()
    required = ("user_id", "card_number", "expiration_date")
    if not all(body.get(k) for k in required):
        return {"success": False, "error": f"Missing one of {required}"}
    return await call_mcp_tool(
        config.CART_MCP_URL,
        "cart_onboard_card",
        {
            "user_id": body["user_id"],
            "card_number": body["card_number"],
            "expiration_date": body["expiration_date"],
            "cvv": body.get("cvv", ""),
            "cardholder_name": body.get("cardholder_name", ""),
        },
    )


@app.post("/invocations")
async def invocations(request: Request):
    payload = await request.json()
    prompt = payload.get("prompt")
    user_id = payload.get("user_id")
    session_id = payload.get("session_id")

    if not all([prompt, user_id, session_id]):
        return {"error": "Missing required fields: prompt, user_id, session_id"}

    async def event_stream():
        try:
            async for chunk in concierge.stream(prompt, user_id, session_id):
                yield f"data: {json.dumps({'delta': chunk})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as exc:  # pragma: no cover
            logger.exception("stream error")
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=config.PORT)
