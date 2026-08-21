import json
import subprocess
import sys
import time

from langchain_aws import ChatBedrockConverse
from langchain_core.tools import tool
from langchain.agents import create_react_agent

from config import AWS_REGION, MODEL_ID, PROMETHEUS_URL


# ── LLM ──────────────────────────────────────────────────────────────────────

llm = ChatBedrockConverse(
    model=MODEL_ID,
    region_name=AWS_REGION
)


# ── Tools ────────────────────────────────────────────────────────────────────

@tool
def get_pod_status(namespace: str = "default") -> str:
    """List all pods and their current status in a Kubernetes namespace."""

    result = subprocess.run(
        [
            "kubectl",
            "get",
            "pods",
            "-n",
            namespace,
            "-o",
            "json"
        ],
        capture_output=True,
        text=True,
        timeout=10
    )

    if result.returncode != 0:
        return json.dumps({
            "error": result.stderr.strip()
        })

    pods = json.loads(result.stdout)
    summary = []

    for pod in pods["items"]:
        name = pod["metadata"]["name"]
        phase = pod["status"].get("phase", "Unknown")
        conditions = pod["status"].get(
            "containerStatuses",
            []
        )

        state = "unknown"

        if conditions:
            state_info = conditions[0].get(
                "state",
                {}
            )

            if "running" in state_info:
                state = "running"

            elif "waiting" in state_info:
                state = state_info["waiting"].get(
                    "reason",
                    "waiting"
                )

            elif "terminated" in state_info:
                state = "terminated"

        summary.append({
            "pod": name,
            "phase": phase,
            "state": state
        })

    return json.dumps(summary)


@tool
def get_pod_logs(
    pod_name: str,
    namespace: str = "default"
) -> str:
    """Get recent logs from a specific pod."""

    result = subprocess.run(
        [
            "kubectl",
            "logs",
            pod_name,
            "-n",
            namespace,
            "--tail=20"
        ],
        capture_output=True,
        text=True,
        timeout=10
    )

    return json.dumps({
        "pod": pod_name,
        "logs": result.stdout or result.stderr
    })


@tool
def restart_pod(
    deployment_name: str,
    namespace: str = "default"
) -> str:
    """Restart a deployment. Requires human approval before executing."""

    print("\n[APPROVAL REQUIRED]")
    print(
        f"Action   : kubectl rollout restart "
        f"deployment/{deployment_name}"
    )
    print(f"Namespace: {namespace}")

    answer = input(
        "Approve this action? (yes/no): "
    ).strip().lower()

    if answer != "yes":
        return json.dumps({
            "status": "cancelled",
            "reason": "User did not approve"
        })

    result = subprocess.run(
        [
            "kubectl",
            "rollout",
            "restart",
            f"deployment/{deployment_name}",
            "-n",
            namespace
        ],
        capture_output=True,
        text=True,
        timeout=10
    )

    if result.returncode == 0:
        return json.dumps({
            "status": "restarted",
            "deployment": deployment_name,
            "output": result.stdout.strip()
        })

    return json.dumps({
        "status": "error",
        "deployment": deployment_name,
        "error": result.stderr.strip()
    })


@tool
def query_metrics(
    query: str,
    namespace: str = "default"
) -> str:
    """Query Prometheus for real-time metrics using PromQL."""

    import requests

    try:
        resp = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
            timeout=5
        )

        resp.raise_for_status()

        data = resp.json()

        results = data.get(
            "data",
            {}
        ).get(
            "result",
            []
        )

        if not results:
            return json.dumps({
                "query": query,
                "result": "no data"
            })

        output = []

        for r in results:
            output.append({
                "labels": r.get("metric", {}),
                "value": r.get(
                    "value",
                    [None, None]
                )[1]
            })

        return json.dumps({
            "query": query,
            "results": output
        })

    except Exception as e:
        return json.dumps({
            "query": query,
            "error": str(e)
        })


# ── Agent ────────────────────────────────────────────────────────────────────

agent = create_react_agent(
    llm,
    [
        get_pod_status,
        get_pod_logs,
        restart_pod,
        query_metrics
    ]
)


def start_prometheus_portforward():
    proc = subprocess.Popen(
        [
            "kubectl",
            "port-forward",
            "svc/prometheus-server",
            "9090:80",
            "-n",
            "monitoring"
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    time.sleep(2)

    return proc


def run_agent(user_message: str):
    print(f"\nUser: {user_message}\n")

    for chunk in agent.stream(
        {
            "messages": [
                ("human", user_message)
            ]
        }
    ):
        if "agent" in chunk:
            for msg in chunk["agent"]["messages"]:
                if msg.content:

                    if isinstance(msg.content, list):
                        for block in msg.content:

                            if (
                                isinstance(block, dict)
                                and block.get("type") == "text"
                            ):
                                print(
                                    f"\n--- Agent ---\n"
                                    f"{block['text']}"
                                )

                            elif (
                                isinstance(block, dict)
                                and block.get("type") == "tool_use"
                            ):
                                print(
                                    f"[tool] "
                                    f"{block['name']} → "
                                    f"{block.get('input', {})}"
                                )

                    else:
                        print(
                            f"\n--- Agent ---\n"
                            f"{msg.content}"
                        )

        elif "tools" in chunk:
            for msg in chunk["tools"]["messages"]:
                print(
                    f"[result] "
                    f"{str(msg.content)[:300]}"
                )


if __name__ == "__main__":
    pf = start_prometheus_portforward()

    try:
        query = (
            " ".join(sys.argv[1:])
            if len(sys.argv) > 1
            else (
                "Check all pods in the default namespace. "
                "Query CPU and memory usage metrics. "
                "If anything is broken, diagnose it and "
                "restart the affected deployment."
            )
        )

        run_agent(query)

    finally:
        pf.terminate()
        pf.wait()
