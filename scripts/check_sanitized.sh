#!/bin/sh
set -eu

cd "$(dirname "$0")/.."

fail=0

check_pattern() {
    label=$1
    pattern=$2
    if grep -RInE \
        --exclude-dir=.git \
        --exclude-dir=__pycache__ \
        --exclude=check_sanitized.sh \
        -- "$pattern" .; then
        echo "error: $label" >&2
        fail=1
    fi
}

check_pattern "machine-specific UUID found; use a placeholder" \
    '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'

check_pattern "absolute home path found; use a relative path or placeholder" \
    '/home/[A-Za-z0-9._-]+'

check_pattern "possible secret or private key found" \
    'BEGIN (OPENSSH|RSA|EC|DSA) PRIVATE KEY|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{20,}'

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    if git ls-files | grep -E '\.(aml|cpio|dat|dsl)$'; then
        echo "error: firmware dump or build artifact is tracked" >&2
        fail=1
    fi
    if git ls-files | grep -i 'obsidian'; then
        echo "error: Obsidian note is tracked" >&2
        fail=1
    fi
fi

if [ "$fail" -ne 0 ]; then
    exit 1
fi

echo "sanitization check passed"
