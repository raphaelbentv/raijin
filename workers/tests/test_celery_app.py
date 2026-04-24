from app.celery_app import celery_app, ping


def test_celery_app_configured() -> None:
    assert celery_app.main == "raijin"
    assert celery_app.conf.task_serializer == "json"


def test_ping_task_callable() -> None:
    assert ping() == "pong"
