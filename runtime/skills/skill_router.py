from runtime.skills.skill_loader import list_skills


class SkillRouter:

    KEYWORDS = {
        "coding": [
            "code", "program", "script", "function",
            "python", "javascript", "bug", "implement"
        ],
        "debugging": [
            "error", "debug", "broken", "failure",
            "traceback", "fix"
        ],
        "linux": [
            "linux", "termux", "shell", "terminal",
            "process", "cpu", "memory", "filesystem"
        ],
        "research": [
            "research", "find", "compare", "investigate",
            "source", "information"
        ],
        "planning": [
            "plan", "roadmap", "steps", "architecture",
            "design"
        ],
        "reasoning": [
            "analyze", "reason", "logic", "why",
            "evaluate", "deduce"
        ],
    }

    def select(self, task):
        task = task.lower()
        available = set(list_skills())

        scores = {}

        for skill, keywords in self.KEYWORDS.items():
            if skill not in available:
                continue

            score = sum(
                1 for keyword in keywords
                if keyword in task
            )

            if score:
                scores[skill] = score

        if not scores:
            return None

        return max(scores, key=scores.get)


if __name__ == "__main__":
    router = SkillRouter()

    tests = [
        "Fix this Python error",
        "Check Termux CPU usage",
        "Research Vulkan performance",
        "Create a project roadmap",
    ]

    for task in tests:
        print(task, "->", router.select(task))
