# Deploy Memes Archive Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete `memes.zip.001` and `memes.zip.002` from the project root only after each one-click deployment script reaches its successful final stage.

**Architecture:** Keep extraction responsibility unchanged in `_setup_memes.py`. Add a small platform-native cleanup block to each deployment script after launch-script settlement and before the completion banner, then document that a full redeploy requires restoring the split archives.

**Tech Stack:** Bash, PowerShell 5.1, Python 3 static verification, Markdown

---

### Task 1: Add a failing cross-platform cleanup contract test

**Files:**
- Create temporarily: `/tmp/airicore_verify_deploy_archive_cleanup.py`
- Test: `一键部署脚本/deploy_linux.sh`
- Test: `一键部署脚本/deploy_macos.command`
- Test: `一键部署脚本/deploy_windows.ps1`

- [x] **Step 1: Write the failing test**

```python
from pathlib import Path

root = Path("/Users/liko/Documents/GitHub/AiriCore")
deploy_dir = root / "一键部署脚本"

cases = {
    "deploy_linux.sh": {
        "launch": 'echo "==> 整理启动脚本"',
        "cleanup": 'echo "==> 清理 memes 分卷"',
        "complete": 'echo "==> 部署完成。后续步骤:"',
        "loop": "for archive_name in memes.zip.001 memes.zip.002; do",
        "remove": 'rm -f "$PROJECT_DIR/$archive_name"',
    },
    "deploy_macos.command": {
        "launch": 'echo "==> 整理启动脚本"',
        "cleanup": 'echo "==> 清理 memes 分卷"',
        "complete": 'echo "==> 部署完成。后续步骤:"',
        "loop": "for archive_name in memes.zip.001 memes.zip.002; do",
        "remove": 'rm -f "$PROJECT_DIR/$archive_name"',
    },
    "deploy_windows.ps1": {
        "launch": 'Write-Host "==> 整理启动脚本"',
        "cleanup": 'Write-Host "==> 清理 memes 分卷"',
        "complete": 'Write-Host "==> 部署完成。后续步骤:"',
        "loop": 'foreach ($archiveName in @("memes.zip.001", "memes.zip.002"))',
        "remove": "Remove-Item -Force $archivePath",
    },
}

for name, expected in cases.items():
    text = (deploy_dir / name).read_text(encoding="utf-8-sig")
    launch_pos = text.index(expected["launch"])
    cleanup_pos = text.index(expected["cleanup"])
    complete_pos = text.index(expected["complete"])
    assert launch_pos < cleanup_pos < complete_pos, name
    assert expected["loop"] in text[cleanup_pos:complete_pos], name
    assert expected["remove"] in text[cleanup_pos:complete_pos], name

print("3 platform cleanup contracts passed")
```

- [x] **Step 2: Run the test and verify RED**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python /tmp/airicore_verify_deploy_archive_cleanup.py`

Expected: FAIL with `ValueError: substring not found` because none of the three deployment scripts contains the cleanup stage.

### Task 2: Implement cleanup in all deployment scripts

**Files:**
- Modify: `一键部署脚本/deploy_linux.sh:217`
- Modify: `一键部署脚本/deploy_macos.command:211`
- Modify: `一键部署脚本/deploy_windows.ps1:238`

- [x] **Step 1: Add the Linux cleanup block**

Insert before the blank line and completion banner:

```bash
echo "==> 清理 memes 分卷"
for archive_name in memes.zip.001 memes.zip.002; do
    if [ -e "$PROJECT_DIR/$archive_name" ]; then
        rm -f "$PROJECT_DIR/$archive_name"
        echo "    已删除 $archive_name"
    fi
done
```

- [x] **Step 2: Add the macOS cleanup block**

Insert the same Bash block before the blank line and completion banner:

```bash
echo "==> 清理 memes 分卷"
for archive_name in memes.zip.001 memes.zip.002; do
    if [ -e "$PROJECT_DIR/$archive_name" ]; then
        rm -f "$PROJECT_DIR/$archive_name"
        echo "    已删除 $archive_name"
    fi
done
```

- [x] **Step 3: Add the Windows cleanup block**

Insert before the blank line and completion banner:

```powershell
Write-Host "==> 清理 memes 分卷"
foreach ($archiveName in @("memes.zip.001", "memes.zip.002")) {
    $archivePath = Join-Path $ProjectDir $archiveName
    if (Test-Path $archivePath) {
        Remove-Item -Force $archivePath
        Write-Host "    已删除 $archiveName"
    }
}
```

- [x] **Step 4: Run the focused test and verify GREEN**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python /tmp/airicore_verify_deploy_archive_cleanup.py`

Expected: PASS with `3 platform cleanup contracts passed`.

### Task 3: Update deployment documentation

**Files:**
- Modify: `一键部署脚本/README.md:21-25`
- Modify: `一键部署脚本/README_CN.md:21-25`

- [x] **Step 1: Document the English cleanup step**

Add item 10:

```markdown
10. After every deployment step succeeds, delete `memes.zip.001` and `memes.zip.002` from the project root.
```

Replace the idempotency note with:

```markdown
> Existing environments, `.env.prod` files and certificates are not overwritten. After a successful deployment removes the split archives, restore both files before running the full deployment script again.
```

- [x] **Step 2: Document the Chinese cleanup step**

Add item 10:

```markdown
10. 全部部署步骤成功后，删除项目根目录中的 `memes.zip.001` 与 `memes.zip.002`。
```

Replace the idempotency note with:

```markdown
> 已有环境、`.env.prod` 和证书不会被覆盖。部署成功后分卷会被删除，如需再次完整运行部署脚本，请先放回这两个分卷。
```

### Task 4: Complete verification and repository hygiene

**Files:**
- Verify: `一键部署脚本/deploy_linux.sh`
- Verify: `一键部署脚本/deploy_macos.command`
- Verify: `一键部署脚本/deploy_windows.ps1`
- Delete: `/tmp/airicore_verify_deploy_archive_cleanup.py`
- Update: `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/deploy-scripts-and-mirrors.md`
- Update: `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/MEMORY.md`

- [x] **Step 1: Run shell syntax checks**

Run: `bash -n 一键部署脚本/deploy_linux.sh 一键部署脚本/deploy_macos.command`

Expected: exit code 0 with no output.

- [x] **Step 2: Verify the Windows BOM**

Run: `xxd -l 3 -p 一键部署脚本/deploy_windows.ps1`

Expected: `efbbbf`.

- [x] **Step 3: Run diff checks**

Run: `git diff --check`

Expected: exit code 0 with no output.

- [x] **Step 4: Remove the temporary test**

Delete `/tmp/airicore_verify_deploy_archive_cleanup.py` after all verification passes.

- [x] **Step 5: Update project memory**

Record the three-platform successful-final-stage cleanup, redeploy archive requirement, changed files, and verification results in `deploy-scripts-and-mirrors.md`; refresh its entry in `MEMORY.md`.

- [x] **Step 6: Commit the implementation**

```bash
git add 一键部署脚本/deploy_linux.sh 一键部署脚本/deploy_macos.command 一键部署脚本/deploy_windows.ps1 一键部署脚本/README.md 一键部署脚本/README_CN.md docs/superpowers/plans/2026-07-30-deploy-memes-archive-cleanup.md
git commit -m "feat: clean up memes archives after deployment"
```
