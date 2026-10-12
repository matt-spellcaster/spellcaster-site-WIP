"""Check that every package version a change adds to package-lock.json is old enough.

    python3 scripts/ci/check_release_age.py <base package-lock.json> [package-lock.json]

.npmrc's min-release-age only applies when npm resolves versions (install, update). npm ci
installs the lockfile as written, and Dependabot's cooldown skips security updates, so a
lockfile can still pin a release younger than the rule allows. This compares the lockfile
with the base branch's and asks the registry when each added (name, version) was published.
It fails on any release younger than min-release-age days, and on any it can't date.
Reads .npmrc from the lockfile's folder. Standard library only.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

REGISTRY = "https://registry.npmjs.org/"


def locked(lock: dict) -> set[tuple[str, str]]:
    """(name, version) for every package in a lockfile, the root project left out."""
    pairs = set()
    for path, pkg in lock.get("packages", {}).items():
        if path:
            pairs.add((pkg.get("name", path.rsplit("node_modules/", 1)[-1]), str(pkg.get("version", ""))))
    return pairs


def min_days(npmrc: str) -> int:
    for line in npmrc.splitlines():
        key, _, value = line.partition("=")
        if key.strip() == "min-release-age":
            return int(value.strip())
    raise ValueError(".npmrc sets no min-release-age")


def publish_times(name: str) -> dict[str, str]:
    """The registry's {version: ISO time} for a package."""
    url = REGISTRY + urllib.parse.quote(name, safe="@")
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp).get("time", {})


def problems(base: dict, head: dict, days: int, now: datetime,
             times: Callable[[str], dict[str, str]] | None = None) -> tuple[list[str], int]:
    """Problems with the added releases, and how many were added."""
    times = times or publish_times
    added = sorted(locked(head) - locked(base))
    found = []
    cache: dict[str, dict[str, str]] = {}
    for name, version in added:
        try:
            if name not in cache:
                cache[name] = times(name)
            published = datetime.fromisoformat(cache[name][version].replace("Z", "+00:00"))
        except Exception as e:  # noqa: BLE001 - any failure to date a release fails the check
            found.append(f"{name}@{version}: couldn't read its publish time ({e!r})")
            continue
        age = now - published
        if age < timedelta(days=days):
            found.append(f"{name}@{version}: published {published:%Y-%m-%d %H:%M} UTC, "
                         f"{age.total_seconds() / 86400:.1f} days ago (needs {days})")
    return found, len(added)


def main(argv: list[str] | None = None, now: datetime | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: check_release_age.py <base package-lock.json> [package-lock.json]")
        return 2
    path = Path(argv[1] if len(argv) > 1 else "package-lock.json")
    base = json.loads(Path(argv[0]).read_text())
    head = json.loads(path.read_text())
    days = min_days((path.parent / ".npmrc").read_text())
    found, count = problems(base, head, days, now or datetime.now(timezone.utc))
    for line in found:
        print(line)
    print(f"{len(found)} problems in {count} added releases (each must be at least {days} days old)")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
