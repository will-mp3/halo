"""Exercise runtime selection without touching Homebrew or agent settings."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class NodeRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="halo runtime ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "halo"
        shutil.copytree(ROOT / "scripts", self.repo / "scripts")
        shutil.copy2(ROOT / "setup.sh", self.repo / "setup.sh")
        self.home = self.root / "home"
        self.home.mkdir()
        self.vault = self.root / "vault"
        self.vault.mkdir()
        server = self.repo / "mcp/memory-layer/dist/server.js"
        server.parent.mkdir(parents=True)
        server.touch()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.prefix = self.root / "node@24"
        (self.prefix / "bin").mkdir(parents=True)
        self.log = self.root / "calls.jsonl"
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "PATH": f"{self.bin}:/usr/bin:/bin:/usr/sbin:/sbin",
            "VAULT_PATH": str(self.vault),
            "TEST_PREFIX": str(self.prefix),
            "TEST_LOG": str(self.log),
            "DRY_RUN": "0",
        }
        self.tool(self.bin / "brew", """
if sys.argv[1:] == ['--prefix', 'node@24']:
    print(os.environ['TEST_PREFIX'])
elif sys.argv[1:2] == ['install']:
    sys.exit(int(os.environ.get('INSTALL_FAILURE', '0')))
elif sys.argv[1:] == ['--version']:
    print('Homebrew test')
else:
    sys.exit(1)
""")
        self.tool(self.bin / "node", "print('26')")
        self.tool(self.bin / "git", "pass")
        self.tool(self.bin / "claude", "pass")
        self.tool(self.bin / "codex", "pass")
        self.tool(self.prefix / "bin/node", """
if sys.argv[1:2] in (['-p'], ['-e']):
    print(os.environ.get('TEST_MAJOR', '24'))
elif sys.argv[1:] == ['--version']:
    print('v24.0.0')
elif any(x.endswith('check-native.mjs') for x in sys.argv):
    sys.exit(int(os.environ.get('NATIVE_FAILURE', '0')))
""")
        self.tool(self.prefix / "bin/npm", "sys.exit(int(os.environ.get('NPM_FAILURE', '0')))")
        for name in ("link-skills", "link-global", "link-hooks", "link-statusline"):
            path = self.repo / f"scripts/{name}.sh"
            path.write_text("#!/bin/bash\nexit 0\n")
            path.chmod(0o755)

    def tool(self, path, body):
        path.write_text(
            f"#!{sys.executable}\nimport json, os, sys\n"
            "with open(os.environ['TEST_LOG'], 'a') as log:\n"
            "    log.write(json.dumps(sys.argv) + '\\n')\n" + body
        )
        path.chmod(0o755)

    def run_script(self, name, *args):
        return subprocess.run(
            ["/bin/bash", str(self.repo / name), *args],
            env=self.env, capture_output=True, text=True,
        )

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def registrations(self):
        return [c for c in self.calls() if Path(c[0]).name in {"claude", "codex"}]

    def test_registration_uses_versioned_node_despite_node_26_on_path(self):
        result = self.run_script("scripts/register-mcp.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        adds = [c for c in self.registrations() if c[1:3] == ["mcp", "add"]]
        self.assertEqual(len(adds), 2)
        for call in adds:
            self.assertEqual(call[call.index("--") + 1], str(self.prefix / "bin/node"))
        self.assertFalse(any(c[0] == str(self.bin / "node") for c in self.calls()))

    def test_native_failure_preserves_existing_registrations(self):
        self.env["NATIVE_FAILURE"] = "1"
        result = self.run_script("scripts/register-mcp.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.registrations(), [])

    def test_wrong_major_preserves_existing_registrations(self):
        self.env["TEST_MAJOR"] = "26"
        result = self.run_script("scripts/register-mcp.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.registrations(), [])

    def test_bootstrap_selects_versioned_npm_without_installing_global_node(self):
        result = self.run_script("scripts/bootstrap-deps.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(any(c[0] == str(self.prefix / "bin/node") for c in self.calls()))
        self.assertFalse(any(c[1:2] == ["install"] for c in self.calls()))

    def test_install_failure_is_fatal(self):
        (self.prefix / "bin/node").unlink()
        self.env["INSTALL_FAILURE"] = "1"
        result = self.run_script("scripts/bootstrap-deps.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn([str(self.bin / "brew"), "install", "node@24"], self.calls())

    def test_setup_installs_locked_dependencies_with_versioned_npm(self):
        result = self.run_script("setup.sh", "--skip-ollama")
        self.assertEqual(result.returncode, 0, result.stderr)
        npm_calls = [c for c in self.calls() if Path(c[0]).name == "npm"]
        self.assertEqual(npm_calls, [
            [str(self.prefix / "bin/npm"), "ci", "--no-fund", "--no-audit"],
            [str(self.prefix / "bin/npm"), "run", "build"],
            [str(self.prefix / "bin/npm"), "run", "check:native"],
        ])

    def test_dependency_install_failure_does_not_register_server(self):
        self.env["NPM_FAILURE"] = "1"
        result = self.run_script("setup.sh", "--skip-ollama")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.registrations(), [])

    def test_dry_run_does_not_install_or_register_when_runtime_missing(self):
        (self.prefix / "bin/node").unlink()
        self.env["DRY_RUN"] = "1"
        result = self.run_script("scripts/bootstrap-deps.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("node@24", result.stdout)
        self.assertFalse(any(c[1:2] == ["install"] for c in self.calls()))
        result = self.run_script("scripts/register-mcp.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.registrations(), [])


if __name__ == "__main__":
    unittest.main()
