from fastapi import FastAPI, Response

app = FastAPI(title="Hestia API")


@app.post("/v1/requests")
def dispatch_request() -> Response:
    # Stub implementation to satisfy contract tests
    return Response(status_code=501)


@app.get("/v1/services/{serviceId}/status")
def get_status(serviceId: str) -> Response:  # noqa: ARG001
    return Response(status_code=501)


@app.post("/v1/services/{serviceId}/start")
def start_service(serviceId: str) -> Response:  # noqa: ARG001
    return Response(status_code=501)


# Transparent proxy path supports multiple methods; stub all
@app.get("/services/{serviceId}/{proxyPath:path}")
@app.post("/services/{serviceId}/{proxyPath:path}")
@app.put("/services/{serviceId}/{proxyPath:path}")
@app.patch("/services/{serviceId}/{proxyPath:path}")
@app.delete("/services/{serviceId}/{proxyPath:path}")
def transparent_proxy(serviceId: str, proxyPath: str) -> Response:  # noqa: ARG001
    return Response(status_code=501)


def run() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
