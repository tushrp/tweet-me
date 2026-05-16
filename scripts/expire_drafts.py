import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import storage

expired = storage.mark_expired_drafts()
print(f"expired {expired} draft(s)")
