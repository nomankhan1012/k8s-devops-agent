import boto3
import json
import subprocess
import sys
import time

from config import MODEL_ID, AWS_REGION
from tools import TOOL_SCHEMAS, run_tool


client = boto3.client(
    "bedrock-runtime",
    region_name=AWS_REGION
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


def run_agent(user_message):
    print(f"\nUser: {user_message}\n")

    messages = [
        {
            "role": "user",
            "content": user_message
        }
    ]

    while True:
        response = client.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2048,
                "tools": TOOL_SCHEMAS,
                "messages": messages
            })
        )

        result = json.loads(
            response["body"].read()
        )

        if result["stop_reason"] == "tool_use":
            messages.append({
                "role": "assistant",
                "content": result["content"]
            })

            tool_results = []

            for block in result["content"]:
                if block["type"] == "tool_use":
                    print(
                        f"[tool] {block['name']} "
                        f"→ {block['input']}"
                    )

                    output = run_tool(
                        block["name"],
                        block["input"]
                    )

                    print(
                        f"[result] "
                        f"{json.dumps(output, indent=2)}\n"
                    )

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": json.dumps(output)
                    })

            messages.append({
                "role": "user",
                "content": tool_results
            })

        else:
            print("\n--- Agent Report ---")
            print(
                result["content"][0]["text"]
            )
            break


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
