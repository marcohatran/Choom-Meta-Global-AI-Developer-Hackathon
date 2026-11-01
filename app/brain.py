"""Loads the proprietary prompt pack and calibration policy (app/private, not in the public repo).

Without it the app runs on the simplified open pack in app/brain_open.py.
"""

try:
    from app.private import pack as _pack
except ImportError:  # public checkout
    from app import brain_open as _pack

pack = _pack
