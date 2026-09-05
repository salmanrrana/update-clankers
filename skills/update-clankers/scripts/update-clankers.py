#!/usr/bin/env python3
"""Update active CLI installations without guessing a different package manager."""

import argparse
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import tempfile

AGENTS = {
    "claude": ("update",),
    "copilot": ("update",),
    "cursor-agent": ("update",),
    "opencode": ("upgrade",),
    "codex": ("update",),
    "pi": ("update", "--self"),
}
PACKAGES = {
    "claude": ("@anthropic-ai/claude-code",),
    "copilot": ("@github/copilot",),
    "opencode": ("opencode-ai",),
    "codex": ("@openai/codex",),
    "pi": ("@earendil-works/pi-coding-agent", "@mariozechner/pi-coding-agent"),
}
BREW_PACKAGES = {
    "claude": ("claude-code",),
    "copilot": ("copilot-cli", "copilot-cli@prerelease"),
    "cursor-agent": ("cursor-cli",),
    "opencode": ("opencode",),
    "codex": ("codex",),
    "pi": ("pi-coding-agent",),
}
VERSION = re.compile(r"(?<![\w.])v?(\d+\.\d+\.\d+(?:[-+][\w.-]+)?)(?!\w|\.\d)")


class UpdateError(Exception):
    pass


@dataclass
class Plan:
    agent: str
    path: Path
    method: str
    command: list[str]
    before: str
    expected: str | None = None


def executable(name: str) -> Path | None:
    # shutil.which on Python 3.10/3.11 prepends cwd on Windows even with a PATH.
    # Search explicit absolute candidates ourselves on every supported Python.
    suffixes = [""]
    if os.name == "nt":
        suffixes = [ext for ext in os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";")
                    if ext.lower() in (".com", ".exe", ".bat", ".cmd")]
    for directory in os.get_exec_path():
        if not os.path.isabs(directory):
            continue
        for suffix in suffixes:
            candidate = Path(directory) / (name + suffix)
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return candidate
    return None


def run(command: list[str], timeout: float = 30, include_stderr: bool = False) -> str:
    """No stdin/prompts; stop the entire updater tree on timeout or interruption."""
    with tempfile.TemporaryDirectory(prefix="clankers-command-") as cwd:
        kwargs = {"start_new_session": True} if os.name != "nt" else {}
        with subprocess.Popen(
            command, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", **kwargs,
        ) as process:
            try:
                output, errors = process.communicate(timeout=timeout)
            except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
                if os.name == "nt":
                    subprocess.run(
                        [str(Path(os.environ["SystemRoot"]) / "System32/taskkill.exe"),
                         "/PID", str(process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                    )
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
                if isinstance(error, KeyboardInterrupt):
                    raise
                raise UpdateError(f"command interrupted or timed out after {timeout:g}s: {command}")
    if process.returncode:
        raise UpdateError(f"exit {process.returncode}: {command}\n{output.strip()}\n{errors.strip()}")
    return (output + (errors if include_stderr else "")).strip()


def version(path: Path) -> str:
    output = run([str(path), "--version"])
    match = VERSION.search(output)
    if not match:
        # Cursor uses date/hash releases, so preserve its complete version line.
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if len(lines) == 1 and re.search(r"\d", lines[0]):
            return lines[0]
        raise UpdateError(f"cannot read a version from {path}: {output}")
    return match[1]


def owns_bin(root: Path, package: str, agent: str, path: Path) -> bool:
    """Match the package's declared bin, not just a globally installed package name."""
    directory = root / package
    try:
        metadata = json.loads((directory / "package.json").read_text(encoding="utf-8"))
        if metadata.get("name") != package:
            return False
        bins = metadata.get("bin", {})
        entry = bins if isinstance(bins, str) else bins.get(agent)
        if not entry:
            return False
        target = (directory / entry).resolve()
        if not target.is_file():
            return False
        if path.resolve() == target:
            return True
        # Bun's Windows .exe launcher stores its target in a companion .bunx.
        companion = path.with_suffix(".bunx")
        if path.suffix.lower() == ".exe" and companion.is_file():
            if companion.stat().st_size > 65536:
                return False
            data = companion.read_bytes()
            if len(data) < 6 or int.from_bytes(data[-2:], "little") >> 3 != 5478:
                return False  # Unknown Bun shim format; do not guess ownership.
            encoded = data[:-2].decode("utf-16-le").split("\0", 1)[0]
            if not encoded.endswith('"'):
                return False
            # Bun omits one leading '..\\' when encoding the target.
            return (path.parent.parent / encoded[:-1].replace("\\", "/")).resolve() == target
        # npm/pnpm generate shell, .cmd and .ps1 shims rather than symlinks.
        # Resolve referenced paths: pnpm shims retain a stable hash symlink,
        # while its package listing reports the resolved installation directory.
        if path.stat().st_size > 32768:
            return False
        text = path.read_text(encoding="utf-8").replace("\\", "/")
        references = re.finditer(r'(?:\$basedir|\$\{basedir\}|%~dp0|%dp0%|\$PSScriptRoot)/([^"\r\n]+)', text)
        return any((path.parent / match[1]).resolve() == target for match in references)
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def package_plan(agent: str, path: Path, before: str) -> Plan | None:
    matches = []
    for manager in ("npm", "pnpm", "bun"):
        tool = executable(manager)
        if not tool:
            continue
        try:
            if manager == "bun":
                root = Path(run([str(tool), "pm", "--global", "bin"])).parent / "install/global/node_modules"
                # Bun's global package root is configurable independently of its bin directory.
                root = Path(os.environ.get("BUN_INSTALL_GLOBAL_DIR", str(root.parent))) / "node_modules"
                roots = [root]
            elif manager == "pnpm":
                # pnpm 11 isolates globals; list exposes package paths for both
                # the old shared root and the new per-install-group layout.
                listed = run([str(tool), "list", "-g", "--parseable"]).splitlines()
                roots = []
                for location in listed:
                    for package in PACKAGES.get(agent, ()):
                        if location.replace("\\", "/").endswith("/" + package):
                            roots.append(Path(location).parents[len(package.split("/")) - 1])
            else:
                roots = [Path(run([str(tool), "root", "-g"]))]
        except UpdateError:
            continue
        for package in PACKAGES.get(agent, ()):
            root = next((root for root in roots if root.is_absolute() and owns_bin(root, package, agent, path)), None)
            if root is None:
                continue
            if manager == "pnpm" and int(run([str(tool), "--version"]).split(".")[0]) >= 11:
                # A single-package add replaces the ENTIRE old pnpm 11 group.
                # Leave grouped installs alone rather than removing unrelated CLIs.
                group = json.loads((root.parent / "package.json").read_text(encoding="utf-8"))
                if set(group.get("dependencies", {})) != {package}:
                    raise UpdateError("pnpm installation group contains other packages; update the group manually to preserve them")
            args = ["install", "-g"] if manager == "npm" else ["add", "-g"]
            if agent == "pi" and manager == "npm":
                args.append("--ignore-scripts")
            matches.append(Plan(agent, path, manager, [str(tool), *args, package + "@latest"], before))
    if len(matches) > 1:
        raise UpdateError("multiple package managers claim this executable; resolve the ownership ambiguity")
    return matches[0] if matches else None


def brew_plan(agent: str, path: Path, before: str) -> Plan | None:
    resolved = path.resolve()
    for marker, kind in (("Caskroom", "--cask"), ("Cellar", "--formula")):
        if marker not in resolved.parts:
            continue
        index = resolved.parts.index(marker)
        package = resolved.parts[index + 1]
        if package not in BREW_PACKAGES.get(agent, ()):
            raise UpdateError(f"unrecognized Homebrew package: {package}")
        prefix = Path(*resolved.parts[:index])
        tool = prefix / "bin/brew"
        if not tool.is_file():
            raise UpdateError(f"owning Homebrew is unavailable: {tool}")
        return Plan(agent, path, "Homebrew", [str(tool), "upgrade", kind, package], before)
    return None


def plan(agent: str) -> Plan | None:
    path = executable(agent)
    if not path:
        return None
    before = version(path)
    managed = brew_plan(agent, path, before) or package_plan(agent, path, before)
    if managed:
        return managed
    resolved = str(path.resolve()).replace("\\", "/")
    shim = ""
    if path.stat().st_size < 32768:
        shim = path.read_text(encoding="utf-8", errors="replace").replace("\\", "/")
    ownership = (resolved + "\n" + shim).lower()
    if path.with_suffix(".bunx").is_file() or any(part in ownership for part in
            ("node_modules/", ".pnpm/", "/nix/store/", "/scoop/", "/winget/", "/.asdf/shims/", "/mise/shims/", "/.volta/")):
        raise UpdateError(f"cannot safely update the manager-owned executable {path} -> {resolved}; use its owning manager/environment")
    if agent == "codex":
        # New Codex knows standalone layouts and installer-specific update actions.
        # Older releases do not have this command; never pass 'update' as a prompt.
        help_text = run([str(path), "--help"])
        if not re.search(r"^[ \t]*update[ \t]+", help_text, re.MULTILINE):
            raise UpdateError(f"unknown Codex installer at {path}; no built-in update command. Update with the original installer")
    return Plan(agent, path, "native updater", [str(path), *AGENTS[agent]], before)


def update(item: Plan, timeout: float, log: Path) -> str:
    output = []
    try:
        # Pin the registry's current latest and verify the active CLI reaches it.
        # This also catches prefix overrides that update an inactive copy.
        if item.method in ("npm", "pnpm", "bun"):
            package = item.command[-1]
            query = "info" if item.method == "bun" else "view"
            latest = json.loads(run([item.command[0], query, package, "version", "--json"]))
            if not isinstance(latest, str) or not VERSION.fullmatch(latest):
                raise UpdateError(f"invalid latest version for {package}: {latest!r}")
            item.expected = latest
            item.command[-1] = package.removesuffix("@latest") + "@" + latest
        output.append("$ " + subprocess.list2cmdline(item.command))
        output.append(run(item.command, timeout, include_stderr=True))
        current = executable(item.agent)
        if current != item.path:
            raise UpdateError(f"active PATH entry changed: {item.path} -> {current}")
        after = version(item.path)
        if item.expected and after != item.expected:
            raise UpdateError(f"verification failed: expected {item.expected}, active {item.agent} is {after}")
        if after != item.before:
            return f"updated: {item.before} -> {after}"
        return f"checked: {after} (version unchanged)"
    except (UpdateError, OSError, ValueError) as error:
        output.append(str(error))
        raise UpdateError(str(error)) from error
    finally:
        log.write_text("\n".join(output) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="inspect and print plans; do not update")
    parser.add_argument("--agent", choices=AGENTS, action="append", help="limit to an agent (repeatable)")
    parser.add_argument("--timeout", type=float, default=600, help="seconds allowed per update command (default: 600)")
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be positive")
    if platform.system() not in ("Linux", "Darwin", "Windows"):
        parser.error(f"unsupported operating system: {platform.system()}")
    print(f"Update Clankers - {platform.system()} - {'DRY RUN' if args.dry_run else 'UPDATE'}", flush=True)
    logs = None if args.dry_run else Path(tempfile.mkdtemp(prefix="update-clankers-"))
    failed = False
    for agent in dict.fromkeys(args.agent or AGENTS):
        try:
            item = plan(agent)
            if not item:
                print(f"{agent:12} skipped (not on PATH)", flush=True)
                continue
            if logs is None:
                print(f"{agent:12} {item.before} | {item.path} -> {item.path.resolve()}", flush=True)
                print(f"{'':12} {item.method}: {subprocess.list2cmdline(item.command)}", flush=True)
            else:
                print(f"{agent:12} updating via {item.method}...", flush=True)
                result = update(item, args.timeout, logs / f"{agent}.log")
                print(f"{agent:12} {result}", flush=True)
        except (UpdateError, OSError, ValueError) as error:
            failed = True
            print(f"{agent:12} FAILED: {error}", flush=True)
    if logs is not None:
        print(f"Logs: {logs}")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
