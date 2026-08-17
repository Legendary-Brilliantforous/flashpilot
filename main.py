import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from python.gui.qt_app import main

main()
