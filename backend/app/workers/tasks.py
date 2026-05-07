from dataclasses import dataclass
from datetime import datetime


@dataclass
class QueuedTask:
    task_type: str
    payload: dict
    queued_at: datetime


def enqueue_scenario_run(payload: dict) -> QueuedTask:
    return QueuedTask(task_type="scenario_run", payload=payload, queued_at=datetime.utcnow())


def enqueue_prediction_job(payload: dict) -> QueuedTask:
    return QueuedTask(task_type="prediction_job", payload=payload, queued_at=datetime.utcnow())
