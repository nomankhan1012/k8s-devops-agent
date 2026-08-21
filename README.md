# Kubernetes DevOps Agent

  An AI-powered DevOps agent that monitors, diagnoses, and repairs Kubernetes workloads using natural language. Built in
  three progressive stages — from raw Bedrock tool-calling to a production AgentCore deployment on EKS.

  ## Architecture

  agentcore invoke
        │
        ▼
  Amazon Bedrock AgentCore Runtime
        │
        ▼
  LangGraph ReAct Agent (Claude Sonnet)
        │
        ▼
  kubectl → Amazon EKS (us-east-1)

  ## Stack

  | Layer | Technology |
  |-------|-----------|
  | LLM | Amazon Bedrock — Claude Sonnet (us.anthropic.claude-sonnet-4-6) |
  | Agent Framework | LangGraph ReAct — parallel tool calls + conversation memory |
  | Runtime | Amazon Bedrock AgentCore |
  | Kubernetes | Amazon EKS (us-east-1) |
  | Metrics | Prometheus (PromQL) |
  | Container | Docker + Amazon ECR |
  | Auth | AWS IAM — execution role with EKS access entry |

  ## Agent Tools

  | Tool | Description |
  |------|-------------|
  | `get_pod_status` | Lists all pods and their health in a namespace |
  | `get_pod_logs` | Fetches recent logs from a specific pod |
  | `restart_pod` | Restarts a deployment (requires `auto_approve=true`) |
  | `query_metrics` | Queries Prometheus via PromQL |

  ## Project Structure

  k8s-devops-agent/
  ├── agent.py               # Phase 1: Raw Bedrock tool-calling loop
  ├── agent_langgraph.py     # Phase 2: LangGraph ReAct agent
  ├── server.py              # Phase 2: FastAPI HTTP wrapper
  ├── tools/
  │   ├── k8s.py             # kubectl-based tools
  │   └── metrics.py         # Prometheus tools
  ├── config.py
  ├── requirements.txt
  └── k8sdevopsagent/        # Phase 3: AgentCore deployment
      └── app/k8sdevopsagent/
          ├── main.py        # BedrockAgentCoreApp entrypoint
          ├── Dockerfile     # python:3.12-slim + awscli + kubectl
          └── pyproject.toml

  ## Usage

  **AgentCore (Production)**

  ```bash
  cd k8sdevopsagent && agentcore deploy

  agentcore invoke --prompt "Check all pods and give me a health report"
  agentcore invoke --prompt "Get logs from the broken-app pod"
  agentcore invoke --prompt '{"prompt": "restart the web deployment", "auto_approve": true}'

  Local — Raw agent

  pip install -r requirements.txt
  python3 agent.py

  Local — LangGraph agent

  python3 agent_langgraph.py

  Implementation Notes

  - Arch-aware kubectl — Dockerfile detects architecture at build time using $(dpkg --print-architecture) so the correct
  binary is installed for ARM64 (AgentCore runtime)
  - EKS auth — _setup_kubeconfig() runs aws eks update-kubeconfig on every invocation using the AgentCore execution role
  - IAM — Execution role has eks:DescribeCluster inline policy + AmazonEKSClusterAdminPolicy via EKS access entry
  - Conversation memory — InMemorySaver checkpointer with 128-thread LRU eviction
  - Approval gate — restart_pod is blocked unless auto_approve=true is passed in the payload
