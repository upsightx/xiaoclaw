#!/usr/bin/env python3
"""Feishu Skill"""
import os, requests
def feishu_doc(action="read", doc_token="", **kwargs):
    app_id = os.getenv("FEISHU_APP_ID","")
    app_secret = os.getenv("FEISHU_APP_SECRET","")
    r = requests.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret}, timeout=10)
    token = r.json().get("data",{}).get("tenant_access_token","")
    if action == "read" and doc_token:
        r = requests.get(f"https://open.feishu.cn/open-apis/doc/v3/{doc_token}/content",
            headers={"Authorization": f"Bearer {token}"})
        return str(r.json())[:2000]
    return "OK"
def get_skill():
    from xiaoclaw.skills import create_skill
    return create_skill("feishu", "飞书操作", {"feishu_doc": feishu_doc})
skill = get_skill()
