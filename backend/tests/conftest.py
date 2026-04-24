import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://raijin:raijin@localhost:5432/raijin")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/1")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
os.environ.setdefault("S3_ENDPOINT_URL", "http://localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY", "test")
os.environ.setdefault("S3_SECRET_KEY", "test_secret")
os.environ.setdefault("S3_BUCKET_INVOICES", "test-invoices")
os.environ.setdefault("JWT_SECRET", "test_secret_" + "x" * 32)
