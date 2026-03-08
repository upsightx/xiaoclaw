"""xiaoclaw API Server — lightweight FastAPI-based HTTP interface"""
import os
import logging

logger = logging.getLogger("xiaoclaw.API")

try:
    from fastapi import FastAPI, HTTPException, Depends, Security
    from fastapi.security import APIKeyHeader
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# API Key authentication
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False) if HAS_FASTAPI else None

def get_api_key(api_key: str = Depends(API_KEY_HEADER) if API_KEY_HEADER else None) -> str:
    """Validate API key from header. Returns the key if valid, raises 401 if invalid."""
    expected_key = os.getenv("XIAOCLAW_API_KEY", "")
    # If no API key configured, deny all requests for security
    if not expected_key:
        logger.error("XIAOCLAW_API_KEY not configured - rejecting all API requests")
        raise HTTPException(status_code=401, detail="API key not configured on server")
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    if api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


def create_app(claw=None):
    """Create FastAPI app wrapping a XiaClaw instance."""
    if not HAS_FASTAPI:
        raise RuntimeError("FastAPI not installed. pip install fastapi uvicorn")

    from .core import XiaClaw, XiaClawConfig, VERSION

    if claw is None:
        claw = XiaClaw(XiaClawConfig.from_env())

    app = FastAPI(title="xiaoclaw", version=VERSION)

    class ChatRequest(BaseModel):
        message: str
        user_id: str = "default"
        stream: bool = False

    class ChatResponse(BaseModel):
        response: str
        session_id: str

    @app.get("/healthz")
    async def healthz():
        """Health check endpoint - no auth required for monitoring."""
        return claw.health_check()

    @app.get("/version")
    async def version(api_key: str = Depends(get_api_key)):
        return {"version": VERSION}

    @app.post("/chat", response_model=ChatResponse)
    async def chat(req: ChatRequest, api_key: str = Depends(get_api_key)):
        if req.stream:
            async def gen():
                async for chunk in claw.handle_message_stream(req.message, user_id=req.user_id):
                    yield chunk
            return StreamingResponse(gen(), media_type="text/plain")
        reply = await claw.handle_message(req.message, user_id=req.user_id)
        return ChatResponse(response=reply, session_id=claw.session.session_id)

    @app.get("/tools")
    async def tools(api_key: str = Depends(get_api_key)):
        return {"tools": claw.tools.list_names()}

    @app.get("/stats")
    async def stats(api_key: str = Depends(get_api_key)):
        return {
            "total_tokens": claw.stats.total_tokens,
            "prompt_tokens": claw.stats.prompt_tokens,
            "completion_tokens": claw.stats.completion_tokens,
            "requests": claw.stats.requests,
            "tool_calls": claw.stats.tool_calls,
        }

    @app.get("/sessions")
    async def sessions(api_key: str = Depends(get_api_key)):
        return {"sessions": claw.session_mgr.list_sessions()}

    @app.post("/sessions/clear")
    async def clear_session(api_key: str = Depends(get_api_key)):
        claw.session = claw.session_mgr.new_session()
        return {"session_id": claw.session.session_id}

    return app


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the API server."""
    if not HAS_FASTAPI:
        print("Error: FastAPI not installed. pip install fastapi uvicorn")
        return
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn not installed. pip install uvicorn")
        return
    app = create_app()
    uvicorn.run(app, host=host, port=port)
