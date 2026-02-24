"""xiaoclaw API Server — lightweight FastAPI-based HTTP interface"""
import logging
from typing import Optional

logger = logging.getLogger("xiaoclaw.API")

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


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
        return claw.health_check()

    @app.get("/version")
    async def version():
        return {"version": VERSION}

    @app.post("/chat", response_model=ChatResponse)
    async def chat(req: ChatRequest):
        if req.stream:
            async def gen():
                async for chunk in claw.handle_message_stream(req.message, user_id=req.user_id):
                    yield chunk
            return StreamingResponse(gen(), media_type="text/plain")
        reply = await claw.handle_message(req.message, user_id=req.user_id)
        return ChatResponse(response=reply, session_id=claw.session.session_id)

    @app.get("/tools")
    async def tools():
        return {"tools": claw.tools.list_names()}

    @app.get("/stats")
    async def stats():
        return {
            "total_tokens": claw.stats.total_tokens,
            "prompt_tokens": claw.stats.prompt_tokens,
            "completion_tokens": claw.stats.completion_tokens,
            "requests": claw.stats.requests,
            "tool_calls": claw.stats.tool_calls,
        }

    @app.get("/sessions")
    async def sessions():
        return {"sessions": claw.session_mgr.list_sessions()}

    @app.post("/sessions/clear")
    async def clear_session():
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
