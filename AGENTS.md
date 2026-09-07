# AiriCore 开发规范入口

开始任何开发、修改、测试或代码审查前，必须读取并遵守以下项目记忆文件：

- `C:\Users\Steve\.codex\projects\d--github-airicore\MEMORY.md`
- `C:\Users\Steve\.codex\projects\d--github-airicore\airicore-project-constraints.md`

以上文件中的项目记忆、开发规范、配置同步、验证清理、目录 mtime 同步和 Git 收尾要求均适用于本仓库。若记忆索引新增了相关文件，也必须按索引读取；当前仓库状态和用户明确要求优先于过期记忆。

## 固定验证环境

- Python 验证必须使用当前系统 Miniconda 的 `airidev` 环境。
- 单元测试：`conda run -n airidev python -m unittest discover -s tests -v`
- 语法检查：`conda run -n airidev python -m py_compile <文件路径>`
- 若命令需要 PowerShell 变量或多条步骤，仍须确保实际 Python 进程运行在 `airidev` 环境中。

## 关键约束速查

- 面向用户的内容、日志、错误和 Bot 文案使用中文；代码标识符使用英文。
- LLM 调用统一通过 `utils/llm.py`，不得在插件中复制客户端、fallback 或预算逻辑。
- 修改 `.env.prod` 配置键时同步修改 `.env.prod_example`。
- 验证完成后删除 `__pycache__` 等缓存和临时结果。
- 修改插件目录后同步目录 mtime，并按项目记忆完成最终 mtime dry-run。
- 不得使用 `git reset --hard` 或未经明确授权的 `git checkout --` 覆盖用户改动。
