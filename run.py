import os
from typing import Any

import psutil
from prometheus_client import Gauge
from prometheus_flask_exporter import PrometheusMetrics

from app import app

metrics = PrometheusMetrics(app)
metrics.info("app_info", "Application info", version="0.1.0")

memory_gauge: Gauge = Gauge("app_memory_usage_bytes", "Resident memory usage in bytes")
cpu_gauge: Gauge = Gauge("app_cpu_usage_percent", "Process CPU usage percent")


@app.before_request
def _update_system_metrics() -> None:
    process = psutil.Process(os.getpid())
    memory_gauge.set(process.memory_info().rss)
    cpu_gauge.set(process.cpu_percent(interval=None))


if __name__ == "__main__":
    host: str = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")
    port: int = int(os.environ.get("FLASK_RUN_PORT", "7001"))
    debug: bool = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host=host, port=port, debug=debug)
