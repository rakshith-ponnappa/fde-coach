# The 26-week curriculum

This overview is generated from [`curriculum.toml`](../curriculum.toml), which is the source of truth read by
`fde today`, `fde plan` and `fde week show N`. Edit the TOML to change the plan; `python3 -m unittest` checks it stays consistent.

- **Weeks 1-16:** a sprint from "new to Python" to job-ready for Forward Deployed / AI platform roles.
- **Weeks 17-26:** a depth track to follow while interviewing or in a new role.

## Phases

| Phase | Weeks | Focus | Goal |
|---|---|---|---|
| 1 | 1-4 | Python fast track | Write, test and debug Python programs on your own; finish Harvard CS50P (free certificate) with a DevOps tool as the final project. |
| 2 | 5-8 | Production Python + first AI app | Build, test, containerise and deploy a Python API, then ship your first LLM app (RAG with evals) to Azure with Terraform. |
| 3 | 9-12 | Agents, evals & LLMOps | Build agents with tools and MCP, prove quality with evals and tracing, secure them, and run AI data pipelines and LLM services in production. |
| 4 | 13-16 | FDE capstone + interview readiness | Work like an FDE on a simulated customer problem end to end, and get ready for every interview round: coding, LLM system design, decomposition, behavioural, demo. |
| 5 | 17-26 | Depth track (while interviewing / in your new job) | Go deeper on what the job ads list beyond the sprint: TypeScript, data engineering, distributed systems, ML, knowledge graphs, open models and inference infrastructure. |

## Skills tracked

Levels: 0 none, 1 aware, 2 guided, 3 independent, 4 production, 5 expert.

| Key | Skill | Target |
|---|---|---|
| `python` | Python programming | 4 |
| `swe` | Software engineering (Git, testing, packaging, code review) | 4 |
| `dsa` | Data structures & algorithms (interviews) | 3 |
| `sql` | SQL & databases | 3 |
| `apis` | APIs & backend services (FastAPI) | 4 |
| `cloud` | Cloud platforms incl. AI services (Azure / AWS / GCP) | 5 |
| `iac_cicd` | Infrastructure as code & CI/CD | 5 |
| `containers` | Docker & Kubernetes | 4 |
| `llm` | LLM APIs, prompting & structured outputs | 4 |
| `rag` | RAG & search | 4 |
| `agents` | Agents, tool use & MCP | 4 |
| `evals` | Evals & LLM observability | 4 |
| `llmops` | Deploying & operating AI systems (LLMOps, security, cost) | 5 |
| `data_pipelines` | Data pipelines (batch & streaming) | 4 |
| `distributed` | Distributed systems & system design | 4 |
| `ml` | ML fundamentals | 3 |
| `knowledge_graphs` | Knowledge graphs & GraphRAG | 3 |
| `typescript` | TypeScript & front-end basics | 2 |
| `communication` | Communication, writing & demos | 5 |
| `discovery` | Customer discovery & problem decomposition | 4 |
| `interviewing` | Interview performance | 4 |

## Week by week

### Phase 1: Python fast track

**Week 1: Setup + Python basics: functions, variables, conditionals, loops**

- Deliverable: CS50P problem sets 0-2 submitted, and 5 Exercism exercises solved and pushed to GitHub.
- Resources: [Harvard CS50P - Introduction to Programming with Python (free, certificate)](https://cs50.harvard.edu/python/), [VS Code: getting started with Python](https://code.visualstudio.com/docs/python/python-tutorial), [Exercism Python track (free practice with mentors)](https://exercism.org/tracks/python)

**Week 2: Exceptions, libraries, unit tests, calling APIs**

- Deliverable: CS50P problem sets 3-5, plus a tested script that calls a public API (e.g. GitHub repo stats) and prints a summary.
- Resources: [CS50P lectures 3-5](https://cs50.harvard.edu/python/), [Python tutorial: virtual environments and packages](https://docs.python.org/3/tutorial/venv.html), [Requests quickstart](https://requests.readthedocs.io/en/latest/user/quickstart/), [pytest: get started](https://docs.pytest.org/en/stable/getting-started.html)

**Week 3: Files, regular expressions, classes - automate a DevOps chore**

- Deliverable: CS50P problem sets 6-8, plus logscan.py: parses a synthetic web-server log, counts errors per hour, with tests.
- Resources: [CS50P lectures 6-8](https://cs50.harvard.edu/python/), [Automate the Boring Stuff with Python (free online)](https://automatetheboringstuff.com/), [regex101 - test regular expressions](https://regex101.com/)

**Week 4: CS50P final project: a Python tool for a real DevOps problem**

- Deliverable: Public GitHub repo for tfplan-summary (README + tests), CS50P certificate, and one tested change merged into fde_coach.
- Resources: [CS50P lecture 9 + final project](https://cs50.harvard.edu/python/), [Terraform JSON output format](https://developer.hashicorp.com/terraform/internals/json-format), [argparse tutorial](https://docs.python.org/3/howto/argparse.html)

### Phase 2: Production Python + first AI app

**Week 5: Professional Python workflow + SQL + interview practice begins**

- Deliverable: tfplan-summary installable with `uv tool install`, linted and type-checked in pre-commit; SQLBolt done; 6 NeetCode problems.
- Resources: [uv - Python packaging and projects](https://docs.astral.sh/uv/), [Ruff - linter and formatter](https://docs.astral.sh/ruff/), [SQLBolt - interactive SQL lessons](https://sqlbolt.com/), [NeetCode roadmap](https://neetcode.io/roadmap)

**Week 6: Build a production-style API: FastAPI, Pydantic, Postgres, Docker, CI**

- Deliverable: A 'runbook API' (CRUD for synthetic runbooks) with tests, a container image and a green CI pipeline.
- Resources: [FastAPI tutorial](https://fastapi.tiangolo.com/tutorial/), [Pydantic documentation](https://pydantic.dev/docs/validation/latest/get-started/), [Docker guide: containerise a Python app](https://docs.docker.com/guides/python/), [pgexercises - practise PostgreSQL queries](https://pgexercises.com/)

**Week 7: How LLMs work + calling LLM APIs: prompts, structured output, tools**

- Deliverable: tfplan-summary v2: an LLM turns the plan into a validated JSON risk summary, and the tool prints the cost of each run.
- Resources: [3Blue1Brown - neural networks and transformers (visual)](https://www.3blue1brown.com/topics/neural-networks), [Anthropic courses on GitHub (prompting, tool use)](https://github.com/anthropics/courses), [Gemini API docs (free tier)](https://aistudio.google.com/docs), [Ollama - run open models on your own machine](https://ollama.com/)

**Week 8: RAG + evals + cloud deploy = Project 1 (start tier B applications)**

- Deliverable: Project 1 'Ops Docs Q&A' live: RAG over 500+ pages of public cloud docs, eval scores in the README, deployed with Terraform. Post it on LinkedIn.
- Resources: [DataTalksClub LLM Zoomcamp (free; RAG + evaluation modules)](https://github.com/DataTalksClub/llm-zoomcamp), [pgvector](https://github.com/pgvector/pgvector), [Hamel Husain - LLM evals FAQ](https://hamel.dev/blog/posts/evals-faq/), [Azure Container Apps documentation](https://learn.microsoft.com/en-us/azure/container-apps/)

### Phase 3: Agents, evals & LLMOps

**Week 9: Agents from scratch: the tool-calling loop and when NOT to use agents**

- Deliverable: On-call helper agent (no framework): reads synthetic alerts, queries a fake metrics API and your runbooks, proposes actions, asks before acting.
- Resources: [Anthropic - Building effective agents](https://www.anthropic.com/research/building-effective-agents), [Hugging Face Agents Course (free, certificate)](https://huggingface.co/learn/agents-course)

**Week 10: MCP + one agent framework, properly**

- Deliverable: Public 'infra-readonly-mcp' repo with tests and a short demo of an agent using it.
- Resources: [Model Context Protocol documentation](https://modelcontextprotocol.io/), [Hugging Face MCP Course (free)](https://huggingface.co/learn/mcp-course), [LangChain Academy - free LangGraph courses](https://academy.langchain.com/), [OpenAI Agents SDK (Python)](https://openai.github.io/openai-agents-python/)

**Week 11: Evals, tracing, security - and better RAG measured by evals**

- Deliverable: CI job running RAG + agent evals and prompt-injection tests on every PR; README section with the eval table and security notes.
- Resources: [Langfuse docs](https://langfuse.com/docs), [Arize Phoenix docs](https://arize.com/docs/phoenix), [OWASP Top 10 for LLM Applications](https://genai.owasp.org/llm-top-10/), [Anthropic - Contextual retrieval](https://www.anthropic.com/research/contextual-retrieval)

**Week 12: AI data pipelines + LLMOps in production**

- Deliverable: Project 2 'Enterprise Ops Assistant': scheduled ingestion + RAG + MCP agent + evals + dashboard, deployable with one Terraform apply.
- Resources: [Prefect documentation](https://www.prefect.io/docs/v3/get-started), [Dagster documentation](https://dagster.io/docs), [LiteLLM - LLM gateway / router](https://docs.litellm.ai/), [Microsoft Foundry (formerly Azure AI Foundry) documentation](https://learn.microsoft.com/en-us/azure/foundry/)

### Phase 4: FDE capstone + interview readiness

**Week 13: FDE craft: discovery, decomposition and the capstone design doc**

- Deliverable: 5 one-page decompositions and a capstone design doc reviewed by one other engineer.
- Resources: [Design docs at Google (how to write one)](https://www.industrialempathy.com/posts/design-docs-at-google/), [Google technical writing courses (free)](https://developers.google.com/tech-writing), [SEC EDGAR public APIs (free data for a capstone)](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)

**Week 14: Capstone build: deliver into a 'customer environment'**

- Deliverable: Capstone v1.0 running in your sandbox with a full handover pack in the repo.
- Resources: [Streamlit documentation](https://docs.streamlit.io/), [Google SRE book (free) - for the runbook and monitoring](https://sre.google/sre-book/table-of-contents/)

**Week 15: Interview prep I: CV, portfolio, coding rounds**

- Deliverable: CV v1 reviewed by 2 people, LinkedIn updated, 30-person referral list, 3 recorded timed coding sessions with notes.
- Resources: [Tech Interview Handbook - resume](https://www.techinterviewhandbook.org/resume/), [Tech Interview Handbook - coding interview prep](https://www.techinterviewhandbook.org/coding-interview-prep/), [NeetCode 150 practice list](https://neetcode.io/practice)

**Week 16: Interview prep II: LLM system design, decomposition, behavioural, demo**

- Deliverable: 6 written designs, 12-story bank, 2 recorded mock interviews and the capstone demo video. You are now job-ready.
- Resources: [System Design Primer](https://github.com/donnemartin/system-design-primer), [Chip Huyen - Building a generative AI platform](https://huyenchip.com/2024/07/25/genai-platform.html), [Tech Interview Handbook - behavioural interviews](https://www.techinterviewhandbook.org/behavioral-interview/)

### Phase 5: Depth track (while interviewing / in your new job)

**Week 17: TypeScript + React for FDEs (half of FDE job ads mention it)**

- Deliverable: A Next.js front-end for Project 2 with streaming answers and citations, deployed on a free tier.
- Resources: [TypeScript handbook](https://www.typescriptlang.org/docs/handbook/intro.html), [Next.js Learn (free course)](https://nextjs.org/learn), [AI SDK documentation (TypeScript toolkit for AI apps)](https://ai-sdk.dev/docs)

**Week 18: Data engineering I: ingestion, orchestration, warehouse, dbt**

- Deliverable: Incremental pipeline from a public API into DuckDB with dbt models, tests and generated docs.
- Resources: [DataTalksClub Data Engineering Zoomcamp (free)](https://github.com/DataTalksClub/data-engineering-zoomcamp), [dlt documentation](https://dlthub.com/docs/intro), [dbt Learn (free courses)](https://learn.getdbt.com/), [DuckDB documentation](https://duckdb.org/docs/)

**Week 19: Data engineering II: Spark batch and Kafka streaming**

- Deliverable: The same transformation in Polars and PySpark with a timing write-up, plus a small events -> Kafka -> database stream.
- Resources: [PySpark getting started](https://spark.apache.org/docs/latest/api/python/getting_started/index.html), [Polars user guide](https://docs.pola.rs/), [Apache Kafka documentation](https://kafka.apache.org/documentation/)

**Week 20: Distributed systems fundamentals**

- Deliverable: Blog post: 'What running production systems taught me about distributed systems', mapped to the theory.
- Resources: [MIT 6.5840 Distributed Systems (free lectures and labs)](https://pdos.csail.mit.edu/6.824/), [Raft consensus - visual explanation](https://raft.github.io/)

**Week 21: System design depth, including ML systems**

- Deliverable: 6 more written designs with diagrams; one presented to a peer in a 45-minute mock.
- Resources: [System Design Primer](https://github.com/donnemartin/system-design-primer), [Chip Huyen's blog (ML systems in production)](https://huyenchip.com/blog/)

**Week 22: ML fundamentals I: how models learn and how to evaluate them**

- Deliverable: Kaggle notebook with a submission and a written evaluation of your model choices.
- Resources: [Google Machine Learning Crash Course (free)](https://developers.google.com/machine-learning/crash-course), [Kaggle Learn (free micro-courses)](https://www.kaggle.com/learn), [scikit-learn user guide](https://scikit-learn.org/stable/user_guide.html)

**Week 23: ML fundamentals II: neural networks, PyTorch and MLOps**

- Deliverable: micrograd re-implemented, plus a tracked PyTorch model served behind an API.
- Resources: [Andrej Karpathy - Neural Networks: Zero to Hero](https://karpathy.ai/zero-to-hero.html), [PyTorch tutorials](https://docs.pytorch.org/tutorials/), [DataTalksClub MLOps Zoomcamp (free)](https://github.com/DataTalksClub/mlops-zoomcamp)

**Week 24: Knowledge graphs & GraphRAG, measured**

- Deliverable: A knowledge graph of your Project 2 documents, an eval table and a blog post: when a graph beats plain vector search (and when it doesn't).
- Resources: [Neo4j GraphAcademy (free courses and certifications)](https://graphacademy.neo4j.com/), [Microsoft GraphRAG](https://microsoft.github.io/graphrag/), [Neo4j GraphRAG for Python](https://neo4j.com/docs/neo4j-graphrag-python/current/)

**Week 25: Open models and inference infrastructure**

- Deliverable: Terraform + Kubernetes manifests that serve an open model with a load-test report (latency, throughput, cost per 1M tokens).
- Resources: [vLLM documentation](https://docs.vllm.ai/), [Unsloth documentation (free Colab/Kaggle notebooks)](https://unsloth.ai/docs)

**Week 26: Stand out: open source, writing, Year 2 plan**

- Deliverable: A merged open-source PR, a talk proposal, and your written Year 2 plan.
- Resources: [Good First Issue - beginner-friendly open-source issues](https://goodfirstissue.dev/), [GitHub: contributing to open source](https://docs.github.com/en/get-started/exploring-projects-on-github/contributing-to-a-project)
