import json
import subprocess

import requests as http_requests
from fastapi import FastAPI
from langchain.agents import create_react_agent
from langchain_aws import ChatBedrockConverse
from langchain_core.tools import tool
from pydantic import BaseModel

from config import AWS_REGION, MODEL_ID, PROMETHEUS_URL

app = FastAPI()
llm = ChatBedrockConverse(
    model=MODEL_ID,
    region_name=AWS_REGION
)

_auto_approve = False


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
        phase = pod["status"].get(
            "phase",
            "Unknown"
        )

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
    """Restart a deployment. Requires auto_approve=true in the API request."""

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


agent = create_react_agent(
    llm,
    [
        get_pod_status,
        get_pod_logs,
        restart_pod,
        query_metrics
    ]
)


class InvokeRequest(BaseModel):
    query: str
    auto_approve: bool = False


@app.post("/invoke")
def invoke(req: InvokeRequest):
    global _auto_approve

    _auto_approve = req.auto_approve

    final_response = ""
    tool_calls = []

    for chunk in agent.stream(
        {
            "messages": [
                ("human", req.query)
            ]
        }
    ):
        if "agent" in chunk:
            for msg in chunk["agent"]["messages"]:

                if not msg.content:
                    continue

                if isinstance(msg.content, list):

                    for block in msg.content:

                        if (
                            isinstance(block, dict)
                            and block.get("type") == "text"
                        ):
                            final_response = block["text"]

                        elif (
                            isinstance(block, dict)
                            and block.get("type") == "tool_use"
                        ):
                            tool_calls.append({
                                "tool": block["name"],
                                "input": block.get(
                                    "input",
                                    {}
                                )
                            })

                else:
                    final_response = msg.content

    return {
        "response": final_response,
        "tool_calls": tool_calls
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }
