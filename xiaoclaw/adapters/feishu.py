"""
Feishu Adapter - 飞书集成
兼容 OpenClaw 生态
"""

import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("xiaoclaw.Feishu")

# 飞书配置
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")


class FeishuAdapter:
    """飞书适配器"""
    
    def __init__(self, app_id: str = None, app_secret: str = None):
        self.app_id = app_id or FEISHU_APP_ID
        self.app_secret = app_secret or FEISHU_APP_SECRET
        self.access_token: Optional[str] = None
        
    def get_tenant_access_token(self) -> str:
        """获取 tenant_access_token"""
        import requests
        
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
            # Feishu API returns tenant_access_token at top level, not nested in "data"
            self.access_token = result.get("tenant_access_token", "")
            if not self.access_token:
                raise Exception(f"Token field missing in response: {result}")
            return self.access_token
        else:
            raise Exception(f"Failed to get token (code={result.get('code')}): {result.get('msg', result)}")
    
    def send_message(self, receive_id: str, message: str) -> Dict:
        """发送消息"""
        import requests
        
        if not self.access_token:
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
        return response.json()
    
    def handle_webhook(self, payload: Dict) -> Optional[str]:
        """处理飞书 webhook 事件"""
        # 简化实现
        event_type = payload.get("type", "")
        
        if event_type == "url_verification":
            # 验证 URL
            return payload.get("challenge", "")
        
        return None


# 兼容 OpenClaw 的飞书模块
def get_feishu_client():
    """获取飞书客户端"""
    return FeishuAdapter()


__all__ = ["FeishuAdapter", "get_feishu_client"]
