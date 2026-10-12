"""Write docs/openapi.json.  Run from the backend folder:  python -m scripts.export_openapi"""

import json

from app.config import ROOT
from app.main import app

out = ROOT / "docs" / "openapi.json"
out.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
print(f"Wrote {out}")
