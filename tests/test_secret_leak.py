"""Tests verifying zero secrets or credentials exist in the public repository."""

from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parent.parent

EXCLUDED_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "venv"}

SUSPICIOUS_PATTERNS = [
    # Google AI API Key prefix
    (re.compile(r"AIza[0-9A-Za-z-_]{35}"), "Google API Key"),
    # Database connection strings with credentials
    (re.compile(r"postgres(ql)?(\+[^:]+)?:\/\/[^:]+:[^@]+@"), "PostgreSQL credentials"),
    # Gemini API Key with actual value
    (re.compile(r"GEMINI_API_KEY\s*=\s*['\"][a-zA-Z0-9_\-]{10,}['\"]"), "Gemini API key assignment"),
    # Real ingest token definition
    (re.compile(r"MONITOR_INGEST_TOKEN\s*[:=]\s*['\"][^'\"\s]+['\"]"), "Monitor ingest token assignment"),
    # Potential private keys or certs
    (re.compile(r"-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----"), "Private key"),
]


def get_repo_files() -> list[Path]:
    """Gather all repository files, skipping internal cache and venv folders."""
    files = []
    for item in REPO_ROOT.rglob("*"):
        if item.is_file():
            if any(part in EXCLUDED_DIRS for part in item.parts):
                continue
            files.append(item)
    return files


def test_no_secrets_in_repo_files():
    """Ensure no file in the repo contains real tokens, secrets, or connection strings."""
    files = get_repo_files()
    assert len(files) > 0, "No files found in repo to inspect"

    findings = []
    current_file = Path(__file__).resolve()
    for f in files:
        # Skip the test file itself to prevent regex definitions from triggering false positives
        if f.resolve() == current_file:
            continue

        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        for pat, desc in SUSPICIOUS_PATTERNS:
            match = pat.search(content)
            if match:
                findings.append(f"{desc} match found in {f.relative_to(REPO_ROOT)}: {match.group(0)[:15]}...")

    assert not findings, f"Potential secrets detected:\n" + "\n".join(findings)


def test_gitignore_covers_sensitive_files():
    """Verify .gitignore properly excludes secrets.toml and .env files."""
    gitignore_path = REPO_ROOT / ".gitignore"
    assert gitignore_path.exists(), ".gitignore must exist"

    content = gitignore_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]

    assert ".streamlit/secrets.toml" in lines or "*.toml" in lines
    assert ".env" in lines


def test_secrets_toml_not_tracked_or_present():
    """Ensure .streamlit/secrets.toml is not committed to the repo."""
    secrets_file = REPO_ROOT / ".streamlit" / "secrets.toml"
    assert not secrets_file.exists(), ".streamlit/secrets.toml must NOT exist in the public repository"


def test_example_files_contain_only_placeholders():
    """Verify .streamlit/secrets.toml.example and .env.example contain only placeholders."""
    secrets_example = REPO_ROOT / ".streamlit" / "secrets.toml.example"
    assert secrets_example.exists()
    content = secrets_example.read_text(encoding="utf-8")

    assert "replace-me" in content
    assert "https://your-monitor-api.example.com" in content

    env_example = REPO_ROOT / ".env.example"
    assert env_example.exists()
    env_content = env_example.read_text(encoding="utf-8")

    assert "replace-me" in env_content
