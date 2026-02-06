"""
HTTP entrypoint for Cloud Run ETL service.

Listens on $PORT (default 8080) and dispatches ETL jobs
based on POST /run JSON payloads from Cloud Composer DAGs.
"""

import json
import logging
import os
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class ETLHandler(BaseHTTPRequestHandler):
    """HTTP handler that dispatches ETL jobs."""

    def do_GET(self):
        """Health check endpoint."""
        if self.path == "/" or self.path == "/health":
            self._respond(200, {"status": "healthy"})
        else:
            self._respond(404, {"error": "Not found"})

    def do_POST(self):
        """Run an ETL job."""
        if self.path != "/run":
            self._respond(404, {"error": "Not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            payload = json.loads(body) if body else {}

            job_name = payload.get("job", "")
            logger.info(f"Received job request: {job_name} with params: {payload}")

            result = self._dispatch_job(job_name, payload)
            self._respond(200, {"status": "success", "job": job_name, "result": result})

        except Exception as e:
            logger.error(f"Job failed: {e}\n{traceback.format_exc()}")
            self._respond(500, {"status": "error", "error": str(e)})

    def _dispatch_job(self, job_name: str, payload: dict) -> dict:
        """Dispatch to the appropriate ETL job."""
        if job_name == "taxi_ingestion":
            return self._run_taxi_ingestion(payload)
        elif job_name == "taxi_gold":
            return self._run_taxi_gold(payload)
        elif job_name == "bigquery_load":
            return self._run_bigquery_load(payload)
        elif job_name == "zone_lookup_ingestion":
            return self._run_zone_lookup_ingestion(payload)
        else:
            raise ValueError(f"Unknown job: {job_name}")

    def _run_taxi_ingestion(self, payload: dict) -> dict:
        from environments.prod.etl.jobs.bronze.taxi_ingestion_job import (
            run_ingestion,
            run_bulk_ingestion,
        )

        taxi_type = payload.get("taxi_type", "yellow")
        start_year = int(payload.get("start_year", 2025))
        start_month = int(payload.get("start_month", 1))
        end_year = int(payload.get("end_year", start_year))
        end_month = int(payload.get("end_month", start_month))

        # Single month or bulk
        if start_year == end_year and start_month == end_month:
            success = run_ingestion(taxi_type=taxi_type, year=start_year, month=start_month)
            return {"success": success}
        else:
            results = run_bulk_ingestion(
                taxi_type=taxi_type,
                start_year=start_year,
                start_month=start_month,
                end_year=end_year,
                end_month=end_month,
            )
            return {"results": results}

    def _run_taxi_gold(self, payload: dict) -> dict:
        from environments.prod.etl.jobs.gold.taxi_gold_job import run_gold_job

        taxi_type = payload.get("taxi_type", "yellow")
        start_year = int(payload.get("start_year", 2025))
        start_month = int(payload.get("start_month", 1))
        end_year = payload.get("end_year")
        end_month = payload.get("end_month")

        success = run_gold_job(
            taxi_type=taxi_type,
            year=start_year,
            month=start_month,
            end_year=int(end_year) if end_year is not None else None,
            end_month=int(end_month) if end_month is not None else None,
        )
        return {"success": success}

    def _run_bigquery_load(self, payload: dict) -> dict:
        from environments.prod.etl.jobs.load.bigquery_load_job import run_bigquery_load

        taxi_type = payload.get("taxi_type", "yellow")
        year = payload.get("start_year") or payload.get("year")
        month = payload.get("start_month") or payload.get("month")

        success = run_bigquery_load(
            taxi_type=taxi_type,
            year=int(year) if year is not None else None,
            month=int(month) if month is not None else None,
        )
        return {"success": success}

    def _run_zone_lookup_ingestion(self, payload: dict) -> dict:
        from environments.prod.etl.jobs.misc.zone_lookup_ingestion_job import run_zone_lookup_ingestion

        success = run_zone_lookup_ingestion()
        return {"success": success}

    def _respond(self, status_code: int, body: dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, format, *args):
        """Override to use Python logging instead of stderr."""
        logger.info(f"{self.address_string()} - {format % args}")


def main():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), ETLHandler)
    logger.info(f"ETL Cloud Run server listening on port {port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
