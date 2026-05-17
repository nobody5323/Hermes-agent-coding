# Hermes-agent-coding

基于 Hermes Agent 的 AI Coding Skill / Toolset MVP。

当前版本先实现一个本地最小闭环：

```text
代码任务 -> 仓库扫描 -> Python AST 分块 -> 关键词 + mock embedding 检索
-> Context Package -> Patch Preview -> 沙箱验证 pytest -> 结构化结果
```

## 目录

```text
skills/ai-coding/              # Hermes Skill 文档和 prompt 模板
extensions/ai_coding/          # 本地 MVP Python 包
extensions/ai_coding/tools/    # repository/search/patch/sandbox 工具函数
extensions/ai_coding/rag/      # chunker/mock embedding/retriever
extensions/ai_coding/sandbox/  # 本地复制仓库 runner + Docker CLI runner
extensions/ai_coding/tests/    # demo 仓库和 smoke tests
```

## 快速验证

```bash
python -m pytest extensions/ai_coding/tests
python demo_minimum_loop.py
python -m extensions.ai_coding.cli run \
  --repo extensions/ai_coding/tests/fixtures/demo_python_repo \
  --task "fix empty password login bug" \
  --patch examples/bugfix_empty_password.diff
```

预期 smoke 输出包含：

```text
Patch preview: 1 file(s), +1/-1, valid=True
Sandbox: exit=0, command succeeded
```

## Docker Sandbox

已实现 Docker CLI runner：

```python
from extensions.ai_coding.tools.sandbox import run_pytest_docker_sandbox
```

CLI 中也可以切换到 Docker 后端：

```bash
python -m extensions.ai_coding.cli run \
  --repo extensions/ai_coding/tests/fixtures/demo_python_repo \
  --task "fix empty password login bug" \
  --patch examples/bugfix_empty_password.diff \
  --sandbox docker
```

它会复制仓库、应用 patch，然后用 `docker run --network none` 在容器里执行 `python -m pytest`。
如果本机没有启动 Docker daemon，会返回结构化 `SandboxResult`，不会中断主流程。

## Hermes Plugin

项目内已经包含 Hermes project-local plugin：

```text
.hermes/plugins/ai-coding/
  plugin.yaml
  __init__.py
```

启用项目插件后，Hermes 可以注册这些工具：

```text
ai_coding_scan_repository
ai_coding_read_file_slice
ai_coding_search_code
ai_coding_retrieve_code_context
ai_coding_build_context_package
ai_coding_preview_patch
ai_coding_validate_patch
ai_coding_run_pytest_sandbox
ai_coding_run_pytest_docker_sandbox
ai_coding_run_minimum_loop
```

运行 Hermes 前设置：

```bash
export HERMES_ENABLE_PROJECT_PLUGINS=true
```

Windows PowerShell：

```powershell
$env:HERMES_ENABLE_PROJECT_PLUGINS = "true"
```

服务器端到端演示记录见：

```text
docs/HERMES_INTEGRATION_DEMO.md
```

## 当前边界

- 暂未接入真实 LLM。
- 暂未接入 Qdrant / 完整 Reranker。
- 已提供 Hermes Plugin 骨架，并已在真实 Hermes Agent + DeepSeek 环境里完成端到端调用验证。
- Docker Desktop 需要在测试机器上单独安装并启动。
