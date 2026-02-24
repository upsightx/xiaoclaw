"""xiaoclaw Provider System - Multi-provider LLM management"""
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    from openai import AsyncOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

logger = logging.getLogger("xiaoclaw.Providers")


@dataclass
class ProviderConfig:
    name: str
    api_key: str
    base_url: str
    models: List[str] = field(default_factory=list)
    default_model: str = ""
    provider_type: str = "openai"  # openai | anthropic

    def __post_init__(self):
        if self.models and not self.default_model:
            self.default_model = self.models[0]


class Provider:
    """Wraps an async LLM client for a single provider."""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.client: Optional[AsyncOpenAI] = None
        if HAS_OPENAI and config.api_key:
            self.client = AsyncOpenAI(
                api_key=config.api_key, base_url=config.base_url
            )
        self.current_model = config.default_model
        logger.info(f"Provider '{config.name}' ready: {self.current_model} @ {config.base_url}")

    @property
    def ready(self) -> bool:
        return self.client is not None

    async def chat(self, messages: List[Dict], model: str = "", **kwargs) -> str:
        if not self.client:
            return "[Provider not configured]"
        use_model = model or self.current_model
        try:
            resp = await self.client.chat.completions.create(
                model=use_model, messages=messages, **kwargs
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"Provider '{self.config.name}' error: {e}")
            return f"[LLM Error: {e}]"


class ProviderManager:
    """Manages multiple providers with runtime switching."""

    def __init__(self):
        self.providers: Dict[str, Provider] = {}
        self.active_name: str = ""

    @property
    def active(self) -> Optional[Provider]:
        return self.providers.get(self.active_name)

    def add(self, config: ProviderConfig) -> Provider:
        p = Provider(config)
        self.providers[config.name] = p
        if not self.active_name:
            self.active_name = config.name
        return p

    def switch(self, name: str) -> bool:
        if name in self.providers:
            self.active_name = name
            logger.info(f"Switched to provider: {name}")
            return True
        logger.warning(f"Provider not found: {name}")
        return False

    def switch_model(self, model: str, provider_name: str = "") -> bool:
        p = self.providers.get(provider_name) if provider_name else self.active
        if p:
            p.current_model = model
            logger.info(f"Model switched to: {model}")
            return True
        return False

    def list_providers(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": n,
                "active": n == self.active_name,
                "model": p.current_model,
                "base_url": p.config.base_url,
                "ready": p.ready,
            }
            for n, p in self.providers.items()
        ]

    async def chat_with_failover(self, messages: List[Dict], **kwargs) -> str:
        """Try active provider, failover to others on failure."""
        tried = set()
        for name in [self.active_name] + [n for n in self.providers if n != self.active_name]:
            if name in tried or name not in self.providers:
                continue
            tried.add(name)
            p = self.providers[name]
            if not p.ready:
                continue
            result = await p.chat(messages, **kwargs)
            if not result.startswith("[LLM Error"):
                if name != self.active_name:
                    logger.info(f"Failover: switched to '{name}'")
                    self.active_name = name
                return result
            logger.warning(f"Provider '{name}' failed, trying next...")
        return "[All providers failed]"

    async def chat(self, messages: List[Dict], **kwargs) -> str:
        if not self.active:
            return "[No active provider]"
        return await self.active.chat(messages, **kwargs)

    @classmethod
    def from_env(cls) -> "ProviderManager":
        """Load providers from environment variables."""
        mgr = cls()
        api_key = os.getenv("OPENAI_API_KEY", "")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.minimax.chat/v1")
        model = os.getenv("XIAOCLAW_MODEL", "MiniMax-M2.5")
        if api_key:
            mgr.add(ProviderConfig(
                name="default", api_key=api_key, base_url=base_url,
                models=[model], default_model=model, provider_type="openai",
            ))
        # Check for additional providers via XIAOCLAW_PROVIDER_* env vars
        for key, val in os.environ.items():
            if key.startswith("XIAOCLAW_PROVIDER_") and key.endswith("_API_KEY"):
                pname = key.replace("XIAOCLAW_PROVIDER_", "").replace("_API_KEY", "").lower()
                purl = os.getenv(f"XIAOCLAW_PROVIDER_{pname.upper()}_BASE_URL", base_url)
                pmodel = os.getenv(f"XIAOCLAW_PROVIDER_{pname.upper()}_MODEL", model)
                mgr.add(ProviderConfig(
                    name=pname, api_key=val, base_url=purl,
                    models=[pmodel], default_model=pmodel,
                ))
        return mgr

    @classmethod
    def from_config(cls, config_path: Path) -> "ProviderManager":
        """Load providers from config.yaml."""
        mgr = cls()
        if not HAS_YAML or not config_path.exists():
            return cls.from_env()
        try:
            data = yaml.safe_load(config_path.read_text())
            providers = data.get("providers", {})
            for name, cfg in providers.items():
                api_key = cfg.get("api_key", "")
                if api_key.startswith("${") and api_key.endswith("}"):
                    api_key = os.getenv(api_key[2:-1], "")
                mgr.add(ProviderConfig(
                    name=name,
                    api_key=api_key,
                    base_url=cfg.get("base_url", ""),
                    models=cfg.get("models", []),
                    default_model=cfg.get("default_model", ""),
                    provider_type=cfg.get("type", "openai"),
                ))
            # Set active from config
            active = data.get("active_provider", "")
            if active and active in mgr.providers:
                mgr.active_name = active
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return cls.from_env()
        return mgr


def test_providers():
    """Quick self-test."""
    mgr = ProviderManager()
    mgr.add(ProviderConfig(
        name="test", api_key="sk-test", base_url="https://test.api/v1",
        models=["test-model"], default_model="test-model",
    ))
    mgr.add(ProviderConfig(
        name="backup", api_key="sk-backup", base_url="https://backup.api/v1",
        models=["backup-model"],
    ))
    assert mgr.active_name == "test"
    assert mgr.switch("backup")
    assert mgr.active_name == "backup"
    assert mgr.switch_model("new-model")
    assert mgr.active.current_model == "new-model"
    assert len(mgr.list_providers()) == 2
    assert not mgr.switch("nonexistent")
    print("  ✓ providers.py tests passed")


if __name__ == "__main__":
    test_providers()
