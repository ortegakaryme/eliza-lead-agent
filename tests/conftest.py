import os

# Settings are read at import time, so test values must exist before app.main is imported.
os.environ.setdefault("NOTION_API_KEY", "secret_test_key_123")
os.environ.setdefault("NOTION_DATABASE_ID", "00000000000000000000000000000000")
os.environ.setdefault("WEBHOOK_SECRET", "test-webhook-secret-123456")
