import pytest
from jobs.task import celery  # Your celery app

@pytest.fixture(autouse=True, scope="session")
def configure_celery():
    celery.conf.task_always_eager = True
    celery.conf.task_eager_propagates = True  # Raise exceptions during test