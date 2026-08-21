+     1: # Kubernetes DevOps Agent
+     2:
+     3: An AI-powered DevOps agent that monitors, diagnoses, and repairs Kubernetes workloads using Amazon Bedrock (Claude Sonnet). Built in three progressive stages — from raw tool-calling to a production AgentCore deployment on EKS.
+     4:
+     5: ## Architecture
+     6:
+     7: ```
+     8: agentcore invoke
+     9:       │
+    10:       ▼
+    11: Amazon Bedrock AgentCore Runtime
+    12:       │
+    13:       ▼
+    14: LangGraph ReAct Agent (Claude Sonnet)
+    15:       │
+    16:       ▼
+    17: kubectl → Amazon EKS (production cluster)
+    18: ```
+    19:
+    20: ## Agent Tools
+    21:
+    22: | Tool | Description |
+    23: |------|-------------|
+    24: | `get_pod_status` | Lists all pods and their health in a namespace |
+    25: | `get_pod_logs` | Fetches recent logs from a specific pod |
+    26: | `restart_pod` | Restarts a deployment (requires `auto_approve=true`) |
+    27: | `query_metrics` | Queries Prometheus via PromQL |
+    28:
+    29: ## Stack
+    30:
+    31: - **Amazon Bedrock** — Claude Sonnet (us.anthropic.claude-sonnet-4-6)
+    32: - **Amazon Bedrock AgentCore** — managed agent runtime
+    33: - **Amazon EKS** — production Kubernetes cluster (us-east-1)
+    34: - **LangGraph** — ReAct agent with parallel tool calls + conversation memory
+    35: - **Prometheus** — metrics backend via PromQL
+    36: - **Docker + ECR** — containerized deployment
+    37: - **AWS IAM** — execution role with EKS access
+    38:
+    39: ## Project Structure
+    40:
+    41: ```
+    42: k8s-devops-agent/
+    43: ├── agent.py                  # Raw Bedrock tool-calling loop (no framework)
+    44: ├── agent_langgraph.py        # LangGraph ReAct agent (parallel tool calls)
+    45: ├── server.py                 # FastAPI HTTP wrapper
+    46: ├── tools/
+    47: │   ├── k8s.py                # kubectl-based tools
+    48: │   └── metrics.py            # Prometheus tools
+    49: ├── config.py
+    50: ├── requirements.txt
+    51: └── k8sdevopsagent/           # AgentCore deployment
+    52:     └── app/k8sdevopsagent/
+    53:         ├── main.py           # BedrockAgentCoreApp entrypoint
+    54:         ├── Dockerfile        # python:3.12-slim + awscli + kubectl (arch-aware)
+    55:         └── pyproject.toml
+    56: ```
+    57:
+    58: ## Usage
+    59:
+    60: ### AgentCore (Production)
+    61:
+    62: ```bash
+    63: # Deploy
+    64: cd k8sdevopsagent && agentcore deploy
+    65:
+    66: # Invoke
+    67: agentcore invoke --prompt "Check all pods and give me a health report"
+    68: agentcore invoke --prompt "Get logs from the broken-app pod"
+    69: agentcore invoke --prompt '{"prompt": "restart the web deployment", "auto_approve": true}'
+    70: ```
+    71:
+    72: ### Local (Raw agent)
+    73:
+    74: ```bash
+    75: pip install -r requirements.txt
+    76: python3 agent.py
+    77: ```
+    78:
+    79: ### Local (LangGraph agent)
+    80:
+    81: ```bash
+    82: python3 agent_langgraph.py
+    83: ```
+    84:
+    85: ## Key Implementation Details
+    86:
+    87: - **Arch-aware kubectl**: Dockerfile uses `$(dpkg --print-architecture)` to install the correct kubectl binary (ARM64 for AgentCore runtime)
+    88: - **EKS auth**: `aws eks update-kubeconfig` runs on every invocation via `_setup_kubeconfig()` using the AgentCore execution role
+    89: - **IAM**: Execution role has `eks:DescribeCluster` + `AmazonEKSClusterAdminPolicy` (via EKS access entry)
+    90: - **Conversation memory**: `InMemorySaver` checkpointer with 128-thread LRU eviction
+    91: - **Approval gate**: `restart_pod` is blocked unless `auto_approve=true` is passed in payload
