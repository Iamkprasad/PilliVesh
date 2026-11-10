class ToolSelector:

    def select(self, task, available_tools, use_web=False):
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

        if use_web and any(word in task for word in [
            "web",
            "website",
            "url",
            "fetch",
            "browse",
            "search",
            "news",
            "online",
        ]):
            if "web_fetch" in available_tools:
                return "web_fetch"

        return None


if __name__ == "__main__":
    selector = ToolSelector()

    print(
        selector.select(
            "Check GPU and RAM performance",
            ["system_info"],
        )
    )
