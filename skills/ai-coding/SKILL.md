# ai-coding Skill

Use this skill when the user asks for code development, bug fixing, test repair, error analysis, code explanation, or repository-aware implementation work.

## Standard Flow

1. Understand the request and classify the task.
2. Scan the repository before planning edits.
3. Retrieve relevant code with keyword search, chunking, and mock embedding retrieval.
4. Build a token-budgeted Context Package.
5. Produce a Patch Preview as unified diff.
6. Validate the patch against the repository.
7. Run verification in a sandbox copy of the repository.
8. Return task summary, context sources, patch summary, sandbox result, and next steps.

## Safety Rules

- Do not read files outside the repository root.
- Do not execute dangerous commands.
- Prefer Patch Preview over direct writes.
- Run tests in an isolated copied repository.
- Do not store large source snippets in memory.

## MVP Tools

- `scan_repository`
- `read_file_slice`
- `search_code`
- `chunk_file`
- `retrieve_code_context`
- `build_context_package`
- `preview_patch`
- `validate_patch_against_repo`
- `run_pytest_sandbox`
- `run_pytest_docker_sandbox`
