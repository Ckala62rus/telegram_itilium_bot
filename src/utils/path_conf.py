from pathlib import Path
from utils.logger_project import setup_logger

BasePath = Path(__file__).resolve().parent.parent
logger = setup_logger(__name__)
