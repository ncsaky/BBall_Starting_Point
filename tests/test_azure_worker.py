"""The Azure worker script switches machines off after failures and copies only changed files (no Azure needed)."""
import argparse
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SPEC = importlib.util.spec_from_file_location(
    "azure_worker", Path(__file__).resolve().parents[1] / "scripts" / "azure_worker.py")
azure = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(azure)

CONFIG = {"resource_group": "group", "vm": "machine", "host": "host", "user": "user", "key": "key",
          "monthly_hour_cap": 300}


class SwitchOffTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.dir = Path(folder.name)
        (self.dir / "config.json").write_text(json.dumps(CONFIG))
        self.state = "VM deallocated"
        self.running = []          # job names marked as running on the fake machine
        self.fail = set()          # steps that raise: start, copy, launch, fetch, reach
        self.stops = 0
        self.commands = []
        self.exit_code = "0"
        for name, value in {"CONFIG": self.dir / "config.json", "LEDGER": self.dir / "ledger.json",
                            "CLAIMS": self.dir / "claims", "power_state": lambda worker: self.state,
                            "sh": self.fake_sh, "start": self.fake_start,
                            "exit_on_termination": lambda: None, "ignore_interrupts": lambda: None}.items():
            patcher = mock.patch.object(azure, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(azure.time, "sleep", lambda seconds: None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def fake_start(self, worker, force_budget=False):
        self.state = "VM running"
        if "start" in self.fail:
            raise RuntimeError("worker started but SSH never answered")

    def fake_sh(self, args, check=True, capture=True):
        line = " ".join(args)
        self.commands.append(line)
        failed, out = False, ""
        if args[0] == "az":
            self.assertIn("deallocate", args)
            self.stops += 1
            self.state = "VM deallocated"
        elif args[0] == "rsync":
            if "--link-dest=../../base" in args:
                failed = "copy" in self.fail
            else:
                failed = "fetch" in self.fail and not line.split()[-2].endswith("run.log")
        elif args[-1] == azure.RUNNING_JOBS:
            failed, out = "reach" in self.fail, "\n".join(self.running)
        elif "nohup" in args[-1]:
            failed = "launch" in self.fail
        elif "cat EXIT_CODE" in args[-1]:
            out = self.exit_code
        if failed and check:
            raise RuntimeError("connection closed by remote host")
        return "" if failed else out

    def run_job(self, **options):
        args = argparse.Namespace(**{"name": "job", "dir": str(self.dir), "command": ["true"], "fetch": [], "tail": 5,
                                     "keep": False, "keep_on": False, "progress": False, "force_budget": False,
                                     "worker": None, **options})
        with contextlib.redirect_stdout(io.StringIO()):
            return azure.run(azure.config(), args)

    def assert_off_and_released(self):
        self.assertEqual((self.stops, self.state), (1, "VM deallocated"))
        self.assertEqual(list((self.dir / "claims").glob("*.json")), [])

    def removed_job_folder(self):
        return any("rm -rf runs/job" in line for line in self.commands)

    def test_success_switches_off(self):
        self.assertEqual(self.run_job(), 0)
        self.assert_off_and_released()
        self.assertTrue(self.removed_job_folder())

    def test_failed_start_copy_or_launch_switches_off(self):
        for step in ("start", "copy", "launch"):
            with self.subTest(step=step):
                self.state, self.fail, self.stops = "VM deallocated", {step}, 0
                with self.assertRaises(RuntimeError):
                    self.run_job(keep_on=True)          # --keep-on does not apply to a failed job
                self.assert_off_and_released()

    def test_interrupted_job_switches_off_and_clears_its_marker(self):
        self.running = ["job"]
        with mock.patch.object(azure, "run_on", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.run_job()
        self.assert_off_and_released()
        self.assertTrue(any("rm -f runs/job/RUNNING" in line for line in self.commands))

    def test_unreachable_machine_is_switched_off(self):
        self.fail = {"copy", "reach"}
        with self.assertRaises(RuntimeError):
            self.run_job()
        self.assert_off_and_released()

    def test_another_running_job_keeps_the_machine_on(self):
        def copy_fails(*_):
            self.running = ["other"]
            raise RuntimeError("copy failed")
        with mock.patch.object(azure, "run_on", copy_fails), self.assertRaises(RuntimeError):
            self.run_job()
        self.assertEqual((self.stops, self.state), (0, "VM running"))

    def test_another_live_claim_keeps_the_machine_on(self):
        worker = azure.pool(azure.config())[0]
        (self.dir / "claims").mkdir()
        (self.dir / "claims" / "canada.json").write_text(json.dumps({"job": "other", "pid": os.getppid()}))
        self.state = "VM running"
        with contextlib.redirect_stdout(io.StringIO()):
            azure.switch_off(worker, "job")
        self.assertEqual(self.stops, 0)

    def test_failed_command_switches_off(self):
        self.exit_code = "3"
        self.assertEqual(self.run_job(keep_on=True), 3)
        self.assert_off_and_released()

    def test_failed_fetch_keeps_the_job_folder_and_switches_off(self):
        self.fail = {"fetch"}
        self.assertEqual(self.run_job(fetch=["output/result"]), 1)
        self.assert_off_and_released()
        self.assertFalse(self.removed_job_folder())

    def test_keep_on_after_success(self):
        self.assertEqual(self.run_job(keep_on=True), 0)
        self.assertEqual((self.stops, self.state), (0, "VM running"))


@unittest.skipUnless(shutil.which("rsync"), "needs rsync")
class CopyTest(unittest.TestCase):
    def test_only_changed_content_is_sent_whatever_the_timestamps(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ("base", "local"):
                (root / name).mkdir()
                (root / name / "same.txt").write_text("unchanged contents\n")
                (root / name / "edited.txt").write_text(f"{name:>5}\n")       # same size, different contents
                for path in (root / name).iterdir():
                    os.utime(path, (1_000_000, 1_000_000))
            os.utime(root / "local" / "same.txt", (2_000_000, 2_000_000))    # a fresh checkout: new timestamp
            command = azure.copy_command(CONFIG, root / "local", "unused")
            flags = command[1:command.index("-e")]
            flags[flags.index("--link-dest=../../base")] = f"--link-dest={root / 'base'}"
            result = subprocess.run(["rsync", *flags, "--stats", f"{root}/local/", f"{root}/copy/"],
                                    capture_output=True, text=True, check=True)
            self.assertRegex(result.stdout, r"files transferred: 1\b")
            self.assertEqual((root / "copy" / "edited.txt").read_text(), "local\n")
            self.assertEqual((root / "copy" / "same.txt").read_text(), "unchanged contents\n")


if __name__ == "__main__":
    unittest.main()
