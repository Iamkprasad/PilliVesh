class ToolSelector:

    def select(self, task, available_tools):
        task = task.lower()

        if any(word in task for word in [
            "system",
            "hardware",
            "cpu",
            "ram",
            "memory",
            "gpu",
            "vulkan",
            "performance",
        ]):
            if "system_info" in available_tools:
                return "system_info"

        return None


if __name__ == "__main__":
    selector = ToolSelector()

    print(
        selector.select(
            "Check GPU and RAM performance",
            ["system_info"],
        )
    )
