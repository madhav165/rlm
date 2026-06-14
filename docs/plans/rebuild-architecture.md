# RLM Rebuild Plan

This is a code-faithful architecture recommendation for `rlm` based on the current repository shape.

## Goal

Build a small core that is explicit about boundaries:

- inference orchestration
- client adapters
- execution environments
- logging and metadata
- shared types and protocol objects

The main design target is to keep recursive execution, model calls, and sandbox execution separable without inventing a large new hierarchy of packages.

## Recommended Shape

### 0. Split The Repository Into Two Explicit Domains

The graph results show two distinct areas:

- the RLM inference and execution engine
- the structured UI/component library

These should be treated as separate product surfaces with separate boundaries, even if they live in one repo.

Why:

- they change for different reasons
- they have different dependency patterns
- mixing them makes the core library harder to evolve cleanly

### 1. `rlm/core`

Own all request lifecycle logic:

- completion entrypoints
- recursive execution loop
- routing to child calls
- depth / iteration limits
- retry and fallback policy
- metadata envelope creation

This should be the only layer that knows how the RLM loop works end to end.

Why:

- keeps orchestration deterministic
- prevents execution policy from leaking into clients or environments
- makes the recursive loop easier to test in isolation

### 2. `rlm/clients`

Put every LM provider integration behind a narrow `BaseLM` interface.

Each client should:

- accept a normalized request object
- return a normalized completion object
- track usage in a shared format
- hide provider-specific auth, transport, and retries

Why:

- avoids provider logic spreading through the core
- makes adding or replacing providers low risk
- keeps the orchestration layer from depending on vendor APIs

### 3. `rlm/environments`

Treat environments as execution backends for code or tool-driven loops.

Each environment should:

- expose a stable execution contract
- load context explicitly
- provide `llm_query` and `rlm_query`
- return one result envelope type
- clean up all state on exit

Why:

- execution is a separate concern from model inference
- isolated and non-isolated backends need different plumbing
- environment implementations stay swappable if the interface is stable

### 4. `rlm/core/types`

Centralize all cross-cutting data structures:

- request / response payloads
- usage summaries
- iteration records
- execution metadata
- environment results

Why:

- prevents type drift across modules
- reduces conversion code
- makes serialization and persistence straightforward

### 5. Cross-Cutting Concerns as Modules, Not New Pillars

The current code already has concrete places for the concerns that were previously split into separate top-level subsystems:

- `rlm/utils/prompts.py` for prompt synthesis and metadata-driven prompt building
- `rlm/utils/parsing.py` for code-block extraction and final-answer parsing
- `rlm/logger/` for logging, iteration capture, and metadata persistence
- `rlm/utils/exceptions.py` for runtime guardrails and failure modes
- `rlm/environments/` for REPL state, persistence, cleanup, and nested-call behavior

These concerns should stay as modules or internal subpackages unless they grow enough code to justify promotion.

Why:

- the repository already expresses these responsibilities without extra package layers
- the current code favors direct functional boundaries over deep architectural layering
- promoting every concern to its own top-level domain would make the plan less faithful to the code

## Dependency Direction

Use a strict inward dependency model:

`clients` and `environments` depend on `core/types`

`core` depends on `core/types` and abstract interfaces only

`logger` depends on `core/types`, not vice versa

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

## What I Would Avoid

- provider SDK calls in orchestration code
- environment-specific branching in the core loop
- multiple overlapping metadata schemas
- implicit globals for context or state
- silent fallback behavior
- pretending `core` and `core/types` are always cleanly separable; the boundary needs to be carefully designed so shared types do not become a dumping ground for policy
- treating prompt formatting as a tiny utility when it is actually a model-aware step
- allowing recursive execution to share mutable REPL state between parent and child calls
- inventing a streaming subsystem unless the codebase actually grows streaming semantics

Why:

- each of those makes the system harder to extend and debug
- the repo already shows that execution metadata and routing need to stay tightly controlled

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
ui/
  components/
  layout/
  primitives/
```

## Why This Works

This layout keeps the codebase aligned around the actual runtime boundaries:

- model calls
- recursive orchestration
- execution environments
- logger / metadata capture
- shared protocol types

That separation makes the library easier to extend without changing the core recursion model every time a new backend or environment is added.

## Synthesis

The design is not really "more modules." It is a redefinition of the system around a few hard boundaries:

1. `core` decides what should happen.
2. `utils/prompts` and `utils/parsing` decide how prompts and answers are shaped.
3. `utils/exceptions` and `core` enforce limits and guardrails.
4. `clients` or `environments` decide where it runs.
5. `logger` and the typed result objects preserve the trace and final state.
6. `environments` decide what can be safely shared across recursive steps.

That is the actual shape of the runtime.

The biggest synthesis from the critique is that recursive RLM is not just a completion engine with extra helpers. It is a stateful control system. The architecture should therefore treat:

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
