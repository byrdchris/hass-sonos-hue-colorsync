
import pathlib

required = ["README.md", "PROJECT_STATE.md", "CHANGELOG.md"]

missing = []
for f in required:
    if not pathlib.Path(f).exists():
        missing.append(f)

if missing:
    raise SystemExit(f"Missing docs: {missing}")

print("docs_ok")
