from dataclasses import dataclass
from typing import Optional


@dataclass
class ExecutionResult:
    success: bool
    output: str = ""
    error: str = ""
    verified: bool = False

    def summary(self):
        if self.success and self.verified:
            return "SUCCESS: action completed and verified."

        if self.success:
            return "COMPLETED: action finished but verification is pending."

        return f"FAILED: {self.error}"


if __name__ == "__main__":
    result = ExecutionResult(
        success=True,
        output="Test completed.",
        verified=True
    )

    print(result.summary())
