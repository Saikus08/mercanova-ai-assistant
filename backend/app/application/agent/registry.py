"""Registry of the tools the model may call."""

from app.application.agent.permissions import PERMISSIONS, Permission
from app.application.agent.tool import Tool, ToolSpec


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            self._check(tool)
            self._tools[tool.name] = tool

    def _check(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Duplicate tool name: {tool.name}")
        permission = PERMISSIONS.get(tool.name)
        if permission is None:
            raise ValueError(f"Tool {tool.name} has no permission entry")
        if permission is Permission.FORBIDDEN:
            raise ValueError(f"Tool {tool.name} is forbidden and can never be registered")
        if tool.args_model.model_config.get("extra") != "forbid":
            raise ValueError(f"Arguments of {tool.name} must forbid extra fields")

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    def specs(self) -> list[ToolSpec]:
        return [tool.spec() for tool in self._tools.values()]
