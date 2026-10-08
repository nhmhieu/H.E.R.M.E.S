# ARCHITECTURE

## System Components
1. Deterministic Engine (R2)
2. Data & Retrieval / RAG Engine (R3)
3. AI Reasoning & Extraction (R4)
4. Orchestrator & Router (R5)
5. CLI & Web Interface (R6)
6. Safeguards & Guardrails (R7)
7. Evaluation & Benchmarks (R8)

## Data Flow
Request -> Router -> Engines -> Verified Output

## Sequence Diagram
1. User interacts with CLI/Web Interface.
2. Request is passed to Safeguards & Guardrails.
3. If safe, request is routed by Orchestrator & Router.
4. Router directs to appropriate engine (Deterministic, RAG, AI).
5. Engine processes request and generates output.
6. Output is verified and returned to user.