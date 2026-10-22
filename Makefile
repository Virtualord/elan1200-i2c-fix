.PHONY: all check lint test sanitize clean

all: check

check: lint test sanitize
	@echo "All checks passed."

lint:
	@if command -v shellcheck >/dev/null 2>&1; then \
		shellcheck scripts/*.sh; \
	else \
		echo "shellcheck not installed; skipping shell lint"; \
	fi
	@for script in scripts/*.sh; do sh -n "$$script"; done
	@python3 -m py_compile scripts/*.py tests/*.py

test:
	@python3 -m unittest discover -s tests -v

sanitize:
	@scripts/check_sanitized.sh

clean:
	@find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	@find . -name '*.pyc' -delete
