from runtime.tools.registry import ToolRegistry
from runtime.tools.system_info import run as system_info


def create_registry():
    registry = ToolRegistry()

    registry.register(
        "system_info",
        "Inspect current CPU, RAM, swap and GPU/Vulkan state.",
        system_info,
    )

    return registry


if __name__ == "__main__":
    registry = create_registry()

    print("Available tools:")
    for tool in registry.list_tools():
        print(f"- {tool['name']}: {tool['description']}")
