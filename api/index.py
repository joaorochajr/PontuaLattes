import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "API"))

from main import ICCollectHandler


class handler(ICCollectHandler):
    pass
