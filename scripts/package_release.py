"""Package reviewed app sources, never a local database or private environment.

This creates an upload artifact; it neither builds nor deploys the application.
Build dependencies and generated frontend assets on the target release directory.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import subprocess
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "tafolliboost-release"
ROOT_FILES = {
    "Dockerfile",
    ".dockerignore",
    ".env.example",
    ".env.production.example",
    "requirements.txt",
    "package.json",
    "package-lock.json",
    "compose.yml",
    "compose.production.yml",
    "README.md",
    "LICENSE",
}
NEW_REVIEWED_FILES = {"scripts/package_release.py", "docs/deploy/DREAMHOST.md", "docs/deploy/BACKUPS.md"}
BLOCKED_PARTS = {
    ".git",
    "data",
    "node_modules",
    ".venv",
    "venv",
    ".review-venv",
    "__pycache__",
    "tests",
    "build",
    "_site",
    "android",
    "ios",
}
TEXT_SUFFIXES = {
    ".py",
    ".js",
    ".mjs",
    ".css",
    ".html",
    ".json",
    ".txt",
    ".md",
    ".yml",
    ".webmanifest",
    ".svg",
}
SECRET_PATTERNS = (
    re.compile(rb"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}"),
    re.compile(rb"\b(?:[sr]k_(?:live|test)_|whsec_)[A-Za-z0-9]{20,}"),
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"),
)


def allowed_source(name: str) -> bool:
    """Allow only known deployable source families, not arbitrary repo files."""
    path = PurePosixPath(name)
    if (
        not path.parts
        or path.is_absolute()
        or ".." in path.parts
        or set(path.parts) & BLOCKED_PARTS
    ):
        return False
    if name in ROOT_FILES or name in NEW_REVIEWED_FILES:
        return True
    if any(part.startswith(".") for part in path.parts):
        return False
    if path.suffix in {".db", ".sqlite", ".sqlite3", ".pyc", ".pem", ".key", ".p12", ".pfx"}:
        return False
    if path.parts[0] == "backend":
        return path.suffix == ".py"
    if path.parts[0] == "frontend":
        if len(path.parts) == 2:
            return path.name in {"index.html", "admin.html"}
        return path.parts[1] in {"js", "css", "content", "public"} and path.suffix in TEXT_SUFFIXES
    if path.parts[0] == "static":
        return (
            path.suffix in {".json", ".svg", ".png", ".jpg", ".mp4", ".vtt", ".ttf", ".txt", ".md", ".traineddata"}
            or path.name == "LICENSE"
        )
    if path.parts[0] == "prompts":
        return path.suffix in {".txt", ".md"}
    if path.parts[0] == "scripts":
        return path.name in {"build_pages.py", "bundle_pages.mjs", "package_release.py"}
    if path.parts[0] == "deploy":
        return name == "deploy/Caddyfile"
    return name in {"docs/product/HOSTED-OPENAI.md", "docs/product/ADMIN.md", "docs/product/BILLING.md"}


def check_content(name: str, data: bytes) -> None:
    """Abort without echoing suspected credentials or file contents."""
    if any(pattern.search(data) for pattern in SECRET_PATTERNS):
        raise ValueError("Release aborted: a source file contains a possible secret.")
    if name in {".env.example", ".env.production.example"}:
        for line in data.decode("utf-8").splitlines():
            assignment = re.match(r"^([A-Z][A-Z0-9_]*)(?:\s*)=(.*)$", line.strip())
            if not assignment:
                continue
            key, value = assignment.groups()
            if key.endswith(
                ("_API_KEY", "_CLIENT_SECRET", "_SECRET_KEY", "_WEBHOOK_SECRET", "_PASSWORD", "_TOKEN")
            ) and value.strip().strip("\"'"):
                raise ValueError(
                    "Release aborted: an environment example has a nonempty secret field."
                )


def source_files(root: Path) -> list[tuple[str, bytes]]:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True)
    names = {item.decode("utf-8") for item in result.stdout.split(b"\0") if item}
    names |= {name for name in NEW_REVIEWED_FILES if (root / name).exists()}
    files = []
    for name in sorted(names):
        if not allowed_source(name):
            continue
        path = root / name
        source_parts = PurePosixPath(name).parts
        if path.is_symlink() or any(
            (root / Path(*source_parts[:i])).is_symlink() for i in range(1, len(source_parts))
        ):
            raise ValueError("Release aborted: source symlinks are not permitted.")
        if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(
                "Release aborted: an expected source file is missing or outside the repository."
            )
        data = path.read_bytes()
        check_content(name, data)
        files.append((name, data))
    required = {
        "backend/main.py",
        "backend/services/legal_service.py",
        "frontend/index.html",
        "scripts/build_pages.py",
        "scripts/bundle_pages.mjs",
        "package-lock.json",
        "requirements.txt",
        "Dockerfile",
        "static/branding.json",
        "deploy/Caddyfile",
    }
    if not required.issubset({name for name, _ in files}):
        raise ValueError("Release aborted: required application sources are missing.")
    return files


def add_file(archive: tarfile.TarFile, name: str, data: bytes) -> None:
    member = tarfile.TarInfo(f"{PREFIX}/{name}")
    member.size = len(data)
    member.mode = 0o644
    member.mtime = 0
    member.uid = member.gid = 0
    archive.addfile(member, io.BytesIO(data))


def package(root: Path, output: Path) -> int:
    files = source_files(root)
    manifest = {
        "format": 1,
        "artifact": "source-only; build frontend and install runtime dependencies before starting",
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in files},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves any earlier release artifact.
    with output.open("xb") as target:
        with gzip.GzipFile(fileobj=target, mode="wb", mtime=0, filename="") as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for name, data in files:
                    add_file(archive, name, data)
                add_file(
                    archive,
                    "RELEASE-MANIFEST.json",
                    json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
                )
    return len(files)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="New .tar.gz source artifact path; never overwritten",
    )
    args = parser.parse_args()
    if not str(args.output).endswith(".tar.gz"):
        parser.error("--output must end in .tar.gz")
    try:
        count = package(ROOT, args.output.expanduser().resolve())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")
    print(
        f"Source release created with {count} files. No generated build, database or private environment was included."
    )


if __name__ == "__main__":
    main()
