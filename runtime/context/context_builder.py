from runtime.memory.memory_manager import build_context
from runtime.state.task_manager import active_tasks
from runtime.skills.skill_loader import load_skill


def build(task, project=None, skill=None, memory_chars=3000):
    parts = []

    parts.append("## CURRENT TASK")
    parts.append(task)

    if project:
        tasks = active_tasks(project)

        if tasks:
            parts.append("\n## ACTIVE PROJECT STATE")
            for item in tasks:
                parts.append(f"- {item[1]}")

    if skill:
        parts.append("\n## ACTIVE SKILL")
        parts.append(load_skill(skill))

    memory = build_context(task, max_chars=memory_chars)

    if memory:
        parts.append("\n## RELEVANT MEMORY")
        parts.append(memory)

    return "\n".join(parts)


if __name__ == "__main__":
    print(build(
        "Optimize GPU inference",
        project="local-ai-runtime",
        skill="coding"
    ))
