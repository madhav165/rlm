# RLM Rebuild Plan

This is a code-faithful architecture recommendation for `rlm` based on the current repository shape.

## Goal

Keep the redesign close to the code that already exists, while making the hard boundaries explicit:

- orchestration
- protocol / typed data
- execution environments
- clients / backends
- logging and metadata
- shared prompt and parsing helpers

The main design target is to keep recursive execution, model calls, and sandbox execution separable without inventing extra top-level subsystems.

## Recommended Shape

### 1. `rlm/core`

This package should own the orchestration layer and stay focused on request lifecycle control.

Keep here:

- `rlm/core/rlm.py` for the recursive completion loop
- `rlm/core/lm_handler.py` for LM request routing and handler lifecycle
- `rlm/core/comms_utils.py` for socket framing and request/response transport helpers
- `rlm/core/types.py` for the typed request/result/configuration objects

Why:

- the current code already uses this split
- orchestration and transport are tightly coupled
- keeping them together avoids pushing control-plane logic into the environments

### 2. `rlm/environments`

This package should own the execution body of the system.

Keep here:

- `rlm/environments/base_env.py` for base classes and protocols
- `rlm/environments/local_repl.py` for the in-process REPL runtime
- `rlm/environments/modal_repl.py`, `docker_repl.py`, `daytona_repl.py`, `prime_repl.py`, `e2b_repl.py` for isolated backends
- REPL state persistence
- custom tools and MCP tool injection
- `llm_query`, `llm_query_batched`, `rlm_query`, `rlm_query_batched`
- `FINAL_VAR`, `SHOW_VARS`
- context/history handling

Why:

- the REPL is the execution environment, not a separate platform layer
- recursive subcalls are exposed as environment functions, so they belong here
- state persistence and tool injection are part of environment behavior, not core orchestration

### 3. `rlm/clients`

This package should remain the provider abstraction layer.

Keep here:

- `rlm/clients/base_lm.py`
- provider-specific client implementations
- model-specific auth, transport, retries, and usage tracking

Why:

- this is already the natural boundary for backend differences
- `BaseLM` is a useful abstraction and should stay narrow
- orchestration should not import provider SDKs directly

### 4. `rlm/utils`

This package should hold shared helpers that are not stable enough to justify a new top-level domain.

Keep here:

- prompt synthesis helpers
- code-block parsing and final-answer extraction
- runtime guardrails / exceptions
- token counting / context helpers
- other small validation utilities

Why:

- the current repo already uses `utils` this way
- these are supporting functions, not a separate architectural pillar
- demoting them avoids the “junk drawer” problem at the top level

### 5. `rlm/logger`

This package should continue to own logging and metadata capture.

Keep here:

- iteration logging
- execution metadata capture
- trace/output persistence
- verbose output helpers

Why:

- the repo already separates logging from orchestration
- keeping trace capture here avoids inventing a separate provenance layer

## What Should Stay Together

These should remain together because the code already treats them as one cohesive responsibility:

- `RLM` orchestration, request lifecycle, and recursion control
- `LMHandler` startup/shutdown and request routing
- socket protocol helpers and the handler transport path
- REPL state, context, and `llm_query` / `rlm_query` helpers
- persistence, custom tools, and MCP injection within environments
- typed results and metadata objects that move between core and environments

## What Should Be Separated

Separate these boundaries because the code already shows them as different concerns:

- orchestration vs provider-specific client code
- orchestration vs REPL execution
- shared typed objects vs behavior
- logging/metadata capture vs core control flow
- prompt-building helpers vs core request lifecycle
- parsing helpers vs execution logic

## What to Demote or Delete

The earlier broader plan overfit the critique. These should not become new top-level packages:

- `policy`
- `prompting`
- `state`
- `streaming`
- `provenance`
- `lifecycle`

Keep those as internal concerns inside `core`, `environments`, `utils`, or `logger` unless the codebase later grows enough to justify promotion.

Why:

- the current code does not warrant that many top-level pillars
- the design should stay faithful to the repository as it exists
- splitting too aggressively makes the plan less realistic and harder to implement

## Dependency Direction

Use a strict inward dependency model:

- `clients` and `environments` depend on `core/types`
- `core` depends on `core/types` and abstract interfaces only
- `logger` depends on `core/types`, not vice versa

Nothing in `core` should import provider SDKs or sandbox-specific machinery directly.

Why:

- preserves substitutability
- keeps the orchestration core portable
- makes the system easier to test without network access or sandboxes

## Runtime Flow

1. A caller creates a normalized request.
2. `core` resolves the target model and execution policy.
3. `core` invokes a `BaseLM` client or an environment callback.
4. The result is wrapped in the existing typed result objects (`RLMChatCompletion`, `REPLResult`, `RLMIteration`).
5. Usage, traces, and final output are persisted or returned through the logger and metadata fields that already exist.

Recursive child calls should use the same contract as top-level calls.

Why:

- one request shape across the stack
- fewer special cases in recursive logic
- easier to reason about failure and retry behavior

## Practical Repo Layout

```text
rlm/
  core/
    rlm.py
    lm_handler.py
    comms_utils.py
    types.py
  clients/
    base_lm.py
    openai.py
  environments/
    base_env.py
    local_repl.py
    modal_repl.py
  logger/
    rlm_logger.py
  utils/
    prompts.py
    parsing.py
    exceptions.py
    token_utils.py
  ui/
    components/
    layout/
    primitives/
```

## Synthesis

The design is not really “more modules.” It is a redefinition of the system around a few hard boundaries:

1. `core` decides what should happen.
2. `utils/prompts` and `utils/parsing` decide how prompts and answers are shaped.
3. `utils/exceptions` and `core` enforce limits and guardrails.
4. `clients` or `environments` decide where it runs.
5. `logger` and the typed result objects preserve the trace and final state.
6. `environments` decide what can be safely shared across recursive steps.

That is the actual shape of the runtime.

The key takeaway from the critique is that recursive RLM is not just a completion engine with extra helpers. It is a stateful control system. The architecture should therefore treat:

- recursion as control flow
- prompt synthesis as execution correctness
- guardrails as an admission gate
- environment state as forked, not shared

This is why the redesign removes convenience in exchange for safety and clarity.

## What This Gives Up

This plan intentionally makes the following harder:

- ad hoc direct calls that bypass orchestration
- implicit shared REPL state between parent and child execution
- mixing prompt formatting with client logic
- treating logging as sufficient provenance
- having one-off behavior live inside `core`
- attaching new functionality without choosing the right boundary first

That tradeoff is deliberate. The current repo is flexible in places because boundaries are loose. The redesign prefers explicit contracts over convenience, because recursive execution gets brittle fast when the state model is not formalized.
