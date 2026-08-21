from tools.k8s import (
    get_pod_status,
    get_pod_logs,
    restart_pod
)

from tools.metrics import query_metrics


TOOL_REGISTRY = {
    "get_pod_status": get_pod_status,
    "get_pod_logs": get_pod_logs,
    "restart_pod": restart_pod,
    "query_metrics": query_metrics,
}


TOOL_SCHEMAS = [
    {
        "name": "get_pod_status",
        "description": (
            "List all pods and their current status "
            "in a Kubernetes namespace"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Kubernetes namespace"
                }
            },
            "required": ["namespace"]
        }
    },
    {
        "name": "get_pod_logs",
        "description": (
            "Get recent logs from a specific pod"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pod_name": {
                    "type": "string",
                    "description": "Name of the pod"
                },
                "namespace": {
                    "type": "string",
                    "description": "Kubernetes namespace"
                }
            },
            "required": [
                "pod_name",
                "namespace"
            ]
        }
    },
    {
        "name": "restart_pod",
        "description": (
            "Restart a deployment. Requires human "
            "approval before executing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "deployment_name": {
                    "type": "string",
                    "description": (
                        "Name of the deployment to restart"
                    )
                },
                "namespace": {
                    "type": "string",
                    "description": "Kubernetes namespace"
                }
            },
            "required": [
                "deployment_name",
                "namespace"
            ]
        }
    },
    {
        "name": "query_metrics",
        "description": (
            "Query Prometheus for real-time metrics "
            "using PromQL. Use to check CPU usage, "
            "memory, container restarts, and error rates."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "PromQL query string"
                },
                "namespace": {
                    "type": "string",
                    "description": (
                        "Kubernetes namespace for context"
                    )
                }
            },
            "required": ["query"]
        }
    }
]


def run_tool(name, inputs):
    if name not in TOOL_REGISTRY:
        return {
            "error": f"Unknown tool: {name}"
        }

    return TOOL_REGISTRY[name](**inputs)
