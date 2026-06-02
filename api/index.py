import sys
from pathlib import Path

# Adiciona API/ ao path para que as importações de main.py funcionem
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "API"))

from main import ICCollectHandler

handler = ICCollectHandler
