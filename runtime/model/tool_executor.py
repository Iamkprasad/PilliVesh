from runtime.model.tool_loop import parse_tool_request
from runtime.tools.default_tools import create_registry
from runtime.execution import ExecutionResult
from runtime.verifier import verify
from runtime.memory.memory_manager import remember_episode


class ToolExecutor:

    def __init__(self):
        self.registry = create_registry()

    def _validate_arguments(self, tool_name, arguments, use_web=False):
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

        # file_read requires a path argument.
        if tool_name == "file_read":
            if not isinstance(arguments, dict) or not arguments.get("path"):
                return False, "file_read requires a path argument"

        # list_dir takes an optional path argument.
        if tool_name == "list_dir":
            if not isinstance(arguments, dict):
                return False, "list_dir arguments must be an object"

        # web_fetch requires web access enabled and a url argument.
        if tool_name == "web_fetch":
            if not use_web:
                return False, "Web access is disabled. Enable it in Settings → Assistant."
            if not arguments.get("url"):
                return False, "web_fetch requires a url argument"

        return True, None

    def execute(self, model_output, use_web=False):
        request = parse_tool_request(model_output)

        if not request:
            return {
                "success": False,
                "message": "No valid tool request.",
            }

        ok, error = self._validate_arguments(request.tool, request.arguments, use_web)
        if not ok:
            return {"success": False, "tool": request.tool, "message": error}

        tool = self.registry.get(request.tool)
        if not tool:
            return {"success": False, "tool": request.tool, "message": f"Unknown tool: {request.tool}"}

        try:
            output = tool.handler(**request.arguments)

            # Tools that return (result, error) tuples surface errors in the
            # second element — treat those as failures.
            if isinstance(output, tuple) and len(output) == 2 and output[1]:
                result = ExecutionResult(
                    success=False,
                    output=output[0],
                    error=str(output[1]),
                    verified=False,
                )
                verified, message = False, str(output[1])
            else:
                result = ExecutionResult(
                    success=True,
                    output=output,
                    verified=True,
                )
                verified, message = verify(result)

            # Record the verified tool episode as a memory so the memory
            # panel is not empty on first use.
            try:
                remember_episode(request.tool, request.tool, output, verified)
            except Exception:
                pass

            return {
                "success": result.success,
                "tool": request.tool,
                "output": output,
                "message": message if not result.success else None,
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
