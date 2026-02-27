"""xiaoclaw Web UI — modern chat interface with FastAPI backend"""
import logging
from pathlib import Path
from typing import Optional, AsyncGenerator
from datetime import datetime

logger = logging.getLogger("xiaoclaw.WebUI")

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
from dataclasses import asdict
    import json
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


# HTML 模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>xiaoclaw 🐾 AI Assistant</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        .chat-container { height: calc(100vh - 200px); }
        .message-user { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .message-ai { background: #1e1e2e; }
        .typing-indicator span { animation: blink 1.4s infinite both; }
        .typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
        .typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes blink { 0%, 80%, 100% { opacity: 0.3; } 40% { opacity: 1; } }
        pre { background: #0d1117; border-radius: 8px; padding: 16px; overflow-x: auto; }
        code { font-family: 'JetBrains Mono', 'Fira Code', monospace; }
        .sidebar { transition: transform 0.3s ease; }
        .sidebar.hidden { transform: translateX(-100%); }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #4a4a5a; border-radius: 3px; }
        .fade-in { animation: fadeIn 0.3s ease; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body class="bg-gray-950 text-gray-100 min-h-screen">
    <div class="flex h-screen">
        <!-- 侧边栏 -->
        <aside id="sidebar" class="sidebar w-72 bg-gray-900 border-r border-gray-800 flex flex-col fixed h-full z-20 lg:relative">
            <div class="p-4 border-b border-gray-800">
                <div class="flex items-center gap-3">
                    <span class="text-3xl">🐾</span>
                    <div>
                        <h1 class="font-bold text-lg">xiaoclaw</h1>
                        <p class="text-xs text-gray-500" id="model-info">Loading...</p>
                    </div>
                </div>
            </div>
            
            <div class="p-3">
                <button onclick="newChat()" class="w-full py-2.5 px-4 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 rounded-lg font-medium flex items-center justify-center gap-2 transition-all">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
                    新对话
                </button>
            </div>
            
            <div class="flex-1 overflow-y-auto p-3 space-y-1" id="session-list"></div>
            
            <div class="p-3 border-t border-gray-800 space-y-2">
                <div class="text-xs text-gray-500 flex justify-between">
                    <span>Token: <span id="token-count">0</span></span>
                    <span>请求: <span id="request-count">0</span></span>
                </div>
                <button onclick="showSettings()" class="w-full py-2 px-3 text-sm text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg flex items-center gap-2 transition-colors">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
                    设置
                </button>
            </div>
        </aside>
        
        <!-- 遮罩层 -->
        <div id="overlay" class="fixed inset-0 bg-black/50 z-10 lg:hidden hidden" onclick="toggleSidebar()"></div>
        
        <!-- 主区域 -->
        <main class="flex-1 flex flex-col min-w-0">
            <!-- 顶部栏 -->
            <header class="h-14 border-b border-gray-800 flex items-center px-4 gap-4 bg-gray-900/50 backdrop-blur">
                <button onclick="toggleSidebar()" class="lg:hidden p-2 hover:bg-gray-800 rounded-lg">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/></svg>
                </button>
                <h2 class="font-medium truncate" id="chat-title">新对话</h2>
                <div class="flex-1"></div>
                <span id="status" class="text-xs px-2 py-1 rounded-full bg-green-500/20 text-green-400">就绪</span>
            </header>
            
            <!-- 消息区域 -->
            <div class="chat-container flex-1 overflow-y-auto p-4 space-y-4" id="messages">
                <div class="text-center text-gray-500 py-20">
                    <p class="text-6xl mb-4">🐾</p>
                    <p class="text-lg">开始一段新对话</p>
                    <p class="text-sm mt-2">xiaoclaw - 轻量级 AI Agent</p>
                </div>
            </div>
            
            <!-- 输入区域 -->
            <div class="border-t border-gray-800 p-4 bg-gray-900/50 backdrop-blur">
                <form onsubmit="sendMessage(event)" class="max-w-4xl mx-auto">
                    <div class="flex gap-3">
                        <div class="flex-1 relative">
                            <textarea id="input" rows="1" placeholder="输入消息..." 
                                class="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 pr-12 resize-none focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-all"
                                onkeydown="handleKeydown(event)" oninput="autoResize(this)"></textarea>
                            <button type="button" onclick="toggleVoice()" id="voice-btn" class="absolute right-3 bottom-3 text-gray-400 hover:text-white transition-colors hidden">
                                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"/></svg>
                            </button>
                        </div>
                        <button type="submit" id="send-btn" class="px-4 py-3 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 rounded-xl font-medium transition-all flex items-center gap-2">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/></svg>
                        </button>
                    </div>
                </form>
            </div>
        </main>
    </div>
    
    <!-- 设置弹窗 -->
    <div id="settings-modal" class="fixed inset-0 bg-black/70 z-50 hidden items-center justify-center">
        <div class="bg-gray-900 rounded-2xl p-6 w-full max-w-md m-4 fade-in">
            <div class="flex items-center justify-between mb-6">
                <h3 class="text-lg font-bold">设置</h3>
                <button onclick="hideSettings()" class="text-gray-400 hover:text-white">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                </button>
            </div>
            <div class="space-y-4">
                <div>
                    <label class="block text-sm text-gray-400 mb-1">API Base URL</label>
                    <input type="text" id="settings-base-url" class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 focus:outline-none focus:border-purple-500">
                </div>
                <div>
                    <label class="block text-sm text-gray-400 mb-1">API Key</label>
                    <input type="password" id="settings-api-key" class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 focus:outline-none focus:border-purple-500" placeholder="sk-...">
                </div>
                <div>
                    <label class="block text-sm text-gray-400 mb-1">模型</label>
                    <input type="text" id="settings-model" class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 focus:outline-none focus:border-purple-500">
                </div>
                <button onclick="saveSettings()" class="w-full py-2 bg-purple-600 hover:bg-purple-700 rounded-lg font-medium transition-colors">保存</button>
            </div>
        </div>
    </div>

    <script>
        let sessionId = null;
        let isLoading = false;
        
        // 初始化
        document.addEventListener('DOMContentLoaded', async () => {
            await loadStats();
            await loadModelInfo();
            hljs.highlightAll();
        });
        
        async function loadStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                document.getElementById('token-count').textContent = data.total_tokens?.toLocaleString() || '0';
                document.getElementById('request-count').textContent = data.requests || '0';
            } catch (e) {}
        }
        
        async function loadModelInfo() {
            try {
                const res = await fetch('/api/model');
                const data = await res.json();
                document.getElementById('model-info').textContent = data.model || 'Unknown';
            } catch (e) {
                document.getElementById('model-info').textContent = 'Not configured';
            }
        }
        
        function autoResize(el) {
            el.style.height = 'auto';
            el.style.height = Math.min(el.scrollHeight, 200) + 'px';
        }
        
        function handleKeydown(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage(e);
            }
        }
        
        async function sendMessage(e) {
            e.preventDefault();
            if (isLoading) return;
            
            const input = document.getElementById('input');
            const message = input.value.trim();
            if (!message) return;
            
            addMessage('user', message);
            input.value = '';
            input.style.height = 'auto';
            
            isLoading = true;
            setStatus('思考中...', 'thinking');
            showTyping();
            
            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message, session_id: sessionId })
                });
                
                const data = await res.json();
                hideTyping();
                addMessage('ai', data.response);
                sessionId = data.session_id;
                
                await loadStats();
                setStatus('就绪', 'ready');
            } catch (e) {
                hideTyping();
                addMessage('ai', '❌ 请求失败: ' + e.message);
                setStatus('错误', 'error');
            }
            
            isLoading = false;
        }
        
        function addMessage(role, content) {
            const container = document.getElementById('messages');
            const isUser = role === 'user';
            
            // 清除欢迎提示
            if (container.querySelector('.text-center')) {
                container.innerHTML = '';
            }
            
            const div = document.createElement('div');
            div.className = 'fade-in flex ' + (isUser ? 'justify-end' : 'justify-start');
            
            const avatar = isUser ? '👤' : '🐾';
            const bgClass = isUser ? 'message-user' : 'message-ai';
            
            let rendered = content;
            try {
                rendered = marked.parse(content);
                setTimeout(() => container.querySelectorAll('pre code').forEach(el => hljs.highlightElement(el)), 0);
            } catch (e) {
                rendered = content.replace(/\\n/g, '<br>');
            }
            
            div.innerHTML = `
                <div class="flex gap-3 max-w-3xl ${isUser ? 'flex-row-reverse' : ''}">
                    <div class="w-8 h-8 rounded-lg bg-gray-800 flex items-center justify-center text-lg shrink-0">${avatar}</div>
                    <div class="${bgClass} rounded-2xl px-4 py-3 ${isUser ? 'rounded-tr-md' : 'rounded-tl-md'}">
                        <div class="prose prose-invert prose-sm max-w-none">${rendered}</div>
                    </div>
                </div>
            `;
            
            container.appendChild(div);
            container.scrollTop = container.scrollHeight;
        }
        
        function showTyping() {
            const container = document.getElementById('messages');
            const div = document.createElement('div');
            div.id = 'typing';
            div.className = 'fade-in flex justify-start';
            div.innerHTML = `
                <div class="flex gap-3">
                    <div class="w-8 h-8 rounded-lg bg-gray-800 flex items-center justify-center text-lg">🐾</div>
                    <div class="message-ai rounded-2xl rounded-tl-md px-4 py-3">
                        <div class="typing-indicator flex gap-1">
                            <span class="w-2 h-2 bg-gray-400 rounded-full"></span>
                            <span class="w-2 h-2 bg-gray-400 rounded-full"></span>
                            <span class="w-2 h-2 bg-gray-400 rounded-full"></span>
                        </div>
                    </div>
                </div>
            `;
            container.appendChild(div);
            container.scrollTop = container.scrollHeight;
        }
        
        function hideTyping() {
            const typing = document.getElementById('typing');
            if (typing) typing.remove();
        }
        
        function setStatus(text, type) {
            const el = document.getElementById('status');
            el.textContent = text;
            el.className = 'text-xs px-2 py-1 rounded-full ';
            if (type === 'thinking') el.className += 'bg-yellow-500/20 text-yellow-400';
            else if (type === 'error') el.className += 'bg-red-500/20 text-red-400';
            else el.className += 'bg-green-500/20 text-green-400';
        }
        
        async function newChat() {
            try {
                await fetch('/api/sessions/clear', { method: 'POST' });
                sessionId = null;
                document.getElementById('messages').innerHTML = `
                    <div class="text-center text-gray-500 py-20">
                        <p class="text-6xl mb-4">🐾</p>
                        <p class="text-lg">开始一段新对话</p>
                    </div>
                `;
                document.getElementById('chat-title').textContent = '新对话';
            } catch (e) {}
        }
        
        function toggleSidebar() {
            const sidebar = document.getElementById('sidebar');
            const overlay = document.getElementById('overlay');
            sidebar.classList.toggle('hidden');
            overlay.classList.toggle('hidden');
        }
        
        function showSettings() {
            document.getElementById('settings-modal').classList.remove('hidden');
            document.getElementById('settings-modal').classList.add('flex');
        }
        
        function hideSettings() {
            document.getElementById('settings-modal').classList.add('hidden');
            document.getElementById('settings-modal').classList.remove('flex');
        }
        
        async function saveSettings() {
            const baseUrl = document.getElementById('settings-base-url').value;
            const apiKey = document.getElementById('settings-api-key').value;
            const model = document.getElementById('settings-model').value;
            
            try {
                await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ base_url: baseUrl, api_key: apiKey, model })
                });
                hideSettings();
                await loadModelInfo();
            } catch (e) {
                alert('保存失败: ' + e.message);
            }
        }
    </script>
</body>
</html>
"""


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: str = "webui"


class SettingsRequest(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None


def create_webui(claw=None):
    """Create Web UI FastAPI app."""
    if not HAS_FASTAPI:
        raise RuntimeError("FastAPI not installed. pip install fastapi uvicorn")

    from .core import XiaClaw, XiaClawConfig, VERSION

    if claw is None:
        claw = XiaClaw(XiaClawConfig.from_env())

    app = FastAPI(title="xiaoclaw WebUI", version=VERSION)
    
    # 共享实例
    app.state.claw = claw

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML_TEMPLATE

    @app.get("/api/model")
    async def get_model():
        cfg = claw.config
        provider = cfg.providers.get(cfg.active_provider, {})
        return {
            "model": provider.get("default_model", "unknown"),
            "provider": cfg.active_provider
        }

    @app.post("/api/chat")
    async def chat(req: ChatRequest):
        try:
            reply = await claw.handle_message(req.message, user_id=req.user_id)
            return {"response": reply, "session_id": claw.session.session_id}
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return {"response": f"❌ 错误: {str(e)}", "session_id": None}

    @app.get("/api/stats")
    async def stats():
        return {
            "total_tokens": claw.stats.total_tokens,
            "prompt_tokens": claw.stats.prompt_tokens,
            "completion_tokens": claw.stats.completion_tokens,
            "requests": claw.stats.requests,
            "tool_calls": claw.stats.tool_calls,
        }

    @app.get("/api/tools")
    async def tools():
        return {"tools": claw.tools.list_names()}

    @app.get("/api/sessions")
    async def sessions():
        return {"sessions": claw.session_mgr.list_sessions()}

    @app.post("/api/sessions/clear")
    async def clear_session():
        claw.session = claw.session_mgr.new_session()
        return {"session_id": claw.session.session_id}

    @app.post("/api/settings")
    async def update_settings(req: SettingsRequest):
        """Update runtime settings (requires restart for full effect)."""
        if req.base_url:
            claw.config.providers[claw.config.active_provider]["base_url"] = req.base_url
        if req.api_key:
            claw.config.providers[claw.config.active_provider]["api_key"] = req.api_key
        if req.model:
            claw.config.providers[claw.config.active_provider]["default_model"] = req.model
        return {"status": "ok"}

    @app.get("/api/analytics")
    async def get_analytics(days: int = 7):
        """Get analytics for recent days."""
        return claw.analytics.get_recent_stats(days)

    @app.get("/api/analytics/daily/{date}")
    async def get_daily_analytics(date: str):
        """Get analytics for a specific date."""
        daily = claw.analytics.get_daily_stats(date)
        return asdict(daily) if daily else {"error": "No data for date"}

    @app.get("/api/analytics/range")
    async def get_range_analytics(start: str, end: str):
        """Get analytics for a date range."""
        return claw.analytics.get_range_stats(start, end)

    return app


def run_webui(host: str = "0.0.0.0", port: int = 8080):
    """Run the Web UI server."""
    if not HAS_FASTAPI:
        print("Error: FastAPI not installed. pip install fastapi uvicorn")
        return
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn not installed. pip install uvicorn")
        return
    
    print(f"🐾 xiaoclaw Web UI starting at http://{host}:{port}")
    app = create_webui()
    uvicorn.run(app, host=host, port=port)
