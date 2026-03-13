from pathlib import Path
import re
import sys


ENV_PATH = Path(__file__).resolve().parent / ".env"
TARGET_KEY = "ENV_TARGET"
TARGET_VALUE = "LIVE"


def main() -> int:
    if not ENV_PATH.exists():
        print(f"Missing .env file: {ENV_PATH}")
        return 1

    content = ENV_PATH.read_text(encoding="utf-8")
    pattern = rf"(?m)^(\s*{re.escape(TARGET_KEY)}\s*=\s*).*$"

    if re.search(pattern, content):
        updated = re.sub(pattern, rf"\1{TARGET_VALUE}", content, count=1)
    else:
        newline = "\n" if content and not content.endswith(("\n", "\r")) else ""
        updated = f"{content}{newline}{TARGET_KEY}={TARGET_VALUE}\n"

    if updated == content:
        print(f"{TARGET_KEY} is already set to {TARGET_VALUE}.")
        return 0

    ENV_PATH.write_text(updated, encoding="utf-8")
    print(f"Updated {ENV_PATH.name}: {TARGET_KEY}={TARGET_VALUE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
