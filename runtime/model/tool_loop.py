import json


class ToolRequest:

    def __init__(self, tool, arguments=None):
        self.tool = tool
        self.arguments = arguments or {}

    def to_dict(self):
        return {
            "tool": self.tool,
            "arguments": self.arguments,
        }


def parse_tool_request(text):
    try:
        data = json.loads(text)

        if not isinstance(data, dict):
            return None

        if "tool" not in data:
            return None

        return ToolRequest(
            data["tool"],
            data.get("arguments", {}),
        )

    except Exception:
        return None


if __name__ == "__main__":
    request = parse_tool_request(
        '{"tool": "system_info", "arguments": {}}'
    )

    if request:
        print("Tool:", request.tool)
        print("Arguments:", request.arguments)
        print("Valid: True")
    else:
        print("Valid: False")
