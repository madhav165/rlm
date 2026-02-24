1. THE HUMAN MENTAL MODEL
Core Concept:  
Recursive Language Models (RLMs) solve the fundamental limitation of LLMs - their finite context window. RLMs enable LLMs to programmatically examine, decompose, and recursively call themselves over arbitrarily long inputs by replacing the standard llm.completion(prompt) call with rlm.completion(prompt). The system works by placing the input context in a Python REPL environment that the LM can interact with and launch sub-LM calls from, creating a tree of recursive reasoning.
Primary Flow:  
1. User calls rlm.completion(prompt) with their query and context
2. RLM spawns an isolated REPL environment containing the context as a context variable
3. The LM receives instructions about available functions (llm_query, rlm_query, FINAL_VAR, etc.)
4. LM responds with code blocks wrapped in triple backticks (e.g., repl code here repl)
5. RLM executes the code in the REPL, capturing stdout/stderr and any sub-LM calls made
6. Code execution results and outputs are fed back to the LM for the next iteration
7. Process repeats until LM provides a FINAL(...) or FINAL_VAR(...) answer
8. RLM returns the final answer
Domain Language & Structure:
- Root RLM: The top-level RLM instance spawned by user code
- Sub-RLM/Child RLM: Recursive RLM instances spawned via rlm_query()
- Iteration: One cycle of LM → code block → execution → feedback
- REPL Environment: The sandbox where code executes with access to context and sub-LM functions
- Depth: Recursion level (0 = root, 1+ = child RLMs)
- Final Answer: Triggered via FINAL("answer") or FINAL_VAR(var_name) in the response
- Context: The input data made available to the REPL as a variable
- llm_query(): Single-shot LM completion without REPL (fast, for simple tasks)
- rlm_query(): Recursive RLM call with its own REPL and iteration (for complex reasoning)
2. THE ENGINEERING BLUEPRINT
Tech Stack:
- Language: Python 3.11+ (strictly typed, type hints throughout)
- Package Manager: uv (for dependencies and virtual environments)
- Core Dependencies: anthropic, google-genai, openai, portkey-ai, pytest, python-dotenv, requests, rich
- Optional Extras: 
  - modal (modal, dill) - for Modal Sandboxes
  - e2b (e2b-code-interpreter, dill) - for E2B Sandboxes  
  - daytona (daytona, dill) - for Daytona Sandboxes
  - prime (prime-sandboxes, dill) - for Prime Intellect Sandboxes
- Visualization: Node.js 20+, Next.js 16, React 19, TailwindCSS 4, shadcn/ui components
- Code Quality: ruff (linter + formatter), pre-commit hooks, strict typing
Core Architecture:
rlm/
├── core/               # Core RLM logic and state machine
│   ├── rlm.py         # RLM class - main entry point
│   ├── lm_handler.py  # Multi-threaded TCP server for LM requests
│   ├── types.py       # Data models (REPLResult, RLMIteration, etc.)
│   └── comms_utils.py # Socket communication protocol
├── clients/           # LM client wrappers (OpenAI, Anthropic, etc.)
│   ├── base_lm.py     # Abstract base class
│   └── *.py           # Concrete client implementations
├── environments/      # REPL environments (Local, Modal, Docker, etc.)
│   ├── base_env.py    # Base classes and protocols
│   └── *_repl.py      # Concrete environment implementations
├── logger/            # Logging and visualization support
│   ├── rlm_logger.py  # Trajectory logging
│   └── verbose.py     # Console output with rich
└── utils/             # Helper functions
    ├── parsing.py     # Code block parsing, FINAL answer extraction
    ├── prompts.py     # System and user prompt templates
    └── token_utils.py # Token counting and limits
Key Entry Points:
- rlm.RLM class - User-facing interface for creating RLM instances
- rlm.RLM.completion(prompt) - Main method for RLM queries
- get_client(backend, kwargs) - Client factory function
- get_environment(env_type, kwargs) - Environment factory function
Data & Execution Flow:
1. Initialization: RLM config (backend, environment, depth limits, callbacks) is stored
2. Completion Call: Spawns fresh LMHandler (TCP server) and environment
3. Message History: System prompt + user metadata + iteration results built up
4. Iteration Loop (max max_iterations):
   - LM receives current message history + user prompt
   - LM responds with text containing ```repl code blocks
   - find_code_blocks() extracts code blocks
   - Each code block executes in environment via execute_code()
   - REPLResult captured (stdout, stderr, locals, execution_time, sub-LM calls)
   - Results formatted and appended to message history
   - Check for FINAL_VAR(...) or FINAL(...) in response
5. Sub-Call Handling (llm_query/rlm_query):
   - Environment sends socket request to LMHandler
   - LMHandler routes to appropriate client
   - Returns RLMChatCompletion response
   - For rlm_query at depth < max_depth: spawns child RLM
6. Termination: Returns RLMChatCompletion with final answer, usage, timing, metadata
State Management:
- Message history persists across iterations within a completion
- Environment locals persist across code blocks within an iteration (unless non-isolated with cleanup)
- Usage tracking per model via UsageSummary and ModelUsageSummary
- Sub-LM calls tracked in REPLResult.llm_calls for nested trajectory logging
- Optional trajectory logging via RLMLogger → JSONL files for visualizer
Developer Constraints:
1. Strict Typing: No # type: ignore without justification; explicit types preferred
2. Naming Conventions:
   - Methods: snake_case (e.g., execute_code, find_final_answer)
   - Classes: PascalCase (e.g., LocalREPL, PortkeyClient)
   - Constants: UPPER_CASE (e.g., RLM_SYSTEM_PROMPT, _SAFE_BUILTINS)
   - NO _ prefix for private methods unless explicitly requested
3. Error Handling: "Fail fast, fail loud" - no silent fallbacks; missing API key → immediate ValueError
4. Code Style: ruff enforced - ruff check --fix . and ruff format . must pass
5. Single Responsibility: One change per PR; small, focused diffs
6. No Dead Code: Delete rather than guard with conditionals
7. Environment Safety: Custom tools cannot override reserved names (llm_query, rlm_query, context, FINAL_VAR, SHOW_VARS, history)
8. Persistence Support: Only environments implementing SupportsPersistence protocol support persistent=True mode (currently only local)
9. Client Pattern: All clients must inherit from BaseLM and implement completion, acompletion, get_usage_summary, get_last_usage
Onboarding Commands:
# Install dependencies
uv sync                           # base dependencies
uv sync --group dev --group test  # dev + test dependencies
# Development
uv run ruff check --fix .         # lint with auto-fix
uv run ruff format .              # format code
uv run pytest                     # run tests
uv run pre-commit install         # install pre-commit hooks
# Quick start (requires OPENAI_API_KEY or PORTKEY_API_KEY)
make quickstart                   # runs examples/quickstart.py
# Environment-specific
uv pip install -e ".[modal]"      # Modal support
uv pip install -e ".[prime]"      # Prime support
# Visualization
cd visualizer
npm run dev                       # run visualizer on localhost:3001
Project Structure Summary:
- Core Engine (rlm/core/): RLM state machine, LM routing, communication protocol
- Client Layer (rlm/clients/): LM provider wrappers (OpenAI, Anthropic, Portkey, LiteLLM, etc.)
- Environment Layer (rlm/environments/): REPL execution sandboxes (local, Docker, Modal, Prime, Daytona, E2B)
- Logging/Visualization (rlm/logger/, visualizer/): Trajectory capture and web-based inspection
- Utilities (rlm/utils/): Prompt templates, code parsing, token counting
