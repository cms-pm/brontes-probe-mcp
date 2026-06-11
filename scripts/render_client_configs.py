#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Render MCP client config templates into README.md.

Usage:
    python scripts/render_client_configs.py          # write mode: update README
    python scripts/render_client_configs.py --check  # check mode: fail if README drifts
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
except ImportError:
    print("error: jinja2 not installed — run: pip install jinja2", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = REPO_ROOT / "docs" / "clients"
README_PATH = REPO_ROOT / "README.md"

BEGIN_MARKER = "<!-- BEGIN client-configs -->"
END_MARKER = "<!-- END client-configs -->"

DEFAULT_VARS: dict[str, str] = {
    "image_digest": "sha256:61e4d0423085ac734a938b2a45a984e5197e1803326547f5d13d519e67798e91",
    "image_tag": "0.2.2",
    "container_name": "brontes-probe-mcp",
    "transports": "stdio,socket",
}

CLIENTS: list[tuple[str, str, str]] = [
    (
        "Claude Desktop",
        "claude_desktop.json.j2",
        "Add the following entry to the `mcpServers` object in "
        "`~/Library/Application Support/Claude/claude_desktop_config.json` "
        "(Linux: `~/.config/Claude/claude_desktop_config.json`):",
    ),
    (
        "Claude Code",
        "claude_code.json.j2",
        "Add to `.mcp.json` in your project root "
        "(or `~/.claude.json` for global config):",
    ),
    (
        "Codex",
        "codex.json.j2",
        "Add to `~/.codex/config.json`:",
    ),
    (
        "OpenCode",
        "opencode.json.j2",
        "Add to `opencode.json` in your project root:",
    ),
]


def render_all(vars: dict[str, str]) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    sections: list[str] = []
    for client_name, template_file, preamble in CLIENTS:
        template = env.get_template(template_file)
        rendered_json = template.render(**vars).rstrip()
        section = f"### {client_name}\n\n{preamble}\n\n```json\n{rendered_json}\n```"
        sections.append(section)
    return "\n\n".join(sections)


def extract_between_markers(text: str) -> str:
    start = text.find(BEGIN_MARKER)
    end = text.find(END_MARKER)
    if start == -1 or end == -1:
        raise ValueError(f"README.md is missing {BEGIN_MARKER!r} or {END_MARKER!r}")
    inner = text[start + len(BEGIN_MARKER) : end]
    return inner.strip()


def inject_between_markers(text: str, rendered: str) -> str:
    start = text.find(BEGIN_MARKER)
    end = text.find(END_MARKER)
    if start == -1 or end == -1:
        raise ValueError(f"README.md is missing {BEGIN_MARKER!r} or {END_MARKER!r}")
    before = text[: start + len(BEGIN_MARKER)]
    after = text[end:]
    return f"{before}\n{rendered}\n{after}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if README content drifts from rendered templates",
    )
    args = parser.parse_args()

    rendered = render_all(DEFAULT_VARS)
    readme_text = README_PATH.read_text(encoding="utf-8")
    current = extract_between_markers(readme_text)

    if args.check:
        if current == rendered:
            print("render check: README client-configs section is up to date")
            sys.exit(0)
        else:
            print("render check FAILED: README client-configs section is out of date")
            print("Run: python scripts/render_client_configs.py")
            sys.exit(1)
    else:
        updated = inject_between_markers(readme_text, rendered)
        README_PATH.write_text(updated, encoding="utf-8")
        print("render: README client-configs section updated")


if __name__ == "__main__":
    main()
