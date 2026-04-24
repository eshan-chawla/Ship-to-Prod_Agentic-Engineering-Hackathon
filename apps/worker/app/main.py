from __future__ import annotations

import signal
import sys
import time
import structlog
from sqlmodel import Session
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import create_db_and_tables, engine
from app.services.pricing_scanner import run_price_scan
from app.services.queues import ScanQueue
from app.services.supplier_scanner import run_supplier_scan

settings = get_settings()
configure_logging(settings.log_level)
log = structlog.get_logger()
running = True


def stop(_signum: int, _frame: object) -> None:
    global running
    running = False


def handle_job(job: dict) -> None:
    job_type = job.get("job_type")
    payload = job.get("payload", {})
    with Session(engine) as session:
        if job_type == "supplier_scan":
            run_supplier_scan(session, int(payload["supplier_id"]))
        elif job_type == "price_scan":
            run_price_scan(session, int(payload["product_id"]))
        else:
            log.warning("unknown_job_type", job=job)


def main() -> int:
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    create_db_and_tables()
    queue = ScanQueue(settings.redis_url)
    log.info("worker_started")
    while running:
        try:
            job = queue.pop_blocking(timeout=5)
            if not job:
                continue
            log.info("job_started", job_id=job.get("job_id"), job_type=job.get("job_type"))
            handle_job(job)
            log.info("job_completed", job_id=job.get("job_id"))
        except Exception as exc:
            log.exception("job_failed", error=str(exc))
            time.sleep(1)
    log.info("worker_stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())

