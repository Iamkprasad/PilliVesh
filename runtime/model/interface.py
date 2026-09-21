from runtime.model.adapter import ModelAdapter


class ModelInterface:

    def __init__(self, model_path=None):
        self.adapter = ModelAdapter(model_path)

    def build_prompt(self, task, context):
        return (
            "You are the local AI assistant.\n\n"
            "Use the provided context, skills, memory and task state "
            "to solve the user's task.\n\n"
            "## TASK\n"
            f"{task}\n\n"
            "## CONTEXT\n"
            f"{context}\n"
        )

    def run(self, task, context):
        prompt = self.build_prompt(task, context)
        return self.adapter.generate(prompt)


if __name__ == "__main__":
    interface = ModelInterface()

    response = interface.run(
        "Check the current system",
        "CPU: 8 cores\nGPU: Adreno 650\nRAM available: 2.4 GiB",
    )

    print("Model:", response.model)
    print("Response:", response.text)
    print("Success:", response.success)
