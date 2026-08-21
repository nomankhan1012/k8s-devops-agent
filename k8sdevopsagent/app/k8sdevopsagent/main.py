import json
import subprocess
from collections import OrderedDict

import requests as http_requests
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from opentelemetry.instrumentation.langchain import LangchainInstrumentor
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from model.load import load_model

LangchainInstrumentor().instrument()

app = BedrockAgentCoreApp()
log = app.logger

PROMETHEUS_URL = "http://localhost:9090"
EKS_CLUSTER_NAME = "devops-agent"
AWS_REGION = "us-east-1"
_llm = None
_auto_approve = False


def _setup_kubeconfig():
    result = subprocess.run(
        [
            "aws",
            "eks",
            "update-kubeconfig",
            "--name",
            EKS_CLUSTER_NAME,
            "--region",
            AWS_REGION
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        log.info(
            f"kubeconfig updated for EKS cluster: {EKS_CLUSTER_NAME}"
        )
    else:
        log.warning(
            f"Failed to update kubeconfig: {result.stderr.strip()}"
        )


_setup_kubeconfig()


def get_or_create_model():
    global _llm
    if _llm is None:
        _llm = load_model()
    return _llm


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
        timeout=10,
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
            s = conditions[0].get(
                "state",
                {}
            )

            if "running" in s:
                state = "running"

            elif "waiting" in s:
                state = s["waiting"].get(
                    "reason",
                    "waiting"
                )

            elif "terminated" in s:
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
        timeout=10,
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
    """Restart a deployment. Requires auto_approve=true in the API payload."""

    if not _auto_approve:
        return json.dumps({
            "status": "requires_approval",
            "message": (
                f"Restart of '{deployment_name}' blocked. "
                "Re-invoke with auto_approve=true to confirm."
            ),
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
        timeout=10,
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

    try:
        resp = http_requests.get(
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


tools = [
    get_pod_status,
    get_pod_logs,
    restart_pod,
    query_metrics
]

_CHECKPOINT_LIMIT = 128
_checkpointer = InMemorySaver()
_thread_ids = OrderedDict()


def touch_thread(thread_id):
    if thread_id in _thread_ids:
        _thread_ids.move_to_end(thread_id)
        return

    while len(_thread_ids) >= _CHECKPOINT_LIMIT:
        evicted, _ = _thread_ids.popitem(last=False)
        _checkpointer.delete_thread(evicted)

    _thread_ids[thread_id] = True


@app.entrypoint
async def invoke(payload, context):
    global _auto_approve

    _setup_kubeconfig()
    log.info("Invoking K8s DevOps Agent...")

    prompt = payload.get(
        "prompt",
        "Check all pods and give a health report."
    )

    _auto_approve = payload.get(
        "auto_approve",
        False
    )

    session_id = getattr(
        context,
        "session_id",
        "default-session"
    )

    touch_thread(session_id)

    graph = create_react_agent(
        get_or_create_model(),
        tools=tools,
        checkpointer=_checkpointer,
    )

    result = await graph.ainvoke(
        {
            "messages": [
                HumanMessage(content=prompt)
            ]
        },
        config={
            "configurable": {
                "thread_id": session_id
            }
        },
    )

    output = result["messages"][-1].content

    log.info(
        f"Agent output: {output}"
    )

    return {
        "result": output
    }


if __name__ == "__main__":
    app.run()
