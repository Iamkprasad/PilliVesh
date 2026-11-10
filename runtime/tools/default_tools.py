from runtime.tools.registry import ToolRegistry
from runtime.tools.system_info import run as system_info
from runtime.tools.file_ops import file_read, list_dir
from runtime.tools.web_fetch import fetch_url


def create_registry():
    registry = ToolRegistry()

    registry.register(
        "system_info",
        "Inspect current CPU, RAM, swap and GPU/Vulkan state.",
        system_info,
    )

    registry.register(
        "file_read",
        "Read a text file inside the project root. Takes a path argument.",
        file_read,
    )

    registry.register(
        "list_dir",
        "List entries in a directory inside the project root. Optional path argument.",
        list_dir,
    )

    registry.register(
        "web_fetch",
        "Fetch a public web page and return its visible text. Takes a url argument. Requires web access to be enabled.",
        fetch_url,
    )

    return registry


if __name__ == "__main__":
    registry = create_registry()

    print("Available tools:")
    for tool in registry.list_tools():
        print(f"- {tool['name']}: {tool['description']}")
