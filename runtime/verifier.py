from runtime.execution import ExecutionResult


def verify(result: ExecutionResult):
    if not result.success:
        return False, "Execution failed."

    if not result.output:
        return False, "Execution produced no output."

    if not result.verified:
        return False, "Execution completed but was not verified."

    return True, "Execution verified successfully."


if __name__ == "__main__":
    result = ExecutionResult(
        success=True,
        output="test completed",
        verified=True,
    )

    ok, message = verify(result)

    print(ok)
    print(message)
