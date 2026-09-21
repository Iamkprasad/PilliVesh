from runtime.context.context_builder import build
from runtime.memory.memory_manager import remember_episode
from runtime.skills.skill_router import SkillRouter
from runtime.tools.default_tools import create_registry
from runtime.tools.selector import ToolSelector
from runtime.execution import ExecutionResult
from runtime.verifier import verify


class Orchestrator:

    def __init__(self):
        self.tools = create_registry()
        self.selector = ToolSelector()
        self.skill_router = SkillRouter()

    def prepare(self, task, project=None, skill=None):
        context = build(
            task=task,
            project=project,
            skill=skill,
        )

        return {
            "task": task,
            "project": project,
            "skill": skill,
            "context": context,
        }

    def run_tool(self, tool_name):
        tool = self.tools.get(tool_name)

        if not tool:
            return ExecutionResult(
                success=False,
                error=f"Tool not found: {tool_name}",
            )

        try:
            output = tool.handler()

            return ExecutionResult(
                success=True,
                output=output,
                verified=True,
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=str(e),
            )

    def run(self, task):
        skill = self.skill_router.select(task)
        context = self.prepare(task, skill=skill)

        tool_names = [
            tool["name"]
            for tool in self.tools.list_tools()
        ]

        selected = self.selector.select(
            task,
            tool_names,
        )

        if not selected:
            return {
                "success": False,
                "skill": skill,
                "tool": None,
                "message": "No suitable tool found.",
            }

        result = self.run_tool(selected)

        verified, message = verify(result)

        remember_episode(
            task, selected, result.output, verified
        )

        return {
            "success": result.success,
            "tool": selected,
            "skill": skill,
            "output": result.output,
            "verified": verified,
            "verification": message,
        }


if __name__ == "__main__":
    runtime = Orchestrator()

    result = runtime.run(
        "Check the current GPU and RAM"
    )

    print("=== SELECTED TOOL ===")
    print(result["tool"])

    print("\n=== RESULT ===")
    print(result["output"])

    print("\n=== VERIFICATION ===")
    print(result["verified"])
    print(result["verification"])
