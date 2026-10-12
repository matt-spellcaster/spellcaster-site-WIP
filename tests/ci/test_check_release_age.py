"""check_release_age: every release a change adds to the lockfile must be min-release-age days old."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "ci"))

import check_release_age
from check_release_age import locked, min_days, problems

NOW = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)
TIMES = {
    "astro": {"7.3.3": "2026-09-01T00:00:00.000Z", "7.3.4": "2026-10-10T12:00:00.000Z"},
    "@img/sharp-linux-x64": {"0.35.5": "2026-10-05T11:59:00.000Z"},
    "devalue": {"5.9.4": "2026-10-05T12:00:00.000Z"},
}


def lock(*pairs):
    packages = {"": {"name": "site"}}
    for name, version in pairs:
        packages[f"node_modules/{name}"] = {"version": version}
    return {"lockfileVersion": 3, "packages": packages}


def check(base, head, times=TIMES.get):
    return problems(base, head, 7, NOW, times)


class Locked(unittest.TestCase):
    def test_names_from_paths_and_aliases(self):
        data = lock(("astro", "7.3.3"))
        data["packages"]["node_modules/a/node_modules/@s/b"] = {"version": "1.0.0"}
        data["packages"]["node_modules/string-width-cjs"] = {"name": "string-width", "version": "4.2.3"}
        self.assertEqual(locked(data), {("astro", "7.3.3"), ("@s/b", "1.0.0"), ("string-width", "4.2.3")})


class Problems(unittest.TestCase):
    def test_only_added_releases_are_checked(self):
        def times(name):
            raise AssertionError(f"looked up {name}")
        self.assertEqual(check(lock(("astro", "7.3.4")), lock(("astro", "7.3.4")), times), ([], 0))
        self.assertEqual(check(lock(("astro", "7.3.4"), ("devalue", "5.9.4")), lock(("astro", "7.3.4")), times),
                         ([], 0))

    def test_old_enough_passes(self):
        # Exactly 7 days is old enough, as npm counts it.
        self.assertEqual(check(lock(("astro", "7.3.3")), lock(("astro", "7.3.3"), ("devalue", "5.9.4"))), ([], 1))

    def test_too_new_fails(self):
        found, count = check(lock(("astro", "7.3.3"), ("@img/sharp-linux-x64", "0.35.5")),
                             lock(("astro", "7.3.4"), ("@img/sharp-linux-x64", "0.35.5")))
        self.assertEqual(count, 1)
        self.assertEqual(found, ["astro@7.3.4: published 2026-10-10 12:00 UTC, 2.0 days ago (needs 7)"])

    def test_threshold_and_scoped_names(self):
        found, _ = check(lock(), lock(("@img/sharp-linux-x64", "0.35.5"), ("devalue", "5.9.4")))
        self.assertEqual(len(found), 0)
        found, _ = problems(lock(), lock(("@img/sharp-linux-x64", "0.35.5")), 8, NOW, TIMES.get)
        self.assertEqual(found, ["@img/sharp-linux-x64@0.35.5: published 2026-10-05 11:59 UTC, "
                                 "7.0 days ago (needs 8)"])

    def test_undatable_release_fails(self):
        def offline(name):
            raise OSError("no network")
        for label, head, times in (("unknown version", lock(("astro", "9.9.9")), TIMES.get),
                                   ("unknown package", lock(("nope", "1.0.0")), lambda name: {}),
                                   ("registry error", lock(("astro", "7.3.3")), offline)):
            with self.subTest(label):
                found, _ = check(lock(), head, times)
                self.assertEqual(len(found), 1)
                self.assertIn("couldn't read its publish time", found[0])

    def test_each_package_is_looked_up_once(self):
        calls = []

        def times(name):
            calls.append(name)
            return TIMES[name]
        check(lock(), {"packages": {"node_modules/astro": {"version": "7.3.3"},
                                    "node_modules/x/node_modules/astro": {"version": "7.3.4"}}}, times)
        self.assertEqual(calls, ["astro"])


class MinDays(unittest.TestCase):
    def test_reads_npmrc(self):
        self.assertEqual(min_days("# c\nignore-scripts=true\nmin-release-age = 7\n"), 7)
        with self.assertRaises(ValueError):
            min_days("ignore-scripts=true\n")

    def test_the_real_npmrc(self):
        repo = Path(__file__).resolve().parents[2]
        self.assertGreaterEqual(min_days((repo / ".npmrc").read_text()), 7)


class Main(unittest.TestCase):
    def run_main(self, base, head):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "base.json").write_text(json.dumps(base))
            (Path(tmp) / "package-lock.json").write_text(json.dumps(head))
            (Path(tmp) / ".npmrc").write_text("min-release-age=7\n")
            with (mock.patch.object(check_release_age, "publish_times", TIMES.get),
                  contextlib.redirect_stdout(io.StringIO()) as out):
                code = check_release_age.main([str(Path(tmp) / "base.json"), str(Path(tmp) / "package-lock.json")],
                                              now=NOW)
        return code, out.getvalue()

    def test_exit_codes(self):
        code, out = self.run_main(lock(), lock(("astro", "7.3.3")))
        self.assertEqual(code, 0)
        self.assertIn("0 problems in 1 added releases (each must be at least 7 days old)", out)
        code, out = self.run_main(lock(), lock(("astro", "7.3.4")))
        self.assertEqual(code, 1)
        self.assertIn("1 problems in 1 added releases", out)

    def test_no_arguments(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(check_release_age.main([]), 2)


if __name__ == "__main__":
    unittest.main()
