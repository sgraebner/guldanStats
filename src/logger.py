
import logging, os, pathlib

def setup_logger():
    log_dir = pathlib.Path("logs")
    log_dir.mkdir(exist_ok=True, parents=True)
    logfile = log_dir / "app.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.FileHandler(logfile, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("kpi-harvester")
