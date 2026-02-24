"""xiaoclaw Webhook Server — receive HTTP callbacks and route to handlers"""
import json
import hmac
import hashlib
import logging
from typing import Dict, Any, Optional, Callable, List

logger = logging.getLogger("xiaoclaw.Webhook")

try:
    from fastapi import FastAPI, Request, HTTPException
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


class WebhookHandler:
    """A registered webhook handler."""
    def __init__(self, name: str, path: str, callback: Callable, secret: str = ""):
        self.name = name
        self.path = path
        self.callback = callback
        self.secret = secret


class WebhookServer:
    """Manages webhook endpoints. Integrates with FastAPI app."""

    def __init__(self):
        self.handlers: Dict[str, WebhookHandler] = {}
        self._event_log: List[Dict] = []

    def register(self, name: str, path: str, callback: Callable, secret: str = ""):
        """Register a webhook handler at a given path."""
        self.handlers[name] = WebhookHandler(name, path, callback, secret)
        logger.info(f"Webhook registered: {name} → {path}")

    def unregister(self, name: str):
        self.handlers.pop(name, None)

    def list_handlers(self) -> List[Dict[str, str]]:
        return [{"name": h.name, "path": h.path} for h in self.handlers.values()]

    def verify_signature(self, handler: WebhookHandler, body: bytes, signature: str) -> bool:
        """Verify HMAC-SHA256 webhook signature."""
        if not handler.secret:
            return True
        expected = hmac.new(handler.secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(f"sha256={expected}", signature)

    async def dispatch(self, path: str, body: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        """Dispatch incoming webhook to matching handler."""
        for handler in self.handlers.values():
            if handler.path == path:
                # Verify signature if secret is set
                sig = headers.get("x-hub-signature-256", headers.get("x-signature", ""))
                if handler.secret and not self.verify_signature(handler, body, sig):
                    logger.warning(f"Webhook signature mismatch: {handler.name}")
                    return {"error": "Invalid signature", "status": 403}

                try:
                    payload = json.loads(body) if body else {}
                except json.JSONDecodeError:
                    payload = {"raw": body.decode("utf-8", errors="replace")}

                self._event_log.append({
                    "handler": handler.name,
                    "path": path,
                    "payload_size": len(body),
                })
                # Keep log bounded
                if len(self._event_log) > 100:
                    self._event_log = self._event_log[-50:]

                try:
                    import asyncio
                    if asyncio.iscoroutinefunction(handler.callback):
                        result = await handler.callback(payload, headers)
                    else:
                        result = handler.callback(payload, headers)
                    return {"ok": True, "result": result}
                except Exception as e:
                    logger.error(f"Webhook handler '{handler.name}' error: {e}")
                    return {"error": str(e), "status": 500}

        return {"error": "No handler for path", "status": 404}

    def get_event_log(self, limit: int = 20) -> List[Dict]:
        return self._event_log[-limit:]

    def mount_on_app(self, app):
        """Mount webhook routes on a FastAPI app."""
        if not HAS_FASTAPI:
            raise RuntimeError("FastAPI not installed")

        server = self

        @app.post("/webhook/{path:path}")
        async def webhook_endpoint(path: str, request: Request):
            body = await request.body()
            headers = dict(request.headers)
            result = await server.dispatch(f"/{path}", body, headers)
            if "error" in result:
                raise HTTPException(status_code=result.get("status", 400), detail=result["error"])
            return result

        @app.get("/webhooks")
        async def list_webhooks():
            return {"handlers": server.list_handlers(), "events": server.get_event_log(10)}

        logger.info(f"Webhook routes mounted: {len(server.handlers)} handlers")


# Default webhook callbacks
def github_webhook(payload: Dict, headers: Dict) -> str:
    """Handle GitHub webhook events."""
    event = headers.get("x-github-event", "unknown")
    action = payload.get("action", "")
    repo = payload.get("repository", {}).get("full_name", "")
    if event == "push":
        commits = len(payload.get("commits", []))
        return f"GitHub push: {repo} ({commits} commits)"
    elif event == "issues":
        title = payload.get("issue", {}).get("title", "")
        return f"GitHub issue {action}: {repo} — {title}"
    elif event == "pull_request":
        title = payload.get("pull_request", {}).get("title", "")
        return f"GitHub PR {action}: {repo} — {title}"
    return f"GitHub {event}: {repo}"


def generic_webhook(payload: Dict, headers: Dict) -> str:
    """Generic webhook handler — just logs the event."""
    return f"Received: {len(json.dumps(payload))} bytes"
