import os
import ast
from pathlib import Path

ROOT = Path(".").resolve()
OUTPUT_FILE = ROOT / "architecture_report.txt"

IGNORE_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__",
    "dist", "build", "migrations", ".idea", ".vscode"
}

PYTHON_EXTENSIONS = {".py"}
FRONTEND_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx"}

KEY_FILENAMES = {
    "settings.py", "urls.py", "models.py", "views.py",
    "serializers.py", "admin.py", "apps.py"
}


def should_ignore(path: Path) -> bool:
    return any(part in IGNORE_DIRS for part in path.parts)


def build_tree(root: Path) -> list[str]:
    lines = []

    def walk(directory: Path, prefix=""):
        try:
            entries = sorted(
                [p for p in directory.iterdir() if not should_ignore(p)],
                key=lambda p: (p.is_file(), p.name.lower())
            )
        except PermissionError:
            return

        for i, entry in enumerate(entries):
            connector = "└── " if i == len(entries) - 1 else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir():
                extension = "    " if i == len(entries) - 1 else "│   "
                walk(entry, prefix + extension)

    lines.append(root.name)
    walk(root)
    return lines


def extract_python_info(file_path: Path) -> dict:
    info = {
        "classes": [],
        "functions": [],
        "imports": [],
        "django_models": [],
        "django_views": [],
    }

    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception:
        return info

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                info["imports"].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            info["imports"].append(module)
        elif isinstance(node, ast.ClassDef):
            info["classes"].append(node.name)

            base_names = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    base_names.append(base.id)
                elif isinstance(base, ast.Attribute):
                    base_names.append(base.attr)

            if "Model" in base_names:
                info["django_models"].append(node.name)

            if any(name in base_names for name in {"APIView", "View", "TemplateView", "ListView", "DetailView"}):
                info["django_views"].append(node.name)

        elif isinstance(node, ast.FunctionDef):
            info["functions"].append(node.name)

    return info


def extract_frontend_info(file_path: Path) -> dict:
    info = {
        "exports": [],
        "react_components": []
    }

    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception:
        return info

    lines = text.splitlines()
    for line in lines:
        stripped = line.strip()

        if stripped.startswith("export default "):
            info["exports"].append(stripped)

        if (
            "function " in stripped
            or "const " in stripped
            or "export default function " in stripped
        ):
            if stripped[:1].isupper() or "function " in stripped:
                info["react_components"].append(stripped)

    return info


def find_interesting_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*"):
        if should_ignore(path) or not path.is_file():
            continue
        if path.name in KEY_FILENAMES or path.suffix in PYTHON_EXTENSIONS.union(FRONTEND_EXTENSIONS):
            files.append(path)
    return sorted(files)


def summarize_project(root: Path) -> str:
    lines = []

    lines.append("ARCHITECTURE REPORT")
    lines.append("=" * 80)
    lines.append("")

    lines.append("DIRECTORY TREE")
    lines.append("-" * 80)
    lines.extend(build_tree(root))
    lines.append("")

    lines.append("KEY FILE ANALYSIS")
    lines.append("-" * 80)

    for file_path in find_interesting_files(root):
        rel = file_path.relative_to(root)
        lines.append(f"\nFILE: {rel}")

        if file_path.suffix in PYTHON_EXTENSIONS:
            info = extract_python_info(file_path)

            if info["django_models"]:
                lines.append(f"  Django models: {', '.join(info['django_models'])}")
            if info["django_views"]:
                lines.append(f"  Django views: {', '.join(info['django_views'])}")
            if info["classes"]:
                lines.append(f"  Classes: {', '.join(info['classes'][:10])}")
            if info["functions"]:
                lines.append(f"  Functions: {', '.join(info['functions'][:15])}")
            if info["imports"]:
                unique_imports = sorted(set(i for i in info["imports"] if i))
                lines.append(f"  Imports: {', '.join(unique_imports[:20])}")

        elif file_path.suffix in FRONTEND_EXTENSIONS:
            info = extract_frontend_info(file_path)
            if info["exports"]:
                lines.append(f"  Exports: {', '.join(info['exports'][:10])}")
            if info["react_components"]:
                lines.append(f"  Possible components: {', '.join(info['react_components'][:10])}")

    return "\n".join(lines)


if __name__ == "__main__":
    report = summarize_project(ROOT)
    OUTPUT_FILE.write_text(report, encoding="utf-8")
    print(f"Wrote report to: {OUTPUT_FILE}")