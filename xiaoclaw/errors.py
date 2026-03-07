"""xiaoclaw unified error handling"""

class XError(Exception):
    """xiaoclaw 统一错误基类"""
    code = "UNKNOWN"
    hint = ""
    
    def __init__(self, message: str, code: str = None, hint: str = None):
        self.message = message
        if code: self.code = code
        if hint: self.hint = hint
        super().__init__(message)
    
    def format(self) -> str:
        parts = [f"❌ [{self.code}] {self.message}"]
        if self.hint:
            parts.append(f"   💡 {self.hint}")
        return "\n".join(parts)

class ConfigError(XError):
    code = "CONFIG"
    hint = "运行 xiaoclaw --setup 重新配置"

class NetworkError(XError):
    code = "NETWORK"
    hint = "检查网络连接或 API 地址是否正确"

class AuthError(XError):
    code = "AUTH"
    hint = "检查 API Key 是否正确，运行 xiaoclaw --setup 重新配置"

class ToolError(XError):
    code = "TOOL"

class SecurityError(XError):
    code = "SECURITY"
    hint = "此操作被安全策略拦截"
