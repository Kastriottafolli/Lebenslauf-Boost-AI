"""Isolate untrusted PDF/DOCX parsers with time and memory limits."""

import base64
import json
import subprocess
import sys


def extract(filename, data):
    try:
        result = subprocess.run(
            [sys.executable, "-m", "backend.services.safe_extraction", filename],
            input=data,
            capture_output=True,
            timeout=20,
            check=False,
        )
        if result.returncode != 0:
            raise ValueError(
                "Datei kann nicht sicher gelesen werden. Bitte TXT/DOCX verwenden / unable to read safely; try text."
            )
        value = json.loads(result.stdout)
        if "error" in value:
            raise ValueError(value["error"])
        return value["text"], value.get("photo")
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        raise ValueError(
            "Datei-Verarbeitung abgebrochen / file processing timed out. Bitte Text einfügen."
        ) from None


def main():
    import resource

    from backend.services import extraction_service

    resource.setrlimit(resource.RLIMIT_CPU, (12, 12))
    if sys.platform == "linux":
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    data = sys.stdin.buffer.read(10 * 1024 * 1024 + 1)
    try:
        text = extraction_service.extract_text(sys.argv[1], data)
        photo = extraction_service.extract_photo(sys.argv[1], data)
        value = {
            "text": text,
            "photo": "data:image/jpeg;base64," + base64.b64encode(photo).decode()
            if photo
            else None,
        }
    except (
        Exception
    ):  # Untrusted decoder errors are intentionally redacted at this process boundary.
        value = {
            "error": "Datei nicht lesbar, zu groß oder nicht unterstützt / file unreadable, too large or unsupported."
        }
    sys.stdout.write(json.dumps(value, ensure_ascii=False))


if __name__ == "__main__":
    main()
