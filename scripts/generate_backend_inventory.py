#!/usr/bin/env python3
"""Generate a text inventory of the Django backend: tree + functions/summaries."""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
OUT = Path(__file__).resolve().parents[1] / "backend_inventory.txt"
SKIP_DIRS = {
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "node_modules",
    "staticfiles",
    "media",
    "migrations",
    ".pytest_cache",
    ".mypy_cache",
}


def walk_files(base: Path) -> list[str]:
    entries: list[str] = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in sorted(dirnames) if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in sorted(filenames):
            if fn.startswith("."):
                continue
            rel = (Path(dirpath) / fn).relative_to(base).as_posix()
            entries.append(rel)
    return entries


def render_tree(files: list[str]) -> list[str]:
    class Node:
        def __init__(self) -> None:
            self.children: dict[str, Node] = {}
            self.is_file = False

    root = Node()
    for f in files:
        cur = root
        parts = f.split("/")
        for i, part in enumerate(parts):
            if part not in cur.children:
                cur.children[part] = Node()
            cur = cur.children[part]
            if i == len(parts) - 1:
                cur.is_file = True

    lines = ["backend/"]

    def walk(node: Node, prefix: str = "") -> None:
        items = sorted(node.children.items(), key=lambda x: (x[1].is_file, x[0].lower()))
        for i, (name, child) in enumerate(items):
            last = i == len(items) - 1
            branch = "`-- " if last else "|-- "
            lines.append(prefix + branch + name)
            if child.children:
                ext = "    " if last else "|   "
                walk(child, prefix + ext)

    walk(root)
    return lines


def first_line_doc(node: ast.AST) -> str:
    doc = ast.get_docstring(node)
    if not doc:
        return ""
    first = doc.strip().split("\n")[0].strip()
    if len(first) > 180:
        return first[:177] + "..."
    return first


def infer_summary(name: str, kind: str, class_name: str | None = None) -> str:
    n = name.lower()
    if kind == "class":
        if n.endswith("serializer"):
            return "DRF serializer for validating/serializing API data."
        if n.endswith("view") or n.endswith("apiview"):
            return "API view handling HTTP requests for this resource."
        if n.endswith("viewset"):
            return "DRF viewset exposing CRUD/list endpoints."
        if n.endswith("admin") or n.endswith("admininline"):
            return "Django admin configuration."
        if n.endswith("form"):
            return "Form for collecting/validating user input."
        if n.endswith("test") or n.startswith("test"):
            return "Test case / test helper class."
        if n.endswith("exception") or n.endswith("error"):
            return "Custom exception type."
        if n.endswith("manager") or n.endswith("queryset"):
            return "ORM manager/queryset helper."
        return f"Class defining {name} behavior and state."
    # function / method
    if n.startswith("get_") and "queryset" in n:
        return "Returns the queryset used by this view."
    if n.startswith("get_"):
        return f"Returns {name[4:].replace('_', ' ')}."
    if n.startswith("set_"):
        return f"Sets {name[4:].replace('_', ' ')}."
    if n.startswith("is_"):
        return f"Boolean check: {name[3:].replace('_', ' ')}."
    if n.startswith("has_"):
        return f"Boolean check for presence of {name[4:].replace('_', ' ')}."
    if n.startswith("create_"):
        return f"Creates {name[7:].replace('_', ' ')}."
    if n.startswith("update_"):
        return f"Updates {name[7:].replace('_', ' ')}."
    if n.startswith("delete_") or n.startswith("remove_"):
        return f"Deletes/removes {re.sub(r'^(delete_|remove_)', '', n).replace('_', ' ')}."
    if n.startswith("validate_"):
        return f"Validates the '{name[9:]}' field or related input."
    if n == "validate":
        return "Cross-field / object-level validation."
    if n == "create":
        return "Creates and returns a new instance."
    if n == "update":
        return "Updates an existing instance."
    if n == "save":
        return "Persists changes."
    if n == "clean":
        return "Cleans/normalizes model or form data before save."
    if n == "str" or n == "__str__":
        return "Human-readable string representation."
    if n.startswith("__") and n.endswith("__"):
        return f"Special method {name}."
    if n.startswith("test_"):
        return f"Test: {name[5:].replace('_', ' ')}."
    if n in {"get", "post", "put", "patch", "delete", "list", "retrieve", "destroy"}:
        return f"Handles {n.upper()} HTTP operation."
    if n == "dispatch":
        return "Routes the request to the appropriate handler."
    if n == "perform_create":
        return "Hook run after serializer create (often sets owner/org)."
    if n == "perform_update":
        return "Hook run after serializer update."
    if n == "get_permissions":
        return "Returns permission classes for the current action."
    if n == "get_serializer_class":
        return "Chooses serializer class for the current action."
    if n == "get_object":
        return "Looks up and returns the target object for this request."
    if class_name:
        return f"Method on {class_name}."
    return f"Function implementing {name.replace('_', ' ')}."


def format_args(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    parts: list[str] = []
    args = node.args
    for a in args.posonlyargs:
        parts.append(a.arg)
    if args.posonlyargs:
        parts.append("/")
    for a in args.args:
        parts.append(a.arg)
    if args.vararg:
        parts.append("*" + args.vararg.arg)
    elif args.kwonlyargs:
        parts.append("*")
    for a in args.kwonlyargs:
        parts.append(a.arg)
    if args.kwarg:
        parts.append("**" + args.kwarg.arg)
    return ", ".join(parts)


def parse_python(path: Path) -> list[dict]:
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src)
    except SyntaxError as e:
        return [{"kind": "error", "name": "(parse error)", "summary": str(e), "lineno": 0}]

    items: list[dict] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sig = f"{node.name}({format_args(node)})"
            summary = first_line_doc(node) or infer_summary(node.name, "function")
            items.append(
                {"kind": "function", "name": sig, "summary": summary, "lineno": node.lineno}
            )
        elif isinstance(node, ast.ClassDef):
            csum = first_line_doc(node) or infer_summary(node.name, "class")
            methods = []
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    sig = f"{child.name}({format_args(child)})"
                    msum = first_line_doc(child) or infer_summary(
                        child.name, "method", class_name=node.name
                    )
                    methods.append(
                        {
                            "kind": "method",
                            "name": sig,
                            "summary": msum,
                            "lineno": child.lineno,
                        }
                    )
            items.append(
                {
                    "kind": "class",
                    "name": node.name,
                    "summary": csum,
                    "lineno": node.lineno,
                    "methods": methods,
                }
            )
    return items


def summarize_non_py(path: Path, rel: str) -> str:
    name = path.name.lower()
    if name == "requirements.txt":
        return "Python package dependencies for the backend."
    if name == "dockerfile":
        return "Container image build instructions for the backend service."
    if name.endswith(".md"):
        return "Markdown documentation."
    if name.endswith((".yml", ".yaml")):
        return "YAML configuration."
    if name.endswith(".html"):
        return "HTML template."
    if name.endswith(".txt"):
        return "Text configuration or notes."
    if name == "manage.py":
        return "Django management entrypoint."
    return f"Non-Python file ({path.suffix or 'no extension'})."


def summarize_module(rel: str, path: Path) -> str:
    try:
        mod = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        mod_doc = ast.get_docstring(mod)
        if mod_doc:
            return mod_doc.strip().split("\n")[0].strip()
    except Exception:
        pass
    name = Path(rel).stem.lower()
    hints = {
        "models": "Django ORM models for core domain entities.",
        "serializers": "DRF serializers for request/response validation and shaping.",
        "views": "HTTP API views and viewsets.",
        "urls": "URL route wiring for API endpoints.",
        "admin": "Django admin registrations.",
        "apps": "Django app configuration.",
        "tests": "Automated tests.",
        "billing_plans": "Plan catalog and pricing/capability definitions.",
        "billing_service": "Billing business logic (subscriptions, payments, entitlements).",
        "billing_views": "HTTP endpoints for billing/PayPal flows.",
        "board_service": "Posting-board domain logic.",
        "meeting_service": "Meeting lifecycle, slides, RSVP, and participation logic.",
        "meeting_wall": "Living meeting wall cards and feed helpers.",
        "meeting_wall_views": "API endpoints for meeting wall actions.",
        "meeting_analytics": "Meeting results analytics and demographic splits.",
        "meeting_export": "Export of meeting data/results.",
        "meeting_ai": "AI assistance for meetings (summaries, processing).",
        "meeting_access": "Access-code / join permission checks for meetings.",
        "directory_taxonomy": "Directory category/taxonomy definitions.",
        "directory_service": "Directory search/listing business logic.",
        "directory_views": "Directory HTTP endpoints.",
        "directory_placement": "Placement of resources/orgs in the directory.",
        "inbox_service": "Messaging/inbox domain logic.",
        "inbox_views": "Inbox HTTP endpoints.",
        "feature_entitlements": "Plan feature gates and capability checks.",
        "access_codes": "Access-code generation and uniqueness checks.",
        "contact_email": "Outbound contact/email helpers.",
        "org_access": "Organization membership and admin permission helpers.",
        "organization_create": "Organization creation flow.",
        "organization_lifecycle": "Org lifecycle transitions (activate, suspend, etc.).",
        "settings": "Django project settings.",
        "wsgi": "WSGI application entrypoint.",
        "asgi": "ASGI application entrypoint.",
        "manage": "Django management command entrypoint.",
    }
    if name in hints:
        return hints[name]
    if name.startswith("test_"):
        return f"Tests for {name[5:].replace('_', ' ')}."
    if name.endswith("_views"):
        return f"HTTP API views for {name[:-6].replace('_', ' ')}."
    if name.endswith("_service"):
        return f"Business logic for {name[:-8].replace('_', ' ')}."
    return f"Python module: {rel}"


def main() -> None:
    files = walk_files(BACKEND)
    lines: list[str] = []
    lines.append("=" * 80)
    lines.append("CommuniB backend inventory")
    lines.append(f"Root: {BACKEND}")
    lines.append("Migrations and caches are omitted from this inventory.")
    lines.append("Function summaries use docstrings when present; otherwise name-based heuristics.")
    lines.append("=" * 80)
    lines.append("")
    lines.append("DIRECTORY TREE")
    lines.append("-" * 80)
    lines.extend(render_tree(files))
    lines.append("")
    lines.append("=" * 80)
    lines.append("FILE DETAILS")
    lines.append("=" * 80)

    py_count = 0
    func_count = 0
    class_count = 0

    for rel in files:
        path = BACKEND / rel
        lines.append("")
        lines.append("-" * 80)
        lines.append(f"FILE: backend/{rel}")
        lines.append("-" * 80)

        if path.suffix != ".py":
            lines.append(f"Summary: {summarize_non_py(path, rel)}")
            lines.append("Functions: (none — not a Python module)")
            continue

        py_count += 1
        lines.append(f"Summary: {summarize_module(rel, path)}")
        items = parse_python(path)
        if not items:
            lines.append("Functions/classes: (none)")
            continue

        for item in items:
            if item["kind"] == "error":
                lines.append(f"  ERROR: {item['summary']}")
                continue
            if item["kind"] == "function":
                func_count += 1
                lines.append(f"  [function L{item['lineno']}] {item['name']}")
                lines.append(f"      {item['summary']}")
            elif item["kind"] == "class":
                class_count += 1
                lines.append(f"  [class L{item['lineno']}] {item['name']}")
                lines.append(f"      {item['summary']}")
                methods = item.get("methods") or []
                if not methods:
                    lines.append("      Methods: (none)")
                for m in methods:
                    func_count += 1
                    lines.append(f"      [method L{m['lineno']}] {m['name']}")
                    lines.append(f"          {m['summary']}")

    lines.append("")
    lines.append("=" * 80)
    lines.append(
        f"Totals: {len(files)} files listed, {py_count} Python modules, "
        f"{class_count} classes, {func_count} functions/methods."
    )
    lines.append("=" * 80)

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"files={len(files)} py={py_count} classes={class_count} funcs={func_count}")


if __name__ == "__main__":
    main()
