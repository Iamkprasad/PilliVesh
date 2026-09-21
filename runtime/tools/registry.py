from dataclasses import dataclass
from typing import Callable


@dataclass
class Tool:
    name: str
    description: str
    handler: Callable


class ToolRegistry:

    def __init__(self):
        self.tools = {}

    def register(self, name, description, handler):
        self.tools[name] = Tool(
            name=name,
            description=description,
            handler=handler,
        )

    def list_tools(self):
        return [
            {
                "name": tool.name,
                "description": tool.description,
            }
            for tool in self.tools.values()
        ]

    def get(self, name):
        return self.tools.get(name)


if __name__ == "__main__":
    registry = ToolRegistry()

    registry.register(
        "system_info",
        "Inspect local AI system information.",
        lambda: "system_info handler",
    )

    print(registry.list_tools())
