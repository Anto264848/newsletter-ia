"""Chemins du projet (tous relatifs à la racine du dépôt)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
PROMPTS_DIR = ROOT / "prompts"
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
DOCS_DIR = ROOT / "docs"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
