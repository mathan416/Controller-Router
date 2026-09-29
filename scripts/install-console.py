#!/usr/bin/env python3
"""Install Router's connection service independently of either controller product."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from router_shared.pairing_install import install

if __name__ == '__main__':
    install(None, None)
