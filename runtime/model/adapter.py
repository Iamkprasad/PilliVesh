class ModelResponse:
    def __init__(self, text, model="dummy", success=True):
        self.text = text
        self.model = model
        self.success = success


class ModelAdapter:
    def __init__(self, model_path=None):
        self.model_path = model_path

    def generate(self, prompt):
        if self.model_path is None:
            return ModelResponse(
                "[MODEL NOT INSTALLED] Adapter is working."
            )

        raise NotImplementedError(
            "Local model backend is not connected yet."
        )


if __name__ == "__main__":
    adapter = ModelAdapter()

    response = adapter.generate(
        "Test the model interface."
    )

    print("Model:", response.model)
    print("Response:", response.text)
    print("Success:", response.success)
