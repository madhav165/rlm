# RLM Rewrite Architecture

## Goal

If this repository were rebuilt from scratch, I would keep the same product shape but make the architecture more explicit:

- one core orchestration layer
- thin LM client adapters
- thin execution environment adapters
- a small set of typed result and metadata envelopes
- no hidden fallbacks or implicit state mutation

The current design already points in this direction: `BaseLM`-style clients, `NonIsolatedEnv` / `IsolatedEnv` environments, request routing through `llm_query` and `rlm_query`, and typed result wrappers like `REPLResult` and `RLMChatCompletion`. A rewrite should preserve those seams and make them first-class.

## Recommended Shape

Use a ports-and-adapters layout.

### 1. Core domain

Keep the core package narrow and deterministic. It should own:

- request and response types
- execution envelopes
- iteration state
- usage accounting
- routing rules
- abstract interfaces for clients and environments

This layer should not know about any specific provider, sandbox, socket server, or cloud tunnel.

### 2. LM clients as adapters

Each provider client should implement the same `BaseLM` contract.

Responsibilities:

- normalize prompt input
- map prompt/messages to provider requests
- execute sync and async completion paths
- track usage per model
- return a typed completion payload

The client layer should stay thin. It should not own orchestration policy, retry strategy, or environment semantics.

### 3. Environments as adapters

Each environment should implement the same execution contract, with separate adapters for:

- local execution
- isolated/cloud execution
- sandbox communication

Responsibilities:

- create an execution namespace
- expose `llm_query`, `llm_query_batched`, `rlm_query`, and `rlm_query_batched`
- execute code
- capture stdout/stderr/result metadata
- preserve state across iterations only when the environment contract requires it

The environment should not decide how model selection works. It should only execute code against the orchestration surface it is given.

### 4. Orchestration layer

The orchestrator should be the only place that knows how the pieces fit together.

Responsibilities:

- resolve the model
- build the execution context
- choose between plain LM completion and recursive RLM execution
- manage request lifecycle state and `request_id` correlation
- enforce iteration and depth limits
- attach request IDs and usage metadata
- convert raw execution output into final typed results

This is the place for `completion`, `rlm_query`, request routing, and result finalization.

## Execution Flow

The flow I would use is:

1. Accept a prompt, messages, or code block as a typed request.
2. Normalize input into a request envelope.
3. Resolve model and environment.
4. Execute through a client or environment adapter.
5. Collect usage, timing, and request correlation data.
6. Return a typed result object.
7. If recursive execution is requested, spawn a child execution with explicit depth and termination rules.

That matches the repository’s existing behavior but makes every transition explicit.

## Data Model

Use a small set of stable envelopes instead of ad hoc dicts.

- `CompletionRequest`
- `CompletionResponse`
- `ExecutionContext`
- `REPLResult`
- `RLMChatCompletion`
- `RLMIteration`
- `UsageSummary`

These should be immutable or effectively immutable at the boundary. Internal mutation should stay localized to the orchestrator or adapter implementation.

## What To Preserve

These are the pieces I would keep:

- the `BaseLM` abstraction
- the environment abstraction split between local and isolated execution
- explicit batched and recursive query paths
- request/response correlation via `request_id`
- usage accounting per model
- a result envelope for code execution and chat execution
- the ability to call `llm_query` and `rlm_query` from within environments

Those are the stable seams that make the library extensible.

## What I Would Change First

1. Make the orchestration API fully typed and centralize it.
2. Reduce cross-module coupling by moving any policy out of clients and environments.
3. Replace implicit response shaping with explicit result envelopes.
4. Make state transitions visible: init, iterate, complete, fail.
5. Standardize error handling so contract violations fail fast and consistently.

## Testing Strategy

I would organize tests around behavior, not implementation details.

### Unit tests

- client request shaping
- usage tracking
- prompt normalization
- environment setup and cleanup
- request routing
- recursive depth limits

### Integration tests

- local environment executing code with mocked LM requests
- isolated environment broker flow
- batched completions
- recursive completions
- request ID propagation
- request lifecycle wait/notify behavior
- sandboxed execution flow

### Contract tests

- every client satisfies the same `BaseLM` contract
- every environment exposes the same query functions
- every result type preserves required metadata
- execution envelopes preserve state across pending, running, and finalized phases

The main goal is to keep tests deterministic and cheap. External providers and sandbox backends should be mocked unless the test is explicitly an integration test.

## Tradeoffs

This architecture is slightly more opinionated than the current implementation, but that is the point.

Benefits:

- easier to extend with new clients and environments
- clearer failure boundaries
- simpler testing
- less accidental coupling
- easier reasoning about execution state

Costs:

- more up-front typing and envelope definitions
- a little more boilerplate in adapters
- stricter separation may require refactoring some convenience paths

I think that tradeoff is worth it for this repository because the core value of `rlm` is its execution model, not ad hoc flexibility.

## Re-query Takeaways

The refreshed graph responses reinforced a few concrete boundaries worth treating as first-class:

- `request_lifecycle_management` should own wait/notify semantics and final response delivery.
- `ExecutionRuntimeContext` should be the explicit carrier for execution state and telemetry.
- `response_stream` should stay distinct from the final response object.
- `Sandboxed Execution Environment` should remain an edge adapter, not part of core orchestration policy.
- `Execution Environment Parameters` and `model_configuration_and_prompt` belong near the orchestration boundary, not inside clients or environments.

## Bottom Line

If I were restarting this repo, I would build a small, typed orchestration core and hang everything else off adapter interfaces. Keep clients dumb, keep environments dumb, keep the execution policy central, and make every completion or REPL result pass through a shared envelope. That preserves the existing design intent while making the system easier to extend, test, and reason about.
