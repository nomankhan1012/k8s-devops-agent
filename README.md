# Kubernetes DevOps Agent

An AI agent that monitors, diagnoses, and repairs Kubernetes workloads using Amazon Bedrock (Claude Sonnet) and real kubectl commands.

## Tools

- `get_pod_status` — lists all pods and health
- `get_pod_logs` — fetches logs from a broken pod
- `restart_pod` — restarts deployment (human approval required)
- `query_metrics` — queries Prometheus via PromQL

## Stack

- Amazon Bedrock (Claude Sonnet)
- Kubernetes (Kind) on AWS EC2
- Prometheus via Helm
- Raw tool-calling loop (no framework)

## Run

pip install -r requirements.txt
python3 agent.py
