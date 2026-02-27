#!/usr/bin/env python3
"""Feishu Skill — 飞书文档操作"""
import os
import logging

logger = logging.getLogger("xiaoclaw.skills.feishu")

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def feishu_doc(action="read", doc_token="", **kwargs):
    """飞书文档操作：读取文档内容。"""
    if not HAS_REQUESTS:
        return "Error: requests library not installed. pip install requests"

    app_id = os.getenv("FEISHU_APP_ID", "")
    app_secret = os.getenv("FEISHU_APP_SECRET", "")

    if not app_id or not app_secret:
        return "Error: FEISHU_APP_ID and FEISHU_APP_SECRET environment variables are required"

    # Get tenant access token
    try:
        r = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=10,
        )
        r.raise_for_status()
        result = r.json()
    except requests.RequestException as e:
        return f"Error: failed to get Feishu access token: {e}"

    # Feishu API returns tenant_access_token at top level, not nested in "data"
    if result.get("code") != 0:
        return f"Error: Feishu auth failed (code={result.get('code')}): {result.get('msg', '')}"
    token = result.get("tenant_access_token", "")
    if not token:
        return "Error: tenant_access_token not found in response"

    if action == "read" and doc_token:
        try:
            r = requests.get(
                f"https://open.feishu.cn/open-apis/doc/v3/{doc_token}/content",
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            r.raise_for_status()
            return str(r.json())[:2000]
        except requests.RequestException as e:
            return f"Error: failed to read document: {e}"

    return "OK"


def get_skill():
    from xiaoclaw.skills import create_skill
    return create_skill("feishu", "飞书操作", {"feishu_doc": feishu_doc})


skill = get_skill()
