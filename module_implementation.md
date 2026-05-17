# Hermes Agent AI Coding 扩展：分模块分步骤实现文档

## 1. 实现总览

本项目不从零实现一个新的 Agent，而是在 Hermes Agent 原有框架上扩展 AI Coding 能力。实现时按“先骨架、再工具、再检索、再上下文工程、再工作流、再沙箱、再记忆”的顺序推进，保证每一步都能单独验证。

最终目标：

- 保留 Hermes Agent 的 CLI/TUI、Tool Calling、Skills、Memory、Sub-agent、Docker Backend 等基础能力。
- 新增 `ai-coding` Skill，用于触发代码任务处理流程。
- 新增 AI Coding Toolset，让 Agent 能扫描代码库、读取文件、搜索代码、生成 Patch、执行沙箱验证。
- 新增 Code RAG 和 Context Engineering，使 Agent 能构建高质量代码任务上下文。
- 新增 LangGraph Workflow，串联需求理解、代码检索、上下文组装、任务规划、Patch 生成、沙箱验证和记忆回写。

建议实现顺序：

1. 项目骨架与配置
2. ai-coding Skill
3. Repository Tools
4. Code Chunker
5. Code RAG
6. Context Engineering
7. Patch 工具
8. Docker Sandbox
9. LangGraph Workflow
10. 长期记忆
11. 子 Agent 协作
12. 测试与演示样例

## 2. 推荐目录结构

如果后续把 Hermes Agent 源码拉到本地，建议在其仓库中新增：

```text
hermes-agent/
  skills/
    ai-coding/
      SKILL.md
      prompts/
        requirement_analysis.md
        query_rewrite.md
        context_package.md
        task_planning.md
        patch_generation.md
        reflection.md
      examples/
        feature_task.md
        bugfix_task.md
        error_analysis_task.md

  extensions/
    ai_coding/
      __init__.py
      config.py
      schemas.py
      workflow.py
      context_engineering.py
      rag/
        __init__.py
        chunker.py
        indexer.py
        retriever.py
        reranker.py
        embeddings.py
      tools/
        __init__.py
        repository.py
        search.py
        patch.py
        sandbox.py
        memory.py
      sandbox/
        Dockerfile.python
        policy.py
        runner.py
      memory/
        writer.py
        retriever.py
      tests/
        fixtures/
          demo_python_repo/
        test_repository_tools.py
        test_chunker.py
        test_context_engineering.py
        test_sandbox_policy.py
        test_workflow_smoke.py
```

如果暂时不改 Hermes Agent 源码，可以先在当前目录按相同结构实现 `extensions/ai_coding/`，后续再迁移到 Hermes 仓库。

## 3. Module 1：项目骨架与基础配置

### 3.1 模块目标

建立 AI Coding 扩展的基础包结构、配置文件和核心数据模型，为后续模块提供统一输入输出。

### 3.2 需要创建的文件

```text
extensions/ai_coding/
  __init__.py
  config.py
  schemas.py
```

### 3.3 核心数据结构

在 `schemas.py` 中定义：

- `CodingTask`：一次用户代码任务。
- `RepositorySummary`：仓库扫描结果。
- `CodeChunk`：代码分块结果。
- `RetrievedChunk`：检索后的代码片段。
- `ContextPackage`：上下文工程输出。
- `PatchPreview`：Patch 预览结果。
- `SandboxResult`：沙箱执行结果。
- `CodingTaskResult`：完整任务结果。

### 3.4 实现步骤

1. 创建 `extensions/ai_coding` 包。
2. 在 `config.py` 中定义默认配置：
   - `default_token_budget`
   - `max_iterations`
   - `default_top_k`
   - `ignored_dirs`
   - `supported_extensions`
   - `sandbox_timeout_seconds`
3. 在 `schemas.py` 中使用 Pydantic 定义所有模块共享的数据模型。
4. 所有后续模块只通过这些 Schema 传递数据，避免自由传 dict 导致字段混乱。

### 3.5 验收标准

- 能成功导入 `extensions.ai_coding`。
- 所有 Schema 可以被实例化和 JSON 序列化。
- 配置项有默认值，且可以被环境变量或配置文件覆盖。

## 4. Module 2：ai-coding Skill

### 4.1 模块目标

让 Hermes Agent 能识别“代码任务”并进入 AI Coding 扩展流程。

### 4.2 需要创建的文件

```text
skills/ai-coding/
  SKILL.md
  prompts/
    requirement_analysis.md
    query_rewrite.md
    context_package.md
    task_planning.md
    patch_generation.md
    reflection.md
```

### 4.3 Skill 内容

`SKILL.md` 应包含：

- 适用场景：功能开发、Bug 修复、报错分析、测试补全、代码解释。
- 不适用场景：系统级操作、真实密钥读取、无授权修改用户文件。
- 标准流程：先理解需求，再检索代码，再构建上下文，再计划，再生成 Patch，再沙箱验证。
- 安全规则：默认只生成 Patch Preview，不直接写入真实文件。
- 输出格式：任务摘要、上下文来源、计划、Patch、验证结果、后续建议。

### 4.4 实现步骤

1. 编写 `SKILL.md`，明确 Agent 行为边界。
2. 编写需求分析 Prompt，用于判断任务类型和风险等级。
3. 编写查询改写 Prompt，用于把用户需求转换为多条检索查询。
4. 编写上下文包 Prompt，约束 Context Package 的 Markdown 输出格式。
5. 编写 Patch 生成 Prompt，要求输出统一 diff 和修改说明。
6. 编写 Reflection Prompt，用于根据沙箱失败日志进行二次修正。

### 4.5 验收标准

- Hermes Agent 能根据用户请求选择 `ai-coding` Skill。
- Skill 文档明确要求先检索和组装上下文，而不是直接生成代码。
- Prompt 模板覆盖任务分析、检索、上下文、Patch、反思五个环节。

## 5. Module 3：Repository Tools

### 5.1 模块目标

为 Agent 提供仓库扫描、文件读取和代码搜索能力。

### 5.2 需要创建的文件

```text
extensions/ai_coding/tools/
  repository.py
  search.py
```

### 5.3 工具列表

| Tool | 功能 |
| --- | --- |
| `scan_repository` | 扫描仓库文件树、语言栈、入口文件、依赖文件 |
| `read_file_slice` | 读取指定文件的指定行范围 |
| `search_code` | 按关键词或正则搜索代码 |
| `detect_project_commands` | 推测测试、格式化、静态检查命令 |

### 5.4 实现步骤

1. 实现目录过滤规则，跳过 `.git`、`.venv`、`node_modules`、`dist`、`build`、`__pycache__`。
2. 实现文件类型识别，根据扩展名分类为 source、test、doc、config、script。
3. 实现仓库摘要生成：
   - 文件数量
   - 主要语言
   - README 是否存在
   - 依赖文件是否存在
   - 测试目录是否存在
4. 实现安全文件读取：
   - 禁止读取仓库外文件。
   - 限制单次读取最大行数。
   - 对大文件返回截断提示。
5. 实现代码搜索：
   - 支持普通关键词。
   - 支持正则。
   - 返回路径、行号、上下文行。
6. 实现命令推测：
   - `pytest.ini` / `pyproject.toml` -> `python -m pytest`
   - `package.json` -> `npm test`
   - `Makefile` -> `make test`

### 5.5 验收标准

- 能扫描 demo 仓库并输出稳定的 `RepositorySummary`。
- 读取文件时不能越过仓库根目录。
- 搜索结果包含路径、行号和命中内容。
- 能为常见 Python / Node 项目推测测试命令。

## 6. Module 4：Code Chunker

### 6.1 模块目标

将源码、文档、配置文件切分成适合检索和上下文注入的代码块。

### 6.2 需要创建的文件

```text
extensions/ai_coding/rag/
  chunker.py
```

### 6.3 分块策略

- Python：优先使用 `ast` 按 class/function 分块。
- Markdown：按标题层级分块。
- JSON/YAML/TOML：按顶层 key 或固定行数分块。
- 其他语言：先使用启发式规则，后续可接入 tree-sitter。
- 超长块：按最大行数继续切分。
- 太短块：与相邻块合并。

### 6.4 实现步骤

1. 实现 `chunk_file(path, project_id)`。
2. 根据文件扩展名分发到不同 chunker。
3. Python 文件使用 `ast.parse` 获取类和函数的起止行。
4. Markdown 文件根据 `#` 标题切分。
5. 其他文本文件使用滑动窗口切分。
6. 为每个 chunk 生成稳定 `chunk_id`，例如 `sha1(project_id + path + start_line + end_line)`。
7. 为 chunk 添加元数据：语言、文件类型、符号名、起止行号。

### 6.5 验收标准

- Python 文件能按函数和类分块。
- README 能按标题分块。
- 解析失败时能退化到滑动窗口分块。
- 每个 `CodeChunk` 都包含路径、起止行号和内容。

## 7. Module 5：Code RAG

### 7.1 模块目标

建立代码库向量索引，并根据用户需求召回相关代码片段。

### 7.2 需要创建的文件

```text
extensions/ai_coding/rag/
  embeddings.py
  indexer.py
  retriever.py
  reranker.py
```

### 7.3 实现步骤

1. 在 `embeddings.py` 中定义 Embedding 抽象接口。
2. 先实现一个本地 mock embedding，便于无 API Key 时测试。
3. 后续接入真实 Embedding 模型，例如 Qwen Embedding。
4. 在 `indexer.py` 中实现：
   - 扫描仓库。
   - 调用 chunker。
   - 生成向量。
   - 写入 Qdrant。
   - 保存索引统计。
5. 在 `retriever.py` 中实现：
   - 向量检索。
   - 关键词检索。
   - 错误日志路径命中。
   - 混合合并。
6. 在 `reranker.py` 中实现重排：
   - 初期可用关键词重合和路径命中做轻量 rerank。
   - 后续接入 Qwen Reranker。
7. 输出统一的 `RetrievedChunk` 列表。

### 7.4 验收标准

- 能把 demo 仓库索引到 Qdrant。
- 输入功能需求能召回相关源码。
- 输入错误堆栈能优先召回堆栈路径文件。
- Reranker 后的结果顺序可解释。

## 8. Module 6：Context Engineering

### 8.1 模块目标

把用户需求、仓库摘要、检索片段、长期记忆、工具输出和沙箱反馈整理为高质量 Context Package。

### 8.2 需要创建的文件

```text
extensions/ai_coding/
  context_engineering.py
```

### 8.3 Context Package 内容

应包含：

- 用户需求和任务类型。
- 仓库结构摘要。
- 相关源码片段。
- 相关测试和配置文件。
- 长期记忆摘要。
- 工具调用结果。
- 沙箱错误日志。
- Token 估算。

### 8.4 实现步骤

1. 实现上下文候选项统一结构。
2. 为每个候选项计算分数：
   - RAG 相关性
   - Reranker 分数
   - 路径命中
   - 错误堆栈命中
   - 测试文件相关性
   - 历史记忆相关性
3. 实现去重：
   - 同一文件相同行范围只保留最高分。
   - 同一文件相邻片段可合并。
4. 实现压缩：
   - 高分源码保留原文。
   - 中分文档保留摘要。
   - 低分内容只保留路径和原因。
5. 实现 Token 预算控制：
   - 用户需求必须保留。
   - 关键源码优先保留。
   - 错误日志保留关键栈帧。
   - 超预算时从低分内容开始裁剪。
6. 同时输出 JSON 版和 Markdown 版。

### 8.5 验收标准

- Context Package 在设定 Token 预算内。
- 必须包含任务需求、仓库摘要和至少一个相关源码片段。
- 同一文件片段不会大量重复。
- 输出能解释每个上下文片段为什么被选中。

## 9. Module 7：Patch 工具

### 9.1 模块目标

让 Agent 生成可审查的 Patch Preview，而不是直接修改真实文件。

### 9.2 需要创建的文件

```text
extensions/ai_coding/tools/
  patch.py
```

### 9.3 实现步骤

1. 定义 Patch 输入格式，优先使用 unified diff。
2. 实现 `preview_patch(patch_text)`：
   - 解析涉及文件。
   - 统计新增/删除行数。
   - 检查 diff 格式是否有效。
   - 输出变更摘要。
3. 实现 `validate_patch_against_repo(repo_path, patch_text)`：
   - 检查目标文件是否存在。
   - 检查上下文行是否匹配。
   - 检查是否修改仓库外路径。
4. 暂不直接实现真实写入，真实应用 Patch 交给 Hermes 原有权限机制或沙箱验证流程。

### 9.4 验收标准

- 能解析 unified diff。
- 能列出变更文件和增删行数。
- 拒绝修改仓库外路径。
- Patch 无法应用时返回明确错误。

## 10. Module 8：Docker Sandbox

### 10.1 模块目标

隔离执行测试命令或静态检查命令，将结果反馈给 Agent。

### 10.2 需要创建的文件

```text
extensions/ai_coding/sandbox/
  Dockerfile.python
  policy.py
  runner.py

extensions/ai_coding/tools/
  sandbox.py
```

### 10.3 安全策略

- 默认禁用网络。
- 限制 CPU、内存和超时时间。
- 不挂载用户主目录。
- 将仓库复制到临时目录执行。
- 禁止危险命令：
  - `rm -rf /`
  - `del /s`
  - `format`
  - `shutdown`
  - 修改系统目录
  - 读取 `.ssh`、`.aws`、`.env` 等敏感路径

### 10.4 实现步骤

1. 实现 `policy.py`：
   - `is_dangerous_command(command)`
   - `validate_mount_path(path)`
   - `build_docker_limits()`
2. 实现 `runner.py`：
   - 创建临时目录。
   - 复制仓库。
   - 可选应用 Patch。
   - 调用 Docker SDK 或 Docker CLI。
   - 捕获 stdout、stderr、exit code、耗时。
3. 实现 `sandbox.py` Tool：
   - 接收 repo、patch、command。
   - 调用 policy 检查。
   - 调用 runner 执行。
   - 返回 `SandboxResult`。
4. 实现失败摘要：
   - 提取最后 N 行 stderr。
   - 提取 pytest failed 信息。
   - 提取 traceback 关键帧。

### 10.5 验收标准

- 能在 Docker 中运行 demo 仓库测试。
- 危险命令会被拒绝。
- 失败时能返回 stderr、exit code 和失败摘要。
- 原始仓库不会被沙箱执行修改。

## 11. Module 9：LangGraph Workflow

### 11.1 模块目标

把所有模块串成完整 AI Coding 执行流程。

### 11.2 需要创建的文件

```text
extensions/ai_coding/
  workflow.py
```

### 11.3 工作流节点

```text
Requirement Analyzer
  -> Query Rewriter
  -> Code Retriever
  -> Context Builder
  -> Task Planner
  -> Tool Executor
  -> Patch Generator
  -> Sandbox Verifier
  -> Reflection / Memory Writer
  -> Final Summary
```

### 11.4 实现步骤

1. 定义 `CodingWorkflowState`。
2. 实现 `analyze_requirement`：
   - 判断任务类型。
   - 提取约束。
   - 评估风险等级。
3. 实现 `rewrite_queries`：
   - 生成语义检索 query。
   - 生成关键词 query。
   - 生成测试检索 query。
4. 实现 `retrieve_context`：
   - 调用 Code RAG。
   - 调用代码搜索。
   - 合并候选片段。
5. 实现 `build_context`：
   - 调用 Context Engineering。
6. 实现 `plan_task`：
   - 输出目标文件、修改步骤、验证命令。
7. 实现 `generate_patch`：
   - 根据上下文和计划生成 Patch Preview。
8. 实现 `verify_patch`：
   - 调用 Docker Sandbox。
9. 实现 `reflect_failure`：
   - 如果失败且未超过迭代次数，分析错误并补充上下文。
10. 实现 `write_task_memory`：
   - 成功写入方案。
   - 失败写入排查经验。
11. 实现 `final_summary`：
   - 输出任务摘要、上下文来源、Patch、验证结果和后续建议。

### 11.5 验收标准

- 单个任务能完整经过工作流。
- 沙箱失败后能进入 Reflection。
- 超过最大迭代次数后能输出失败原因。
- 所有节点输入输出都有结构化记录。

## 12. Module 10：长期记忆

### 12.1 模块目标

让 Agent 在跨会话任务中复用项目知识和历史修复经验。

### 12.2 需要创建的文件

```text
extensions/ai_coding/memory/
  writer.py
  retriever.py

extensions/ai_coding/tools/
  memory.py
```

### 12.3 记忆类型

- Project Fact：项目结构、技术栈、入口文件、测试命令。
- Task Memory：任务目标、涉及文件、最终方案。
- Error Memory：错误日志、根因、修复方式。
- Preference Memory：用户偏好的风格、输出格式和测试方式。

### 12.4 实现步骤

1. 实现 `write_memory(memory_item)`。
2. 实现 `retrieve_memory(query, project_id)`。
3. 记忆保存为摘要，不保存大段源码。
4. 为记忆添加 metadata：
   - project_id
   - task_type
   - related_files
   - confidence
   - created_at
5. 在 Context Engineering 中加入 memory 候选项。
6. 成功任务后写入有效方案。
7. 失败任务后写入失败原因和排查路径。

### 12.5 验收标准

- 第二次相似任务能召回历史经验。
- 记忆不会污染上下文，低相关记忆会被裁剪。
- 用户纠正后能写入 Preference Memory。

## 13. Module 11：子 Agent 协作

### 13.1 模块目标

对复杂代码任务进行角色拆分，提高检索、规划和验证质量。

### 13.2 子 Agent 角色

| 子 Agent | 职责 |
| --- | --- |
| Retrieval Agent | 分析任务并召回相关文件 |
| Context Agent | 构建和压缩 Context Package |
| Planning Agent | 生成修改计划和风险点 |
| Verification Agent | 分析测试命令和沙箱失败日志 |

### 13.3 实现步骤

1. 在 Workflow 中判断任务复杂度。
2. 简单任务走单 Agent 流程。
3. 复杂任务并行调用多个子 Agent。
4. 主 Agent 汇总子 Agent 输出。
5. 如果子 Agent 结论冲突，优先相信工具结果、测试结果和明确文件证据。

### 13.4 验收标准

- 多文件任务能拆分给多个子 Agent。
- 主 Agent 能合并结果并输出一致计划。
- 子 Agent 输出都能进入任务轨迹。

## 14. Module 12：测试与演示样例

### 14.1 Demo 仓库

创建一个小型 Python 项目作为演示仓库：

```text
demo_python_repo/
  pyproject.toml
  README.md
  src/
    calculator.py
    user_service.py
  tests/
    test_calculator.py
    test_user_service.py
```

### 14.2 测试场景

| 场景 | 用户输入 | 验证点 |
| --- | --- | --- |
| 功能开发 | 给 calculator 增加 divide 方法并补测试 | 能定位源码和测试文件 |
| Bug 修复 | 修复 user_service 登录空密码报错 | 能生成合理 Patch |
| 报错分析 | 输入 pytest traceback | 能召回堆栈相关文件 |
| 上下文工程 | 限制 token_budget 为 3000 | 能保留关键源码并裁剪低优先级内容 |
| 沙箱验证 | 运行 python -m pytest | 能返回结构化 SandboxResult |

### 14.3 测试命令

```bash
pytest extensions/ai_coding/tests
python -m pytest extensions/ai_coding/tests/test_workflow_smoke.py
```

### 14.4 验收标准

- 单元测试覆盖 chunker、context engineering、sandbox policy。
- 集成测试跑通从任务输入到 Patch Preview 的链路。
- 沙箱测试不会修改原始 demo 仓库。
- 最终输出能支撑简历中关于 Code RAG、Context Engineering、Tool Calling、Docker Sandbox、长期记忆的描述。

## 15. 推荐开发顺序

### Step 1：先做无模型版本

先不接真实 LLM，只实现：

- 仓库扫描
- Python 分块
- 关键词检索
- Context Package 组装
- Patch Preview 校验
- Sandbox Policy

这样可以先把工程骨架跑通。

### Step 2：接入 Embedding 和 Qdrant

完成：

- 向量索引
- 语义检索
- Reranker 重排
- 错误日志检索

### Step 3：接入 LLM 和 LangGraph

完成：

- 需求分析
- 查询改写
- 任务规划
- Patch 生成
- 失败反思

### Step 4：接入 Hermes

完成：

- Skill 注册
- Tool 注册
- Memory 接入
- 子 Agent 接入
- Docker Backend 复用

### Step 5：完善演示和简历材料

完成：

- Demo 仓库
- 三类任务样例
- 执行截图或日志
- README
- 简历项目描述

## 16. 最小可行版本范围

如果时间有限，MVP 只做以下内容：

- `ai-coding` Skill 文档。
- Repository Scan。
- Python AST Chunker。
- 简单关键词检索 + mock embedding。
- Context Package 组装。
- Patch Preview。
- Docker Sandbox 执行 `pytest`。
- 一条 Bug 修复示例链路。

MVP 不强制完成：

- 完整 Qdrant 集成。
- 完整 Reranker。
- 多语言 tree-sitter。
- 子 Agent 并行。
- 复杂长期记忆。

这样仍然可以体现：Hermes 框架扩展、Python Agent、代码 RAG 雏形、Context Engineering、Tool Calling、Docker Sandbox。

