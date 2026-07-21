"""
FastAPI entrypoint for the concierge agent.

Endpoints:
  GET    /health                                   - liveness
  POST   /invocations                              - SSE stream of the agent response
         body: { "prompt": str, "user_id": str, "itinerary_id": str }
  GET    /api/itineraries/{user_id}                - list the user's itineraries
  POST   /api/itineraries/{user_id}                - create a named itinerary  { "name": str }
  GET    /api/itinerary/{user_id}/{itinerary_id}   - itinerary items
  PATCH  /api/itinerary/{user_id}/{itinerary_id}   - rename                    { "name": str }
  DELETE /api/itinerary/{user_id}/{itinerary_id}   - delete (+ its chat history)
  GET    /api/cart/{user_id}                       - cart contents
  GET    /api/vic/iframe-config/{user_id}          - VIC iframe config
  POST   /api/vic/onboard-card                     - secure card onboarding
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


# --- Itinerary management (call Cosmos directly, no LLM) ---------------------
@app.get("/api/itineraries/{user_id}")
async def list_itineraries(user_id: str):
    items = await concierge.cosmos.list_itineraries(user_id) if concierge.cosmos else []
    return {"user_id": user_id, "itineraries": items}


@app.post("/api/itineraries/{user_id}")
async def create_itinerary(user_id: str, request: Request):
    body = await request.json()
    name = (body.get("name") or "Untitled itinerary").strip()
    itinerary = await concierge.cosmos.create_itinerary(user_id, name) if concierge.cosmos else None
    return {"user_id": user_id, "itinerary": itinerary}


@app.get("/api/itinerary/{user_id}/{itinerary_id}")
async def get_itinerary(user_id: str, itinerary_id: str):
    doc = await concierge.cosmos.get_itinerary(user_id, itinerary_id) if concierge.cosmos else None
    return {
        "user_id": user_id,
        "itinerary_id": itinerary_id,
        "name": doc.get("name") if doc else None,
        "items": doc.get("items", []) if doc else [],
    }


@app.patch("/api/itinerary/{user_id}/{itinerary_id}")
async def rename_itinerary(user_id: str, itinerary_id: str, request: Request):
    body = await request.json()
    name = (body.get("name") or "").strip()
    ok = await concierge.cosmos.rename_itinerary(user_id, itinerary_id, name) if concierge.cosmos else False
    return {"user_id": user_id, "itinerary_id": itinerary_id, "renamed": ok}


@app.delete("/api/itinerary/{user_id}/{itinerary_id}")
async def delete_itinerary(user_id: str, itinerary_id: str):
    ok = await concierge.cosmos.delete_itinerary(user_id, itinerary_id) if concierge.cosmos else False
    if ok:
        await concierge.clear_history(user_id, itinerary_id)
    return {"user_id": user_id, "itinerary_id": itinerary_id, "deleted": ok}


# --- UI support endpoints (call MCP/Cosmos directly, no LLM) -----------------
@app.get("/api/cart/{user_id}")
async def get_cart(user_id: str):
    return await call_mcp_tool(config.CART_MCP_URL, "cart_view_cart", {"user_id": user_id})


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
    # itinerary_id scopes the conversation thread + memory; accept legacy session_id.
    itinerary_id = payload.get("itinerary_id") or payload.get("session_id")

    if not all([prompt, user_id, itinerary_id]):
        return {"error": "Missing required fields: prompt, user_id, itinerary_id"}

    async def event_stream():
        try:
            async for chunk in concierge.stream(prompt, user_id, itinerary_id):
                yield f"data: {json.dumps({'delta': chunk})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as exc:  # pragma: no cover
            logger.exception("stream error")
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=config.PORT)
