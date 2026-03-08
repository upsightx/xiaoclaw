"""
Feishu Adapter - 飞书集成
兼容 OpenClaw 生态
"""

import os
import json
import logging
import time
from typing import Dict, Optional

logger = logging.getLogger("xiaoclaw.Feishu")


class FeishuAdapter:
    """飞书适配器"""
    
    def __init__(self, app_id: Optional[str] = None, app_secret: Optional[str] = None, 
                 verification_token: Optional[str] = None):
        # Read from env in __init__ only, don't expose at module level
        self.app_id = app_id or os.getenv("FEISHU_APP_ID", "")
        self.app_secret = app_secret or os.getenv("FEISHU_APP_SECRET", "")
        self.verification_token = verification_token or os.getenv("FEISHU_VERIFICATION_TOKEN", "")
        self.access_token: Optional[str] = None
        self._token_expires_at: float = 0  # Token expiry timestamp
    
    def _is_token_valid(self) -> bool:
        """Check if the cached token is still valid."""
        return self.access_token and time.time() < self._token_expires_at - 60  # 60s buffer
        
    def get_tenant_access_token(self, force_refresh: bool = False) -> str:
        """获取 tenant_access_token"""
        import requests
        
        # Return cached token if valid
        if not force_refresh and self._is_token_valid():
            return self.access_token
        
        if not self.app_id or not self.app_secret:
            raise ValueError(
                "飞书 app_id 和 app_secret 未配置。"
                "请设置环境变量 FEISHU_APP_ID 和 FEISHU_APP_SECRET"
            )
        
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        response = requests.post(url, json=data, timeout=10)
        result = response.json()
        
        if result.get("code") == 0:
            self.access_token = result.get("tenant_access_token", "")
            expire = result.get("expire", 7200)  # Default 2 hours
            self._token_expires_at = time.time() + expire
            if not self.access_token:
                raise Exception(f"Token field missing in response: {result}")
            return self.access_token
        else:
            raise Exception(f"Failed to get token (code={result.get('code')}): {result.get('msg', result)}")
    
    def send_message(self, receive_id: str, message: str) -> Dict:
        """发送消息"""
        import requests
        
        # Get fresh token (will auto-refresh if expired)
        self.get_tenant_access_token()
        
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        params = {
            "receive_id_type": "open_id"
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        data = {
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps({"text": message})
        }
        
        response = requests.post(url, params=params, headers=headers, json=data)
        result = response.json()
        
        # Check for errors
        if result.get("code") != 0:
            logger.error(f"Feishu send_message error: {result}")
            # If token expired, force refresh and retry once
            if result.get("code") == 99991663:  # Token expired
                self.get_tenant_access_token(force_refresh=True)
                headers["Authorization"] = f"Bearer {self.access_token}"
                response = requests.post(url, params=params, headers=headers, json=data)
                result = response.json()
        
        return result
    
    def handle_webhook(self, payload: Dict, headers: Dict = None) -> Optional[str]:
        """处理飞书 webhook 事件"""
        # Verify webhook token if configured
        if self.verification_token:
            token = payload.get("token", "")
            if token != self.verification_token:
                logger.warning("Feishu webhook: invalid token")
                return None
        
        event_type = payload.get("type", "")
        
        if event_type == "url_verification":
            # Return proper JSON response per Feishu API spec
            return json.dumps({"challenge": payload.get("challenge", "")})
        
        return None


# 兼容 OpenClaw 的飞书模块
def get_feishu_client():
    """获取飞书客户端"""
    return FeishuAdapter()


__all__ = ["FeishuAdapter", "get_feishu_client"]
