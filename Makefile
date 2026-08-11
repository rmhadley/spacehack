# spacehack — build & dist automation
#
# Targets:
#   make dist   — build wheel + assemble dist/ package (default)
#   make clean  — remove build artifacts
#
# The dist/ folder contains everything someone needs to run the game
# (assuming Python 3.10+ is already installed):
#
#   dist/spacehack/
#   ├── spacehack-<version>-py3-none-any.whl
#   ├── run.py                      # cross-platform launcher
#   ├── run_spacehack.bat           # Windows: double-click
#   └── run_spacehack               # macOS/Linux: terminal: sh run_spacehack

.PHONY: dist zip app pyinstaller clean

# Use the project venv if available (avoids macOS "externally-managed" errors
# and ensures build/pip are both present).  Falls back to bare python3.
PYTHON := $(shell if [ -f .venv/bin/python3 ]; then echo .venv/bin/python3; else echo python3; fi)

# Version — read from pyproject.toml, fall back to 0.0.1 on failure.
# Uses a regex grep (not tomllib) so it works on Python 3.10+.
VERSION := $(shell $(PYTHON) -c \
  "import re; print(re.search(r'version\\s*=\\s*\"([^\"]+)\"', open('pyproject.toml').read()).group(1))" \
  2>/dev/null || echo "0.0.1")

# ──────────────────────────────────────────────
# dist  — default target, builds dist/ package
# ──────────────────────────────────────────────
dist: dist/spacehack/run.py dist/spacehack/run_spacehack.bat \
      dist/spacehack/run_spacehack \
      dist/spacehack/spacehack-$(VERSION)-py3-none-any.whl
	@echo "─── Package ready in dist/spacehack/ ───"
	@ls -1 dist/spacehack/

# Build the wheel from source.
dist/spacehack/spacehack-%-py3-none-any.whl:
	$(PYTHON) -m pip install build --quiet
	$(PYTHON) -m build --wheel --outdir dist
	@mkdir -p dist/spacehack
	mv dist/spacehack-*.whl dist/spacehack/

# Copy launcher scripts (unversioned, regenerated from repo root).
dist/spacehack/run.py: run.py
	@mkdir -p dist/spacehack
	cp run.py dist/spacehack/

dist/spacehack/run_spacehack.bat: run_spacehack.bat
	@mkdir -p dist/spacehack
	cp run_spacehack.bat dist/spacehack/

dist/spacehack/run_spacehack: run_spacehack
	@mkdir -p dist/spacehack
	cp run_spacehack dist/spacehack/
	chmod +x dist/spacehack/run_spacehack

# Current date for dev builds (YYYYMMDD).
ZIP_DATE := $(shell date +%Y%m%d)

# ──────────────────────────────────────────────
# zip  — bundle dist/spacehack/ into a single .zip for sharing
# ──────────────────────────────────────────────
zip: dist
	@cd dist && zip -r spacehack-dev-$(ZIP_DATE).zip spacehack/
	@echo "─── Zip ready: dist/spacehack-dev-$(ZIP_DATE).zip ───"

# ──────────────────────────────────────────────
# pyinstaller — build standalone .app (macOS) or .exe (Windows)
# Requires: pip install pyinstaller
# ──────────────────────────────────────────────
pyinstaller:
	$(PYTHON) -m pip install pyinstaller --quiet 2>/dev/null || true
	# PYINSTALLER_STRICT_BUNDLE_CODESIGN_ERROR: fail if PyInstaller's own
	# bundle signing fails (default is a warning-only, unsigned .app).
	PYINSTALLER_STRICT_BUNDLE_CODESIGN_ERROR=1 pyinstaller --clean --noconfirm spacehack.spec
	@echo "─── Standalone build ready in dist/ ───"

# ──────────────────────────────────────────────
# app — macOS .app: build, ad-hoc deep-sign, verify
# macOS enforces a signature on every nested binary (mandatory on Apple
# Silicon); an unsigned bundle opens as "damaged".  Ad-hoc signing with
# identity '-' needs no Apple certificate and is exactly what the OS
# requires to accept the architecture components cleanly.
# ──────────────────────────────────────────────
app: pyinstaller
	@if [ "$$(uname -s)" = "Darwin" ]; then \
		codesign --force --deep --sign - dist/spacehack.app; \
		codesign --verify --deep --strict --verbose=2 dist/spacehack.app; \
		cp "packaging/Open Spacehack.command" dist/; \
		chmod +x "dist/Open Spacehack.command"; \
		echo "─── Signed spacehack.app + Gatekeeper launcher ready in dist/ ───"; \
	else \
		echo "─── .app bundle + codesign require macOS (skipped on $$(uname -s)) ───"; \
	fi

# ──────────────────────────────────────────────
# clean
# ──────────────────────────────────────────────
clean:
	rm -rf build/ dist/ *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
