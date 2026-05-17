# Findings

## Source Documents

- `module_implementation.md` defines the MVP scope as: `ai-coding` Skill docs, Repository Scan, Python AST Chunker, simple keyword retrieval plus mock embedding, Context Package assembly, Patch Preview, Docker Sandbox executing `pytest`, and one bug fix example chain.
- The practical first loop can run locally without Hermes deployment or real LLM integration.

## Implementation Notes

- The MVP should expose normal Python functions first, so later Hermes plugin registration can wrap those functions as tools.
