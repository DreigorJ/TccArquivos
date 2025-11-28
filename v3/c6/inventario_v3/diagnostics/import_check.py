#!/usr/bin/env python3
"""
Import checker that starts Django before importing app modules.

Run from project root (where manage.py lives) with:
  python -m inventario_v3.diagnostics.import_check_with_setup

It will:
- ensure project root is on sys.path
- set DJANGO_SETTINGS_MODULE if not set (defaults to 'DjangoProject.settings')
- call django.setup()
- try importing a list of modules and print full tracebacks
"""
import os
import sys
import importlib
import traceback
from pathlib import Path

# Ensure project root on sys.path (parent of this diagnostics package)
THIS = Path(__file__).resolve()
PROJECT_ROOT = THIS.parents[2] if THIS.parts[-3] == "inventario_v3" else THIS.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

print("Working dir:", Path.cwd())
print("Project root (on sys.path):", PROJECT_ROOT)
print("Python executable:", sys.executable)
print("sys.path (first entries):")
for p in sys.path[:8]:
    print("  ", p)
print()

# Ensure DJANGO_SETTINGS_MODULE is set
if "DJANGO_SETTINGS_MODULE" not in os.environ or not os.environ["DJANGO_SETTINGS_MODULE"]:
    os.environ["DJANGO_SETTINGS_MODULE"] = "DjangoProject.settings"
    print("DJANGO_SETTINGS_MODULE not set. Defaulting to:", os.environ["DJANGO_SETTINGS_MODULE"])
else:
    print("DJANGO_SETTINGS_MODULE:", os.environ["DJANGO_SETTINGS_MODULE"])

print("\nNow importing Django and calling django.setup()...\n")
try:
    import django
    django.setup()
    print("django.setup() finished OK\n")
except Exception:
    print("django.setup() FAILED")
    traceback.print_exc()
    print("Aborting further imports.\n")
    sys.exit(1)

modules = [
    "inventario_v3.models",
    "inventario_v3.forms",
    "inventario_v3.admin",
    "inventario_v3.views",
    "inventario_v3.urls",
]

for m in modules:
    print("=== Importing:", m, "===")
    try:
        importlib.invalidate_caches()
        mod = importlib.import_module(m)
        print("OK:", m, "loaded as", getattr(mod, "__name__", "<module>"))
    except Exception:
        print("FAILED importing", m)
        traceback.print_exc()
    print()

print("Done.")