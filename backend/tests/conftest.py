import os
import sys

# Ensure backend root is in sys.path
backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

# Direct all test runs to an isolated test database so tests NEVER drop or wipe the development database
TEST_DB_PATH = os.path.join(backend_root, "data", "test_declinedoctor.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
