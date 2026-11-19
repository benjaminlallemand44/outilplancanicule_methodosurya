"""Configuration commune de la campagne de tests.

Marqueurs :
* ``excel`` : tests qui recalculent l'Excel avec LibreOffice (lents) ;
* ``interface`` : tests Playwright qui lancent l'application dans un vrai navigateur (lents).

``python -m pytest tests -m "not excel and not interface"`` pour la partie rapide.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def pytest_configure(config):
    config.addinivalue_line("markers", "excel: recalcul de l'Excel par LibreOffice (lent)")
    config.addinivalue_line("markers", "interface: navigateur réel (Playwright), lent")
