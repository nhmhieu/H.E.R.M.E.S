# H.E.R.M.E.S
![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)

## Project Overview
H.E.R.M.E.S (HCMUS Educational Resource & Mentoring Expert System) is a 10-week academic capstone project for course CSC10014 - Computational Thinking. It acts as a reliable computational pipeline for student needs: Request -> Understand -> Route -> Retrieve / Compute -> Reason -> Verify -> Respond.

## Team Structure
1. **Member 1**: Team Leader & Orchestration Lead
2. **Member 2**: Deterministic Algorithms Lead
3. **Member 3**: Data & RAG Lead
4. **Member 4**: AI & Safety Lead
5. **Member 5**: Interface & QA/Evaluation Lead

## Architecture Pipeline
```
Request -> Router -> Engines -> Verified Output
```

## Quickstart Guide
1. Create a virtual environment: `python -m venv venv`
2. Activate the virtual environment: `source venv/bin/activate` (or `venv\Scripts\activate` on Windows)
3. Install dependencies in editable mode: `pip install -e .[dev]`
4. Run the CLI: `hermes --help`
5. Run tests: `pytest`
