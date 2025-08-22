import logging
import pathlib


def setup_logger():
    log_dir = pathlib.Path("logs")
    log_dir.mkdir(exist_ok=True, parents=True)
    logger = logging.getLogger("kpi_harvester")
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
    sh = logging.StreamHandler()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh.setFormatter(fmt)
    sh.setFormatter(fmt)
    if not logger.handlers:
        logger.addHandler(fh)
        logger.addHandler(sh)
    return logger
