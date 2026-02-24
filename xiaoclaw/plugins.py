"""xiaoclaw Plugin System — discover and load pip-installable plugins"""
import logging
import importlib
import importlib.metadata
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field

logger = logging.getLogger("xiaoclaw.Plugins")

PLUGIN_ENTRY_POINT = "xiaoclaw.plugins"


@dataclass
class PluginInfo:
    """Metadata about a loaded plugin."""
    name: str
    version: str = ""
    description: str = ""
    module: Any = None
    enabled: bool = True
    tools: Dict[str, Callable] = field(default_factory=dict)
    hooks: Dict[str, Callable] = field(default_factory=dict)


class PluginManager:
    """Discovers and manages xiaoclaw plugins via entry_points."""

    def __init__(self):
        self.plugins: Dict[str, PluginInfo] = {}

    def discover(self) -> List[str]:
        """Discover installed plugins via entry_points (pip-installable)."""
        discovered = []
        try:
            eps = importlib.metadata.entry_points()
            # Python 3.12+ returns SelectableGroups, 3.10+ may differ
            if hasattr(eps, 'select'):
                plugin_eps = eps.select(group=PLUGIN_ENTRY_POINT)
            elif isinstance(eps, dict):
                plugin_eps = eps.get(PLUGIN_ENTRY_POINT, [])
            else:
                plugin_eps = [ep for ep in eps if ep.group == PLUGIN_ENTRY_POINT]

            for ep in plugin_eps:
                try:
                    module = ep.load()
                    info = self._extract_plugin_info(ep.name, module)
                    self.plugins[ep.name] = info
                    discovered.append(ep.name)
                    logger.info(f"Plugin discovered: {ep.name} v{info.version}")
                except Exception as e:
                    logger.error(f"Failed to load plugin '{ep.name}': {e}")
        except Exception as e:
            logger.debug(f"Plugin discovery: {e}")
        return discovered

    def load_module(self, name: str, module_path: str) -> Optional[PluginInfo]:
        """Manually load a plugin from a module path."""
        try:
            module = importlib.import_module(module_path)
            info = self._extract_plugin_info(name, module)
            self.plugins[name] = info
            logger.info(f"Plugin loaded: {name}")
            return info
        except Exception as e:
            logger.error(f"Failed to load plugin '{name}' from {module_path}: {e}")
            return None

    def _extract_plugin_info(self, name: str, module) -> PluginInfo:
        """Extract plugin info from a loaded module."""
        info = PluginInfo(name=name, module=module)
        info.version = getattr(module, '__version__', getattr(module, 'VERSION', ''))
        info.description = getattr(module, '__description__', getattr(module, 'DESCRIPTION', ''))

        # Extract tools: module.TOOLS = {"name": callable}
        if hasattr(module, 'TOOLS'):
            info.tools = dict(module.TOOLS)
        elif hasattr(module, 'get_tools'):
            info.tools = dict(module.get_tools())

        # Extract hooks: module.HOOKS = {"event": callable}
        if hasattr(module, 'HOOKS'):
            info.hooks = dict(module.HOOKS)
        elif hasattr(module, 'get_hooks'):
            info.hooks = dict(module.get_hooks())

        # Call setup if exists
        if hasattr(module, 'setup'):
            try:
                module.setup()
            except Exception as e:
                logger.error(f"Plugin '{name}' setup error: {e}")

        return info

    def enable(self, name: str) -> bool:
        if name in self.plugins:
            self.plugins[name].enabled = True
            return True
        return False

    def disable(self, name: str) -> bool:
        if name in self.plugins:
            self.plugins[name].enabled = False
            return True
        return False

    def list_plugins(self) -> List[Dict[str, Any]]:
        return [
            {"name": p.name, "version": p.version, "description": p.description,
             "enabled": p.enabled, "tools": list(p.tools.keys()),
             "hooks": list(p.hooks.keys())}
            for p in self.plugins.values()
        ]

    def get_all_tools(self) -> Dict[str, Callable]:
        """Get all tools from enabled plugins."""
        tools = {}
        for p in self.plugins.values():
            if p.enabled:
                tools.update(p.tools)
        return tools

    def get_all_hooks(self) -> Dict[str, List[Callable]]:
        """Get all hooks from enabled plugins."""
        hooks: Dict[str, List[Callable]] = {}
        for p in self.plugins.values():
            if p.enabled:
                for event, fn in p.hooks.items():
                    hooks.setdefault(event, []).append(fn)
        return hooks

    def apply_to_claw(self, claw):
        """Register all plugin tools and hooks with a XiaClaw instance."""
        for p in self.plugins.values():
            if not p.enabled:
                continue
            # Register tools
            for name, func in p.tools.items():
                claw.tools.tools[name] = {"func": func, "description": f"Plugin: {p.name}"}
                logger.info(f"Plugin tool registered: {name} (from {p.name})")
            # Register hooks
            for event, func in p.hooks.items():
                claw.hooks.register(event, func)
                logger.info(f"Plugin hook registered: {event} (from {p.name})")
