from runtime.model.tool_loop import parse_tool_request
from runtime.tools.default_tools import create_registry
from runtime.execution import ExecutionResult
from runtime.verifier import verify


class ToolExecutor:

    def __init__(self):
        self.registry = create_registry()

    def _validate_arguments(self, tool_name, arguments):
        """Strict argument validation. Returns (ok, error_message)."""
        if not isinstance(arguments, dict):
            return False, "arguments must be an object"

        tool = self.registry.get(tool_name)
        if tool is None:
            return False, f"Unknown tool: {tool_name}"

        # system_info takes no arguments — strict allow-list.
        if tool_name == "system_info":
            if arguments:
                return False, "system_info takes no arguments"

        return True, None

    def execute(self, model_output):
        request = parse_tool_request(model_output)

        if not request:
            return {
                "success": False,
                "message": "No valid tool request.",
            }

        ok, error = self._validate_arguments(request.tool, request.arguments)
        if not ok:
            return {"success": False, "tool": request.tool, "message": error}

        tool = self.registry.get(request.tool)
        if not tool:
            return {"success": False, "tool": request.tool, "message": f"Unknown tool: {request.tool}"}

        try:
            output = tool.handler()

            result = ExecutionResult(
                success=True,
                output=output,
                verified=True,
            )

            verified, message = verify(result)

            return {
                "success": result.success,
                "tool": request.tool,
                "output": output,
                "verified": verified,
                "verification": message,
            }

        except Exception as e:
            return {
                "success": False,
                "tool": request.tool,
                "message": str(e),
            }


if __name__ == "__main__":
    executor = ToolExecutor()

    result = executor.execute(
        '{"tool": "system_info", "arguments": {}}'
    )

    print("=== TOOL ===")
    print(result["tool"])

    print("=== VERIFIED ===")
    print(result["verified"])

    print("=== RESULT ===")
    print(result["output"])
