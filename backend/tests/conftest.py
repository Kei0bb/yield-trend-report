import os

# Force mock mode for the whole test session (no Oracle needed).
os.environ.setdefault("USE_MOCK_DATA", "true")
