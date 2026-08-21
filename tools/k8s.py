import json
import subprocess


def get_pod_status(namespace="default"):
    result = subprocess.run(
        ["kubectl", "get", "pods", "-n", namespace, "-o", "json"],
        capture_output=True,
        text=True,
        timeout=10
    )

    if result.returncode != 0:
        return {"error": result.stderr.strip()}

    pods = json.loads(result.stdout)
    summary = []

    for pod in pods["items"]:
        name = pod["metadata"]["name"]
        phase = pod["status"].get("phase", "Unknown")
        conditions = pod["status"].get("containerStatuses", [])

        state = "unknown"

        if conditions:
            state_info = conditions[0].get("state", {})

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

    return summary


def get_pod_logs(pod_name, namespace="default"):
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

    return {
        "pod": pod_name,
        "logs": result.stdout or result.stderr
    }


def restart_pod(deployment_name, namespace="default"):
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
        return {
            "status": "cancelled",
            "reason": "User did not approve"
        }

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
        return {
            "status": "restarted",
            "deployment": deployment_name,
            "output": result.stdout.strip()
        }

    return {
        "status": "error",
        "deployment": deployment_name,
        "error": result.stderr.strip()
    }
