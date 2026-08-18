# airi_security_monitor Native Binary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (recommended) or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `airi_security_monitor` business code into `plugins/airi_security_monitor/src/`, compile it into a single Linux AMD64 CPython 3.11 `.pyd`, and leave a minimal loader as the only production Python source.

**Architecture:** `src/scanner.py` and `src/plugin.py` remain the editable implementation. `src/_airi_security_monitor.py` is a Cython amalgamation that includes both modules into one extension named `_airi_security_monitor`; the root `__init__.py` validates Linux/AMD64/CPython 3.11 and explicitly loads the ELF extension whose filename ends in `.pyd`. Production packaging copies only the loader and binary.

**Tech Stack:** Python 3.11, NoneBot, Cython, `quay.io/pypa/manylinux2014_x86_64`, Docker/Colima, ELF/binutils verification, unittest, JSON state persistence.

---

### Task 1: Move the editable implementation into `src/`

**Files:**
- Create: `plugins/airi_security_monitor/src/__init__.py`
- Create: `plugins/airi_security_monitor/src/scanner.py`
- Create: `plugins/airi_security_monitor/src/plugin.py`
- Modify: `plugins/airi_security_monitor/__init__.py`
- Delete: `plugins/airi_security_monitor/scanner.py`
- Test: `tmp/test_airi_security_monitor_src.py`

- [ ] **Step 1: Write the failing source-layout test**

Create the temporary test below. It verifies that the scanner is importable from the new editable source package and that the existing miner rule still returns the same public `Finding` fields.

```python
import importlib
import unittest
import nonebot


class SourceLayoutTests(unittest.TestCase):
    def test_scanner_lives_under_src_and_keeps_miner_rule(self):
        nonebot.init()
        scanner = importlib.import_module("plugins.airi_security_monitor.src.scanner")
        findings = scanner.find_process_findings(
            [{"pid": 91, "name": "xmrig", "exe": "/tmp/xmrig", "cmdline": [], "username": "root"}]
        )
        self.assertEqual(findings[0].severity, "严重")
        self.assertEqual(findings[0].category, "运行进程")
        self.assertEqual(findings[0].key, "miner:xmrig")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python tmp/test_airi_security_monitor_src.py`

Expected: FAIL with `ModuleNotFoundError` because `plugins/airi_security_monitor/src/` does not exist yet.

- [ ] **Step 3: Move the implementation and make source imports explicit**

Create `src/scanner.py` from the current scanner implementation without behavior changes. Create `src/plugin.py` from the current plugin implementation, changing its scanner import to:

```python
try:
    from .scanner import SEVERITY_RANK, scan_system
except ImportError:
    pass
```

Keep the current `utils.notification` import, configuration keys, matcher declaration, startup/shutdown hooks, state file handling, and all Chinese user-facing messages unchanged. Create an empty `src/__init__.py`. Leave the root `__init__.py` as a temporary compatibility import until Task 2 replaces it with the binary loader. Remove the old root `scanner.py` after the new source files exist.

- [ ] **Step 4: Run the source test to verify it passes**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python tmp/test_airi_security_monitor_src.py`

Expected: PASS.

- [ ] **Step 5: Commit the source relocation**

Run: `git add -f plugins/airi_security_monitor/src plugins/airi_security_monitor/__init__.py && git rm --cached plugins/airi_security_monitor/scanner.py 2>/dev/null || true && git commit -m "refactor: move security monitor source under src"`

The plugin directory is intentionally ignored by the repository; force-add only the requested source and loader files when they are meant to be versioned, and do not alter the existing ignore policy for unrelated plugins.

### Task 2: Add the single-module Cython build input

**Files:**
- Create: `plugins/airi_security_monitor/src/_airi_security_monitor.py`
- Create: `plugins/airi_security_monitor/src/build.py`
- Test: `tmp/test_airi_security_monitor_build.py`

- [ ] **Step 1: Write the failing amalgamation test**

Create the temporary test below. It checks that the build input has the required module name and includes both editable source units.

```python
from pathlib import Path
import unittest


class BuildInputTests(unittest.TestCase):
    def test_amalgamation_declares_binary_module_and_sources(self):
        path = Path("plugins/airi_security_monitor/src/_airi_security_monitor.py")
        text = path.read_text(encoding="utf-8")
        self.assertIn('include "scanner.py"', text)
        self.assertIn('include "plugin.py"', text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python tmp/test_airi_security_monitor_build.py`

Expected: FAIL with `FileNotFoundError` because the amalgamation file is not present.

- [ ] **Step 3: Write the amalgamation and build command**

Create `src/_airi_security_monitor.py` with exactly:

```python
include "scanner.py"
include "plugin.py"
```

Create `src/build.py` as a command-line build tool with these concrete behaviors:

1. Accept `--output` and require a path ending in `_airi_security_monitor.pyd`.
2. Create a temporary directory under `tmp/airi_security_monitor_build` and delete it on successful or failed exit.
3. Invoke the current Python interpreter with `-m cython` on `_airi_security_monitor.py`, using `--3str`, `--directive embedsignature=False,language_level=3` and outputting C into the temporary directory.
4. Invoke a pinned `quay.io/pypa/manylinux2014_x86_64` container with `--platform linux/amd64` and mount the repository read-write. Inside the container use `/opt/python/cp311-cp311/bin/python`, install the pinned Cython build dependency, and compile with `-shared`, `-fPIC`, `-O3`, `-flto`, `-fvisibility=hidden`, `-ffunction-sections`, `-fdata-sections`, `-Wl,--gc-sections`, `-Wl,-z,noexecstack`, and `strip --strip-unneeded`.
5. Refuse to produce output if Docker is unavailable, report the exact missing executable in Chinese, and support the documented Colima fallback by invoking `colima start --arch x86_64` before retrying Docker.
6. Write to a sibling temporary `.pyd`, validate the ELF and exported initialization symbol inside the container, then atomically replace `--output` with `os.replace` on the host.

The build tool must contain no production fallback and must not embed environment values. It must not create C, object, cache, or debug files inside the plugin directory.

- [ ] **Step 4: Run the build-input test to verify it passes**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python tmp/test_airi_security_monitor_build.py`

Expected: PASS.

- [ ] **Step 5: Commit the build input**

Run: `git add -f plugins/airi_security_monitor/src/_airi_security_monitor.py plugins/airi_security_monitor/src/build.py && git commit -m "build: add security monitor Cython amalgamation"`

### Task 3: Replace the root entry point with the explicit `.pyd` loader

**Files:**
- Modify: `plugins/airi_security_monitor/__init__.py`
- Test: `tmp/test_airi_security_monitor_loader.py`

- [ ] **Step 1: Write the failing loader contract test**

Create the temporary test below. It parses the entry point without importing it on macOS and asserts that the loader contract is present.

```python
from pathlib import Path
import unittest


class LoaderContractTests(unittest.TestCase):
    def test_loader_has_platform_checks_and_explicit_extension_loader(self):
        text = Path("plugins/airi_security_monitor/__init__.py").read_text(encoding="utf-8")
        self.assertIn("sys.platform", text)
        self.assertIn("platform.machine", text)
        self.assertIn("ExtensionFileLoader", text)
        self.assertIn("_airi_security_monitor.pyd", text)
        self.assertNotIn("from .scanner import", text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python tmp/test_airi_security_monitor_loader.py`

Expected: FAIL because the current root file is the full Python plugin and has no explicit binary loader.

- [ ] **Step 3: Implement the loader**

Replace root `__init__.py` with a loader that:

1. Imports only standard-library modules needed for platform checks, `importlib.util`, `ExtensionFileLoader`, `Path`, `platform`, `sys`, and `types`.
2. Raises `RuntimeError` with Chinese diagnostics unless `sys.platform == "linux"`, `platform.machine().lower()` is `x86_64` or `amd64`, and `sys.implementation.name == "cpython"` with `sys.version_info[:2] == (3, 11)`.
3. Resolves `_airi_security_monitor.pyd` beside `__init__.py` and raises a Chinese `ImportError` if it is absent.
4. Creates `ExtensionFileLoader("_airi_security_monitor", str(binary_path))`, obtains a spec with `importlib.util.spec_from_file_location`, creates the module, inserts it into `sys.modules`, and executes it.
5. Copies non-private names from the loaded module into the package globals and registers the same module under `f"{__name__}.scanner"` in `sys.modules`.
6. Never imports or executes `src/`, never catches a load failure to fall back to source, and preserves the extension error as the chained cause of the Chinese error.

The loader must not contain comments or docstrings and must not initialize NoneBot itself; the compiled module retains the existing initialization behavior.

- [ ] **Step 4: Run the loader contract test to verify it passes**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python tmp/test_airi_security_monitor_loader.py`

Expected: PASS.

- [ ] **Step 5: Commit the loader**

Run: `git add -f plugins/airi_security_monitor/__init__.py && git commit -m "feat: load security monitor from native extension"`

### Task 4: Build and verify the Linux AMD64 binary

**Files:**
- Create: `plugins/airi_security_monitor/_airi_security_monitor.pyd`
- Test: `tmp/test_airi_security_monitor_binary.py`

- [ ] **Step 1: Write the failing binary verification test**

Create the temporary test below. It verifies the expected artifact contract before the artifact exists.

```python
from pathlib import Path
import subprocess
import unittest


class BinaryTests(unittest.TestCase):
    def test_binary_is_linux_amd64_extension_with_init_symbol(self):
        binary = Path("plugins/airi_security_monitor/_airi_security_monitor.pyd")
        self.assertTrue(binary.is_file())
        file_output = subprocess.check_output(["file", str(binary)], text=True)
        self.assertIn("ELF 64-bit", file_output)
        self.assertIn("x86-64", file_output)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python tmp/test_airi_security_monitor_binary.py`

Expected: FAIL because the `.pyd` artifact has not been generated.

- [ ] **Step 3: Install build-only dependencies and build**

Ensure Docker is available. If it is not, install the project build runtime with `brew install colima docker` and start an x86_64 Colima VM with `colima start --arch x86_64 --cpu 4 --memory 8`.

Then run:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python plugins/airi_security_monitor/src/build.py --output plugins/airi_security_monitor/_airi_security_monitor.pyd
```

The build must run with the CPython 3.11 toolchain inside the manylinux2014 x86_64 image. Do not compile with the macOS interpreter or host compiler.

- [ ] **Step 4: Run binary verification to verify it passes**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python tmp/test_airi_security_monitor_binary.py`

Expected: PASS with an ELF 64-bit x86-64 artifact. The exported `PyInit__airi_security_monitor` symbol is verified by the manylinux-container command below.

Run additional checks through the same manylinux container:

```bash
docker run --rm --platform linux/amd64 -v "$PWD:/work" -w /work quay.io/pypa/manylinux2014_x86_64:latest bash -lc '
file plugins/airi_security_monitor/_airi_security_monitor.pyd
readelf -h plugins/airi_security_monitor/_airi_security_monitor.pyd
readelf --version-info plugins/airi_security_monitor/_airi_security_monitor.pyd | grep GLIBC_ | sort -Vu
readelf -S plugins/airi_security_monitor/_airi_security_monitor.pyd | grep -E "debug|comment" && exit 1 || true
strings plugins/airi_security_monitor/_airi_security_monitor.pyd | grep -E "/Users/|/private/var|\\.pyc$" && exit 1 || true
'
```

Expected: x86-64 ELF, no GLIBC requirement newer than 2.17, no debug/comment sections, and no development-machine paths or Python bytecode paths.

- [ ] **Step 5: Commit the binary artifact**

Run: `git add -f plugins/airi_security_monitor/_airi_security_monitor.pyd && git commit -m "build: add Linux AMD64 security monitor binary"`

### Task 5: Verify source behavior and production-only layout

**Files:**
- Modify: `plugins/airi_security_monitor/src/plugin.py` only if behavior-preserving import adjustments are required
- Create: `tmp/test_airi_security_monitor_runtime.py`
- Delete: all files under `tmp/airi_security_monitor_build` and temporary test files after verification

- [ ] **Step 1: Write the source regression test**

Create a temporary unittest that imports `plugins.airi_security_monitor.src.scanner` and covers miner detection, MCSManager root shell detection, systemd remote execution, SSH failure threshold, listener allowlist, Airi PID plus port exemption, privileged-file changes, and log offset rotation. Use in-memory dictionaries and temporary files only; do not touch `/etc`, `/proc`, `/var/log`, production data, or the real notification account.

- [ ] **Step 2: Run the source regression test before any further edits**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python tmp/test_airi_security_monitor_runtime.py`

Expected: PASS for all retained existing behaviors. If it fails, fix only the source import adjustment and rerun.

- [ ] **Step 3: Validate the production layout**

Create a temporary staging directory containing only `__init__.py` and `_airi_security_monitor.pyd`. Confirm the staging tree has no `src`, `.pyc`, generated C file, object file, build cache, or copied environment file. Confirm the source tree remains available only in the development workspace.

- [ ] **Step 4: Run the full verification set**

Run:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m compileall -q plugins/airi_security_monitor/src
git diff --check
```

Run the source, build, loader, and binary temporary tests in sequence. Run the plugin load smoke test in `airidev` after initializing NoneBot before importing the plugin. The macOS host must produce the expected platform rejection for the root loader; a real successful import must be performed only in Linux AMD64 CPython 3.11.

Run the Linux runtime smoke test with:

```bash
docker run --rm --platform linux/amd64 -v "$PWD/tmp/airi_security_monitor_staging:/runtime" -v "$PWD:/repo" -w /repo -e PYTHONPATH=/runtime:/repo python:3.11-slim bash -lc 'python -m pip install --no-cache-dir nonebot2==2.5.0 psutil==7.2.2 && python -c "import nonebot; nonebot.init(); import plugins.airi_security_monitor as plugin; assert plugin.__name__ == \"plugins.airi_security_monitor\"; assert \"plugins.airi_security_monitor.scanner\" in __import__(\"sys\").modules"'
```

Expected: the command exits 0 and loads the plugin using only the root loader and `.pyd` from the mounted production staging directory.

- [ ] **Step 5: Remove temporary verification artifacts**

Delete `tmp/test_airi_security_monitor_*.py`, `tmp/airi_security_monitor_build`, staging directories, generated C files, object files, and any new `__pycache__` under the plugin. Re-run `find plugins/airi_security_monitor -name '__pycache__' -o -name '*.c' -o -name '*.o'` and require no output.

### Task 6: Update project memory and finish repository hygiene

**Files:**
- Create: `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/airi-security-monitor-native-binary.md`
- Modify: `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/MEMORY.md`

- [ ] **Step 1: Record the mandatory workflow**

Add a memory entry stating that all future `airi_security_monitor` changes must edit `plugins/airi_security_monitor/src/` first, run source tests, rebuild the Linux AMD64 CPython 3.11 `.pyd`, verify the ELF and runtime artifact, and only then replace the production binary. State that production packages exclude `src/` and that there is no source fallback.

- [ ] **Step 2: Add the memory index entry**

Add `airi security monitor native binary` to the `airi_security_monitor` section of `MEMORY.md` with a link to the new memory file.

- [ ] **Step 3: Run final verification and repository hygiene**

Run `git diff --check`, the full temporary test sequence, binary checks, and `git status --short`. Remove generated `__pycache__` after all compile checks. Apply the repository memory rule by removing any tracked `docs/` cache entry with `git rm -r --cached docs` only if one was introduced by this task, while retaining local specification and plan files.

- [ ] **Step 4: Commit the implementation**

Run: `git add -f plugins/airi_security_monitor plugins/airi_security_monitor/src && git commit -m "feat: ship security monitor as Linux AMD64 extension"`

The memory files are outside the repository and are updated locally after the implementation commit; they are not passed to `git add`.

The final report must include the actual compiler, Python ABI, ELF architecture, GLIBC floor, verification commands and results, and any limitation if a real Linux runtime smoke test could not run on the macOS host.
