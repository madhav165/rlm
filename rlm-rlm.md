### 1. THE HUMAN MENTAL MODEL

**Core concept:**
RLM (Recursive Language Models) is a framework that enables LLMs to solve complex problems through iterative computation and recursive reasoning. It provides a REPL environment where LLMs can write and execute Python code, query sub-LLMs for assistance, and maintain context across iterations. Think of it as giving an LLM the ability to 'think step-by-step' with the computational power of a Python interpreter and the collaborative intelligence of other LLMs.
**Primary flow:**
1. User submits a query to the RLM with specified backend (OpenAI, Anthropic, etc.) and environment (local, Docker, Modal, etc.)
2. RLM initializes a REPL environment with specialized functions: llm_query() for simple LLM calls, rlm_query() for recursive reasoning
3. The model writes code to solve the problem, potentially spawning sub-calls to other LLMs
4. Code is executed safely in an isolated environment with restricted builtins
5. Results are parsed for code blocks and final answers
6. If compaction is enabled, long trajectories are summarized to stay within context limits
7. Execution continues until a final answer is found or constraints are exceeded
**Domain language & structure:**
- **Iteration**: Each cycle of code execution + LLM response
- **Trajectory**: Complete sequence of iterations leading to final answer
- **Compaction**: Summarization of earlier iterations to manage context length
- **Environment**: Execution context (local, Docker, Modal, Prime, Daytona, e2b)
- **Backend**: LLM provider (OpenAI, Anthropic, Azure OpenAI, Gemini, etc.)
- **History**: Accumulated context including earlier iterations and compactions

### 2. THE ENGINEERING BLUEPRINT
**Tech stack:**
- **Language**: Python 3.11+ (primary), TypeScript/React for web dashboard
- **Core frameworks**: Python: pyproject.toml with uv dependency management, Frontend: Next.js 14 with TypeScript, TailwindCSS
- **Key dependencies**: anthropic>=0.75.0, google-genai>=1.56.0, openai>=2.14.0, portkey-ai>=2.1.0, modal>=0.73.0 (optional)
- **Testing**: pytest>=9.0.2
- **Development tools**: ruff (linting/formatting), ty (type checking)

**Core architecture:**
The project follows a layered architecture:
- rlm/ (core library)
  - clients/ (LLM backend integrations: OpenAI, Anthropic, Gemini, Portkey, etc.)
  - environments/ (execution environments: local, Docker, Modal, Prime, Daytona, e2b)
  - core/ (core types and utilities: types.py, comms_utils.py, lm_handler.py)
  - utils/ (helper utilities: parsing.py, prompts.py, token_utils.py, exceptions.py)
- examples/ (example scripts: quickstart.py, logger_example.py, etc.)
- dashboard/ (Next.js web interface)

**Data & execution flow:**
1. **Initialization**: RLM() constructor creates backend client and environment
2. **Execution**: .run() method sets up environment with safe builtins and custom tools, sends system prompt, parses responses
3. **Iteration loop**: Continues until final answer found, budget exceeded, timeout reached, or token limit hit
4. **Communication**: Socket-based protocol between main process and environment subprocesses
5. **Compaction**: Long trajectories are optionally summarized to manage context length

**Developer constraints:**
- **Reserved tool names**: llm_query, rlm_query, FINAL_VAR, SHOW_VARS, context, history cannot be overridden
- **Safe execution**: REPL environments use _SAFE_BUILTINS with dangerous functions removed
- **Context limits**: Models have specified token limits; compaction triggers at 80% of limit by default
- **Custom tools**: Must return JSON-serializable values

**Onboarding:**
```bash
# Install dependencies
make install        # Base dependencies
make install-dev    # Dev dependencies (ruff, pytest)

# Run examples
make quickstart     # Run quickstart.py (needs OPENAI_API_KEY)
make docker-repl    # Run Docker REPL example (needs Docker)
make lm-repl        # Run LM in REPL example
make modal-repl     # Run Modal example (needs Modal account)

# Development
make lint           # Run ruff linter
make format         # Run ruff formatter
make test           # Run pytest
make check          # Run lint + format + tests

