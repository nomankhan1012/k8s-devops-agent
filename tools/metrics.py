import requests
from config import PROMETHEUS_URL


def query_metrics(query, namespace=None):
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
            return {
                "query": query,
                "result": "no data"
            }

        output = []

        for r in results:
            output.append({
                "labels": r.get("metric", {}),
                "value": r.get(
                    "value",
                    [None, None]
                )[1]
            })

        return {
            "query": query,
            "results": output
        }

    except Exception as e:
        return {
            "query": query,
            "error": str(e)
        }
