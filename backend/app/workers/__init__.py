"""
Worker module reserved for future asynchronous execution.

Current strategy:
- the API creates a ScenarioRun with status "queued"
- the service immediately promotes it to "processing"
- the same controlled flow finalizes it as "completed" or "failed"

This keeps the execution deterministic and easy to validate in local
and development environments, while preserving a clear path to an
async worker architecture later.
"""

__all__: list[str] = []