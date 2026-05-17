# Hermes Agent AI Coding Extension Implementation Guide

## 1. 实现目标

本实现文档描述如何在 Hermes Agent 原有框架上落地 AI Coding 扩展。实现重点不是构建平台，而是在 Hermes 的 Skill、Tool、Memory、Sub-agent、Docker Backend 等能力上增加代码任务处理链路。

最终交付物应包含：

- `ai-coding` Skill：定义代码任务处理规范和提示词模板。
- AI Coding Toolset：封装代码扫描、检索、上下文构建、Patch 预览和沙箱验证工具。
- Code RAG Engine：支持代码库分块、向量化、Qdrant 检索和 Reranker 重排。
- Context Engineering 模块：生成受 Token 预算约束的 Context Package。
- LangGraph Workflow：编排从需求理解到记忆回写的完整 Agent 流程。
- Docker Sandbox：隔离执行测试命令并反馈失败原因。
- 示例任务和测试用例：验证功能开发、Bug 修复、报错分析三类场景。

## 2. 建议目录结构

若直接扩展 Hermes Agent 仓库，建议新增以下目录：

```text
hermes-agent/
  skills/
    ai-coding/
      SKILL.md
      prompts/
        requirement_analysis.md
        query_rewrite.md
        context_package.md
        patch_generation.md
        reflection.md
      examples/
        bugfix_task.md
        feature_task.md
        error_analysis_task.md

  extensions/
    ai_coding/
      __init__.py
      workflow.py
      config.py
      schemas.py
      context_engineering.py
      rag/
        __init__.py
        indexer.py
        chunker.py
        embeddings.py
        retriever.py
        reranker.py
      tools/
        __init__.py
        repository.py
        search.py
        patch.py
        sandbox.py
        memory.py
      sandbox/
        Dockerfile.python
        runner.py
        policy.py
      memory/
        writer.py
        retriever.py
      tests/
        test_context_engineering.py
        test_chunker.py
        test_sandbox_policy.py
        test_workflow_smoke.py
```

如果暂时不改 Hermes 源码，也可以将 `extensions/ai_coding` 作为独立 Python 包实现，再通过 Hermes Tool/Skill 配置接入。

## 3. 依赖建议

```text
python >= 3.10
langgraph
qdrant-client
pydantic
tree-sitter 或 ast
sentence-transformers 或外部 embedding API
docker
unidiff
rich
```

可选依赖：

- `tiktoken`：Token 预算估算。
- `rank-bm25`：混合检索。
- `watchfiles`：监听代码变动并增量索引。
- `gitpython`：读取 Git 状态和最近修改文件。

## 4. 核心数据结构

### 4.1 CodingTask

```python
class CodingTask(BaseModel):
    task_id: str
    repo_path: str
    user_request: str
    task_type: Literal["feature", "bugfix", "refactor", "explanation", "test"]
    constraints: list[str] = []
    max_iterations: int = 3
    token_budget: int = 24000
```

### 4.2 CodeChunk

```python
class CodeChunk(BaseModel):
    chunk_id: str
    project_id: str
    path: str
    language: str
    file_type: Literal["source", "test", "doc", "config", "script"]
    symbol_name: str | None = None
    start_line: int
    end_line: int
    content: str
    metadata: dict = {}
```

### 4.3 ContextPackage

```python
class ContextPackage(BaseModel):
    task: dict
    repository: dict
    retrieved_context: dict
    memory: dict
    tool_results: dict
    execution_feedback: dict | None = None
    token_estimate: int
```

### 4.4 SandboxResult

```python
class SandboxResult(BaseModel):
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    failure_summary: str | None = None
```

## 5. 实现阶段

### Phase 1：Skill 骨架

目标：让 Hermes Agent 能识别并进入 AI Coding 任务模式。

任务：

- 新增 `skills/ai-coding/SKILL.md`。
- 定义适用场景：功能开发、Bug 修复、报错分析、代码解释、测试补全。
- 定义执行规则：先检索、再组装上下文、再计划、再 Patch、再验证。
- 定义安全规则：不直接改写文件，默认生成 Patch 预览；命令执行走沙箱。
- 编写 prompts 模板，包括需求分析、查询改写、上下文包、Patch 生成和失败反思。

验收标准：

- 用户输入代码任务时，Hermes 能根据 Skill 文档选择 AI Coding 流程。
- Skill 文档清楚约束工具调用顺序和输出格式。

### Phase 2：代码库扫描与分块

目标：把目标仓库转化为结构化代码块。

任务：

- 实现 `scan_repository(repo_path)`，输出文件树、语言栈、入口文件和依赖文件。
- 实现文件过滤规则，跳过 `.git`、`.venv`、`node_modules`、`dist`、`build`、大文件和二进制文件。
- 实现 `chunk_file(path)`，优先按函数、类、模块边界分块。
- 对 Python 文件优先使用 `ast` 分块；其他语言使用启发式规则或 tree-sitter。
- 为每个代码块生成 `CodeChunk`，包含路径、语言、起止行号、符号名和内容。

验收标准：

- 能扫描一个示例仓库并输出结构化文件清单。
- 能对 Python 源码按类和函数分块。
- 对无法解析的文件能退化为固定行数窗口分块。

### Phase 3：Code RAG

目标：支持通过自然语言任务召回相关代码。

任务：

- 实现 `index_repository(repo_path, project_id)`。
- 调用 Embedding 模型为 `CodeChunk` 生成向量。
- 将向量、正文和元数据写入 Qdrant。
- 实现 `retrieve_code_context(query, project_id, top_k)`。
- 实现 Reranker 重排，将相关性更高的源码、测试和配置文件提前。
- 支持混合检索：向量检索 + 关键词搜索 + 错误堆栈路径命中。

验收标准：

- 输入功能需求时，能召回相关源码和测试文件。
- 输入错误日志时，能优先召回堆栈中涉及的文件。
- Reranker 后的 Top-K 结果比纯向量检索更稳定。

### Phase 4：Context Engineering

目标：将代码、记忆、工具结果和错误日志组装成可控上下文包。

任务：

- 实现 `build_context_package(task, repo_summary, chunks, memory, tool_results, feedback)`。
- 实现上下文评分：语义相关性、路径命中、依赖关系、测试相关性、历史任务相关性。
- 实现去重：同一文件相邻片段合并，同一内容多次召回只保留最高分。
- 实现压缩：低优先级内容转摘要，高优先级源码保留完整片段。
- 实现 Token 预算控制，超过预算时按优先级裁剪。
- 输出结构化 JSON 和面向 Prompt 的 Markdown 两种格式。

验收标准：

- Context Package 包含用户需求、仓库摘要、相关源码、测试/配置、记忆和错误反馈。
- 在设定 Token 预算内优先保留关键源码。
- 对同一任务，多次构建结果稳定且可解释。

### Phase 5：LangGraph Workflow

目标：编排完整 AI Coding 流程。

任务：

- 实现 `workflow.py`，定义节点和状态。
- 节点包括：Requirement Analyzer、Query Rewriter、Code Retriever、Context Builder、Task Planner、Tool Executor、Patch Generator、Sandbox Verifier、Reflection、Memory Writer。
- 每个节点输入输出使用 Pydantic Schema 约束。
- 支持最多 3 次失败反思迭代。
- 支持复杂任务调用 Hermes 子 Agent：检索 Agent、上下文 Agent、规划 Agent、验证 Agent。

验收标准：

- 输入一个 Bug 修复任务，Workflow 能产出计划、相关文件、Patch 草案和验证建议。
- 沙箱失败后能进入 Reflection 节点并进行第二轮上下文补充。
- 达到最大迭代次数后能输出失败原因和下一步建议。

### Phase 6：Toolset 接入 Hermes

目标：将 AI Coding 能力暴露为 Hermes 可调用工具。

任务：

- 注册 `scan_repository`、`read_file_slice`、`search_code`、`index_repository`、`retrieve_code_context`、`build_context_package`、`preview_patch`、`run_in_docker`、`analyze_failure`、`write_memory`。
- 每个工具定义清晰输入、输出和错误格式。
- 工具默认不进行破坏性操作。
- Patch 工具只生成 diff 和变更摘要，真实写入由 Hermes 原有权限机制控制。

验收标准：

- Hermes Agent 能在 coding 任务中调用新增工具。
- 工具调用日志能被记录到任务轨迹。
- 工具失败时返回结构化错误，不中断整个任务链路。

### Phase 7：Docker Sandbox

目标：隔离执行测试和静态检查。

任务：

- 实现 `run_in_docker(image, command, repo_path, patch)`。
- 将仓库复制到临时目录并应用 Patch。
- 使用容器执行测试命令，默认关闭网络。
- 限制 CPU、内存、执行时间和挂载路径。
- 实现命令风险扫描，拦截危险命令。
- 返回 `SandboxResult`。

验收标准：

- 能在容器中运行 `pytest`、`python -m pytest`、`npm test` 等常见命令。
- 高风险命令被拒绝执行。
- stdout、stderr、exit code 和失败摘要被完整返回。

### Phase 8：长期记忆

目标：让 Agent 在跨会话任务中复用经验。

任务：

- 实现 `write_memory`，记录项目结构、历史任务、错误修复经验和用户偏好。
- 实现 `retrieve_memory`，根据当前任务检索相关记忆。
- 将记忆结果注入 Context Package。
- 成功任务写入有效方案，失败任务写入排查路径和失败原因。

验收标准：

- 第二次处理相似任务时能召回历史修复经验。
- 记忆内容以摘要为主，不保存大段源码。
- 记忆内容能被 Context Engineering 模块排序和裁剪。

## 6. 关键接口设计

### 6.1 Python API

```python
def index_repository(repo_path: str, project_id: str) -> IndexSummary:
    """Scan, chunk, embed, and store repository chunks."""

def run_coding_task(task: CodingTask) -> CodingTaskResult:
    """Run the full AI Coding workflow."""

def build_context_package(input: ContextBuildInput) -> ContextPackage:
    """Build a token-budgeted context package."""

def run_patch_verification(input: SandboxInput) -> SandboxResult:
    """Verify a patch in Docker sandbox."""
```

### 6.2 CLI 示例

```bash
hermes ai-coding index --repo ./demo-project --project demo
hermes ai-coding run --repo ./demo-project --task "修复登录接口 500 错误"
hermes ai-coding verify --repo ./demo-project --patch .hermes-ai-coding/patches/task-001.diff
```

### 6.3 任务输出格式

````markdown
## Task Summary
- Task type:
- Target files:
- Risk level:

## Context Used
- Source files:
- Tests:
- Configs:
- Memories:

## Plan
1.
2.
3.

## Patch Preview
```diff
...
```

## Sandbox Result
- Command:
- Exit code:
- Summary:

## Final Notes
- What changed:
- Why:
- Follow-up:
````

## 7. 测试方案

### 7.1 单元测试

- `test_chunker.py`：验证 Python 函数、类、普通文本分块。
- `test_context_engineering.py`：验证上下文排序、去重、压缩和 Token 预算。
- `test_sandbox_policy.py`：验证危险命令识别和沙箱参数生成。
- `test_memory.py`：验证记忆写入、检索和摘要格式。

### 7.2 集成测试

- 示例功能开发任务：新增一个简单函数并补测试。
- 示例 Bug 修复任务：根据错误日志定位并生成修复 Patch。
- 示例报错分析任务：输入 pytest 失败日志，输出根因和修复建议。
- 沙箱验证任务：应用 Patch 后执行测试，返回结构化结果。

### 7.3 对比测试

- 对比纯向量检索与 Reranker 重排后的相关文件命中率。
- 对比未使用 Context Engineering 与使用上下文排序/压缩后的无关上下文占比。
- 对比无长期记忆与有长期记忆时相似任务的计划质量。

## 8. 里程碑

### Milestone 1：最小可用扩展

- 完成 `ai-coding` Skill。
- 完成仓库扫描、Python 分块、关键词检索。
- 完成 Context Package 基础版。
- 可输出任务计划和 Patch 草案。

### Milestone 2：RAG 与上下文工程增强

- 接入 Qdrant。
- 接入 Embedding 与 Reranker。
- 完成 Token 预算控制、上下文排序、去重和压缩。
- 支持错误日志驱动检索。

### Milestone 3：沙箱验证闭环

- 完成 Docker Sandbox。
- 支持 Patch 应用和测试命令执行。
- 支持失败反思和二次修正。

### Milestone 4：长期记忆与子 Agent

- 接入 Hermes Memory。
- 复杂任务拆分给检索、上下文、规划、验证子 Agent。
- 完成跨会话任务经验复用。

## 9. 风险与处理

| 风险 | 影响 | 处理方式 |
| --- | --- | --- |
| 代码分块不准确 | 检索片段不完整 | Python 优先 AST，其他语言使用 tree-sitter 或窗口分块兜底 |
| 上下文过长 | LLM 忽略关键信息 | 使用 Token 预算、排序、去重、压缩 |
| Patch 无法应用 | 验证流程中断 | Patch 预览前做文件版本校验和冲突检测 |
| 沙箱命令有风险 | 可能破坏环境 | Docker 隔离、禁网、资源限制、命令拦截 |
| 长期记忆污染 | 后续任务被错误经验影响 | 记忆保存摘要和置信度，允许用户纠正 |
| 子 Agent 结果冲突 | 主 Agent 决策困难 | 主 Agent 按证据来源、工具结果和测试反馈排序 |

## 10. 验收标准

项目完成后应满足：

- 能在 Hermes Agent 中以 Skill 形式触发 AI Coding 流程。
- 能对示例仓库建立索引并召回相关代码片段。
- 能生成结构化 Context Package，并控制在 Token 预算内。
- 能根据需求输出任务计划、目标文件、Patch 草案和测试建议。
- 能在 Docker 沙箱中执行验证命令并返回结构化结果。
- 能将成功经验和失败原因写入长期记忆，并在相似任务中召回。
- 文档、示例和测试足以支撑简历项目描述中的技术点。
