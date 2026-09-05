"""Isolated fake installations: never invoke real agents or package managers."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "skills/update-clankers/scripts/update-clankers.py"
spec = importlib.util.spec_from_file_location("updater", SCRIPT)
updater = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = updater
spec.loader.exec_module(updater)


class Installations(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="clankers tests ")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.bin = self.home / "bin"
        self.bin.mkdir()
        self.calls = self.home / "calls"
        self.env = {**os.environ, "PATH": str(self.bin), "BUN_INSTALL_GLOBAL_DIR": str(self.home / "bun/install/global"),
                    "TMPDIR": str(self.home), "TEMP": str(self.home), "TMP": str(self.home)}

    def script(self, path, body):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"#!{sys.executable}\n" + body, encoding="utf-8")
        path.chmod(0o755)
        return path

    def command(self, name, body):
        if os.name == "nt":
            source = self.script(self.bin / (name + ".py"), body)
            path = self.bin / (name + ".cmd")
            path.write_text(f'@echo off\n"{sys.executable}" "{source}" %*\n', encoding="utf-8")
            return path
        return self.script(self.bin / name, body)

    def agent_body(self, state, native=True):
        return (
            "import pathlib, sys\n"
            f"state = pathlib.Path({str(state)!r})\n"
            "if '--version' in sys.argv: print('agent ' + state.read_text() + '.')\n"
            f"elif '--help' in sys.argv: print({'  update  Update to latest' if native else '  exec  Run agent'!r})\n"
            "else:\n"
            f"    pathlib.Path({str(self.calls)!r}).open('a').write('native ' + ' '.join(sys.argv[1:]) + '\\n')\n"
            "    state.write_text('2.0.0')\n"
        )

    def native(self, name="codex", supported=True):
        state = self.home / (name + ".version")
        state.write_text("1.0.0")
        return self.command(name, self.agent_body(state, supported))

    def package(self, agent="codex", package="@openai/codex", manager="npm", noop=False, shim=False, isolated=False):
        layout = "pnpm/global/v11/hash/node_modules" if isolated else manager + "/node_modules"
        root = self.home / ("bun/install/global/node_modules" if manager == "bun" else layout)
        directory = root / package
        directory.mkdir(parents=True)
        if isolated:
            (root.parent / "package.json").write_text(json.dumps({"dependencies": {package: "1.0.0"}}))
        state = directory / "version"
        state.write_text("1.0.0")
        target = self.script(directory / "bin/cli.py", self.agent_body(state))
        (directory / "package.json").write_text(json.dumps({"name": package, "bin": {agent: "bin/cli.py"}}))
        path = self.bin / (agent + ".cmd" if os.name == "nt" else agent)
        if os.name == "nt" or shim:
            relative = os.path.relpath(target, path.parent)
            if os.name == "nt":
                path.write_text(f'@echo off\nset "dp0=%~dp0"\n"{sys.executable}" "%dp0%\\{relative}" %*\n')
            else:
                path.write_text(f'#!/bin/sh\nbasedir="$(dirname "$0")"\nexec "{sys.executable}" "$basedir/{relative}" "$@"\n')
                path.chmod(0o755)
        else:
            path.symlink_to(target)
        body = (
            "import json, pathlib, sys\n"
            "args = sys.argv[1:]\n"
            f"if args == ['--version']: print({'11.0.0' if isolated else '10.0.0'!r})\n"
            f"elif args == ['root', '-g']: print({str(root)!r}); print('npm config warning', file=sys.stderr)\n"
            f"elif args == ['pm', '--global', 'bin']: print({str(self.home / 'bun/bin')!r})\n"
            f"elif args == ['list', '-g', '--parseable']: print({str(root.parent)!r}); print({str(directory)!r})\n"
            "elif args[0] in ('view', 'info'): print(json.dumps('2.0.0'))\n"
            "else:\n"
            f"    pathlib.Path({str(self.calls)!r}).open('a').write({manager!r} + ' ' + ' '.join(args) + '\\n')\n"
            f"    pathlib.Path({str(state)!r}).write_text({'1.0.0' if noop else '2.0.0'!r})\n"
        )
        self.command(manager, body)
        return path, root

    def invoke(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], env=self.env, cwd=self.home,
                              text=True, capture_output=True, timeout=30, encoding="utf-8")

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_npm_updates_active_nvm_style_install_and_verifies(self):
        self.package()
        result = self.invoke("--agent", "codex")
        self.assert_ok(result)
        self.assertIn("updated: 1.0.0 -> 2.0.0", result.stdout)
        self.assertEqual(self.calls.read_text(), "npm install -g @openai/codex@2.0.0\n")

    def test_npm_success_that_leaves_old_codex_is_failure(self):
        self.package(noop=True)
        result = self.invoke("--agent", "codex")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("verification failed: expected 2.0.0", result.stdout)

    def test_wrong_npm_prefix_cannot_update_a_second_copy(self):
        self.package()
        self.command("npm", f"print({str(self.home / 'other/node_modules')!r})\n")
        result = self.invoke("--agent", "codex")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertFalse(self.calls.exists())

    def test_pnpm_and_bun_ownership(self):
        for manager in ("pnpm", "bun"):
            with self.subTest(manager=manager):
                path, _ = self.package(manager=manager)
                result = self.invoke("--agent", "codex")
                self.assert_ok(result)
                self.assertIn(f"{manager} add -g @openai/codex@2.0.0", self.calls.read_text())
                path.unlink()

    @unittest.skipIf(os.name == "nt", "POSIX shim; Windows shims covered by every package test")
    def test_pnpm_shell_shim(self):
        self.package(manager="pnpm", shim=True)
        # The shell wrapper needs dirname, but no real package manager is visible.
        import shutil
        (self.bin / "dirname").symlink_to(shutil.which("dirname"))
        self.assert_ok(self.invoke("--agent", "codex"))

    @unittest.skipIf(os.name == "nt", "Homebrew is supported on macOS/Linux")
    def test_brew_symlink_cask_and_formula_do_not_use_npm(self):
        for kind in ("Caskroom", "Cellar"):
            with self.subTest(kind=kind):
                state = self.home / "brew.version"
                state.write_text("1.0.0")
                target = self.script(self.home / kind / "codex/1.0.0/bin/codex", self.agent_body(state))
                link = self.bin / "codex"
                link.symlink_to(target)
                self.script(self.bin / "brew",
                            f"import pathlib, sys\npathlib.Path({str(self.calls)!r}).write_text(' '.join(sys.argv[1:]))\n"
                            f"pathlib.Path({str(state)!r}).write_text('2.0.0')\n")
                self.command("npm", "raise RuntimeError('must not run npm for Homebrew')\n")
                self.assert_ok(self.invoke("--agent", "codex"))
                flag = "--cask" if kind == "Caskroom" else "--formula"
                self.assertEqual(self.calls.read_text(), f"upgrade {flag} codex")
                link.unlink()

    def test_new_codex_native_update_and_old_unknown_failure(self):
        self.native()
        self.assert_ok(self.invoke("--agent", "codex"))
        self.assertEqual(self.calls.read_text(), "native update\n")
        self.calls.unlink()
        self.native(supported=False)
        result = self.invoke("--agent", "codex")
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown Codex installer", result.stdout)
        self.assertFalse(self.calls.exists())

    def test_all_native_commands_are_awaited(self):
        for agent in updater.AGENTS:
            self.native(agent)
        result = self.invoke()
        self.assert_ok(result)
        self.assertEqual(self.calls.read_text().splitlines(),
                         ["native " + " ".join(args) for args in updater.AGENTS.values()])
        self.assertEqual(result.stdout.count("updated:"), 6)

    def test_pi_preserves_installed_package_name(self):
        self.package(agent="pi", package="@mariozechner/pi-coding-agent")
        self.assert_ok(self.invoke("--agent", "pi"))
        self.assertIn("--ignore-scripts @mariozechner/pi-coding-agent@2.0.0", self.calls.read_text())

    def test_dry_run_has_no_update_calls(self):
        self.package()
        result = self.invoke("--dry-run", "--agent", "codex")
        self.assert_ok(result)
        self.assertIn("install -g @openai/codex@latest", result.stdout)
        self.assertFalse(self.calls.exists())

    def test_missing_agents_are_skipped_not_installed(self):
        result = self.invoke()
        self.assert_ok(result)
        self.assertEqual(result.stdout.count("skipped (not on PATH)"), 6)
        self.assertFalse(self.calls.exists())

    def test_failure_does_not_skip_remaining_agents(self):
        self.command("claude", "raise SystemExit('broken version command')\n")
        self.native("pi")
        result = self.invoke("--agent", "claude", "--agent", "pi")
        self.assertEqual(result.returncode, 1)
        self.assertIn("broken version command", result.stdout)
        self.assertIn("pi           updated:", result.stdout)

    def test_update_failure_keeps_diagnostics(self):
        self.native("claude")
        self.command("claude", "import sys\nif '--version' in sys.argv: print('1.0.0')\nelse: raise SystemExit('permission denied')\n")
        result = self.invoke("--agent", "claude")
        self.assertEqual(result.returncode, 1)
        self.assertIn("permission denied", result.stdout)
        logdir = Path(result.stdout.split("Logs: ")[1].strip())
        self.assertIn("permission denied", (logdir / "claude.log").read_text())

    def test_timeout_stops_updater(self):
        self.command("claude", "import sys, time\nif '--version' in sys.argv: print('1.0.0')\nelse: time.sleep(10)\n")
        result = self.invoke("--agent", "claude", "--timeout", "0.1")
        self.assertEqual(result.returncode, 1)
        self.assertIn("timed out", result.stdout)

    @unittest.skipIf(os.name == "nt", "POSIX process-group behavior")
    def test_timeout_also_stops_update_children(self):
        marker = self.home / "child-survived"
        child = f"import pathlib, time; time.sleep(0.5); pathlib.Path({str(marker)!r}).touch()"
        self.command("claude", "import subprocess, sys, time\n"
                     "if '--version' in sys.argv: print('1.0.0')\n"
                     "else:\n"
                     f"    subprocess.Popen([sys.executable, '-c', {child!r}])\n"
                     "    time.sleep(10)\n")
        result = self.invoke("--agent", "claude", "--timeout", "0.1")
        self.assertEqual(result.returncode, 1)
        import time
        time.sleep(0.6)
        self.assertFalse(marker.exists())

    def test_unchanged_native_version_is_not_claimed_latest(self):
        self.command("claude", "print('1.0.0')\n")
        result = self.invoke("--agent", "claude")
        self.assert_ok(result)
        self.assertIn("checked: 1.0.0 (version unchanged)", result.stdout)
        self.assertNotIn("already latest", result.stdout)

    def test_unknown_arguments_do_not_update(self):
        self.native()
        self.assertEqual(self.invoke("--wat").returncode, 2)
        self.assertFalse(self.calls.exists())

    def test_current_directory_is_not_searched(self):
        legitimate = self.native()
        self.script(self.home / legitimate.name, "raise RuntimeError('untrusted project executable')\n")
        previous = Path.cwd()
        try:
            os.chdir(self.home)
            with patch.dict(os.environ, self.env):
                self.assertEqual(updater.executable("codex"), legitimate)
            with patch.dict(os.environ, {"PATH": "."}):
                self.assertIsNone(updater.executable("codex"))
        finally:
            os.chdir(previous)

    def test_pnpm11_isolated_global_package(self):
        self.package(manager="pnpm", isolated=True)
        # pnpm 11 removed the shared root; list exposes the owning install group.
        manager_script = self.bin / ("pnpm.py" if os.name == "nt" else "pnpm")
        body = manager_script.read_text().replace(
            "if args == ['root', '-g']:", "if args == ['unsupported-old-root-command']:")
        manager_script.write_text(body)
        self.assert_ok(self.invoke("--agent", "codex"))
        self.assertIn("pnpm add -g @openai/codex@2.0.0", self.calls.read_text())

    def test_pnpm11_shim_uses_hash_link_but_listing_uses_real_directory(self):
        _, root = self.package(manager="pnpm", isolated=True, shim=True)
        hashed = root.parent
        generation = self.home / "pnpm/install-generation"
        hashed.rename(generation)
        if os.name == "nt":
            subprocess.run([os.environ['COMSPEC'], '/c', 'mklink', '/J', str(hashed), str(generation)],
                           check=True, capture_output=True)
        else:
            hashed.symlink_to(generation, target_is_directory=True)
            import shutil
            (self.bin / 'dirname').symlink_to(shutil.which('dirname'))
        manager_script = self.bin / ("pnpm.py" if os.name == "nt" else "pnpm")
        body = manager_script.read_text().replace(repr(str(hashed)), repr(str(generation))).replace(
            repr(str(root / '@openai/codex')), repr(str(generation / 'node_modules/@openai/codex')))
        manager_script.write_text(body)
        self.assert_ok(self.invoke('--agent', 'codex'))

    def test_pnpm11_group_is_not_replaced_by_a_single_package(self):
        _, root = self.package(manager="pnpm", isolated=True)
        group = root.parent / "package.json"
        group.write_text(json.dumps({"dependencies": {"@openai/codex": "1.0.0", "other-cli": "1.0.0"}}))
        result = self.invoke("--agent", "codex")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("installation group", result.stdout)
        self.assertFalse(self.calls.exists())

    @unittest.skipIf(os.name == "nt", "Homebrew is supported on macOS/Linux")
    def test_pi_homebrew_formula(self):
        state = self.home / "pi.version"
        state.write_text("1.0.0")
        target = self.script(self.home / "Cellar/pi-coding-agent/1.0.0/libexec/bin/pi", self.agent_body(state))
        (self.bin / "pi").symlink_to(target)
        self.script(self.bin / "brew", f"import pathlib, sys\npathlib.Path({str(self.calls)!r}).write_text(' '.join(sys.argv[1:]))\n")
        self.assert_ok(self.invoke("--agent", "pi"))
        self.assertEqual(self.calls.read_text(), "upgrade --formula pi-coding-agent")

    def test_bun_binary_shim_matches_companion_target(self):
        path, root = self.package(manager="bun")
        target = root / "@openai/codex/bin/cli.py"
        path.unlink()
        launcher = self.home / "bun/bin/codex.exe"
        launcher.parent.mkdir(parents=True)
        launcher.write_bytes(b'MZ' + bytes(40000))
        relative = os.path.relpath(target, launcher.parent).replace('/', '\\')
        # Bun omits the first parent traversal; its launcher restores it.
        relative = relative.removeprefix('..\\')
        metadata = (relative + '\"\0').encode('utf-16-le') + (5478 << 3).to_bytes(2, 'little')
        launcher.with_suffix('.bunx').write_bytes(metadata)
        with patch.dict(os.environ, self.env):
            item = updater.package_plan("codex", launcher, "1.0.0")
        self.assertIsNotNone(item)
        self.assertEqual(item.method, "bun")
        launcher.with_suffix('.bunx').write_bytes(('wrong-target\"\0').encode('utf-16-le') + metadata[-2:])
        with patch.dict(os.environ, self.env):
            self.assertIsNone(updater.package_plan("codex", launcher, "1.0.0"))


if __name__ == "__main__":
    unittest.main()
