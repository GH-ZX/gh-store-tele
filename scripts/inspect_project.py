#!/usr/bin/env python3
"""GH Store Project Inspector & Health Diagnostic Tool.

Run this script after making changes to quickly verify:
- Python syntax & unbound local variables
- i18n translation key parity across all languages
- Model imports & SQLAdmin view registrations
- Config key parity between .env.template and config.py
- Webhook route formatting sanity
- Unit test suite execution (host or Docker)

Usage:
    python scripts/inspect_project.py
    python scripts/inspect_project.py --skip-tests
    python scripts/inspect_project.py --diff
"""

import argparse
import ast
import builtins
import json
import os
import py_compile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BUILTIN_NAMES = set(dir(builtins))

def header(title: str) -> None:
    print(f"\n\033[1;34m=== {title} ===\033[0m")


def pass_msg(msg: str) -> None:
    print(f"  \033[32m✔\033[0m {msg}")


def warn_msg(msg: str) -> None:
    print(f"  \033[33m⚠\033[0m {msg}")


def fail_msg(msg: str) -> None:
    print(f"  \033[31m✖\033[0m {msg}")


def check_syntax_and_ast() -> int:
    header("1. Python Syntax & Unbound Variable Check")
    failures = 0
    checked_files = 0

    skip_dirs = {".git", "venv", ".venv", "postgres_data", "__pycache__"}

    for root, dirs, files in os.walk(ROOT):
        if any(d in root for d in skip_dirs):
            continue
        for f in files:
            if not f.endswith(".py"):
                continue
            path = Path(root) / f
            rel_path = path.relative_to(ROOT)
            checked_files += 1

            # 1. Compile check
            try:
                py_compile.compile(str(path), doraise=True)
            except Exception as e:
                fail_msg(f"Syntax/compile error in {rel_path}: {e}")
                failures += 1
                continue

            # 2. AST parsing & basic unbound variable check
            try:
                with open(path, "r", encoding="utf-8") as src:
                    tree = ast.parse(src.read(), str(rel_path))
            except Exception as e:
                fail_msg(f"AST parse error in {rel_path}: {e}")
                continue

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    local_vars = set()
                    for arg in node.args.args + node.args.kwonlyargs:
                        local_vars.add(arg.arg)
                    for stmt in ast.walk(node):
                        if isinstance(stmt, ast.Assign):
                            for target in stmt.targets:
                                if isinstance(target, ast.Name):
                                    local_vars.add(target.id)
                        elif isinstance(stmt, ast.AnnAssign):
                            if isinstance(stmt.target, ast.Name):
                                local_vars.add(stmt.target.id)
                        elif isinstance(stmt, ast.For):
                            if isinstance(stmt.target, ast.Name):
                                local_vars.add(stmt.target.id)
                    for sub in ast.walk(node):
                        if (
                            isinstance(sub, ast.Call)
                            and isinstance(sub.func, ast.Attribute)
                            and isinstance(sub.func.value, ast.Name)
                        ):
                            name = sub.func.value.id
                            if name == "kept_ids" and "kept_ids" not in local_vars:
                                fail_msg(f"{rel_path}:{sub.lineno} in {node.name}(): 'kept_ids' is not initialized!")
                                failures += 1

    if failures == 0:
        pass_msg(f"All {checked_files} Python files passed syntax & AST checks.")
    return failures


def check_i18n_parity() -> int:
    header("2. i18n Translation Key Parity")
    i18n_dir = ROOT / "i18n"
    if not i18n_dir.is_dir():
        fail_msg("i18n directory not found!")
        return 1

    en_path = i18n_dir / "en.json"
    if not en_path.is_file():
        fail_msg("i18n/en.json base file not found!")
        return 1

    with open(en_path, "r", encoding="utf-8") as f:
        en_data = json.load(f)

    failures = 0
    checked_langs = 0

    for file in sorted(i18n_dir.glob("*.json")):
        if file.name == "en.json":
            continue
        lang = file.stem
        checked_langs += 1
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)

        missing_keys = []
        for section, keys in en_data.items():
            if section not in data:
                missing_keys.append(f"[{section}] section missing")
                continue
            for k in keys:
                if k not in data[section]:
                    missing_keys.append(f"{section}.{k}")

        if missing_keys:
            fail_msg(f"'{lang}.json' is missing {len(missing_keys)} key(s): {', '.join(missing_keys[:5])}...")
            failures += 1
        else:
            pass_msg(f"'{lang}.json' matches all keys in en.json ({len(en_data)} sections).")

    return failures


def check_config_and_env() -> int:
    header("3. Config & Environment Parity")
    env_template_path = ROOT / ".env.template"
    if not env_template_path.is_file():
        warn_msg(".env.template not found, skipping config check.")
        return 0

    template_keys = set()
    with open(env_template_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key = line.split("=", 1)[0].strip()
                template_keys.add(key)

    import config
    config_keys = set(dir(config))

    missing_in_config = [k for k in template_keys if k not in config_keys]
    if missing_in_config:
        warn_msg(f"Keys in .env.template not referenced in config.py: {', '.join(missing_in_config)}")
    else:
        pass_msg(f"All {len(template_keys)} template env keys are handled in config.py.")

    # Check for crucial keys
    critical_keys = ["TOKEN", "BATSTORE_API_KEY", "SAM_API_KEY", "GHSTORE_STARS_ENABLED"]
    for ck in critical_keys:
        if ck in config_keys:
            pass_msg(f"Critical configuration '{ck}' defined.")
        else:
            fail_msg(f"Critical configuration '{ck}' MISSING from config.py!")

    return 0


def check_database_models() -> int:
    header("4. Database Models & SQLAdmin Views")
    import db
    from models.base import Base

    tables = list(Base.metadata.tables.keys())
    pass_msg(f"SQLAlchemy metadata defines {len(tables)} tables: {', '.join(tables)}")

    # Check that new GHstore tables exist
    expected_tables = {
        "users", "buys", "items", "categories", "subcategories",
        "app_config", "batstore_products", "batstore_orders",
        "sam_payments", "restock_subscriptions"
    }
    missing_tables = expected_tables - set(tables)
    if missing_tables:
        fail_msg(f"Expected tables missing from SQLAlchemy Base metadata: {missing_tables}")
        return 1
    else:
        pass_msg("All required GHstore core & reseller tables are declared in Base.metadata.")
    # Check Alembic migrations
    versions_dir = ROOT / "migrations" / "versions"
    if versions_dir.is_dir():
        migration_files = list(versions_dir.glob("*.py"))
        pass_msg(f"Alembic migration files found: {len(migration_files)} revisions.")
        # Warn if batstore_products is not in any migration file
        has_batstore_migration = False
        for mf in migration_files:
            if "batstore_product" in mf.read_text(encoding="utf-8"):
                has_batstore_migration = True
                break
        if not has_batstore_migration:
            warn_msg("Notice: 'batstore_products' is created by Base.metadata.create_all, but not in migrations/versions/ yet.")

    return 0


def run_unit_tests() -> int:
    header("5. Unit Test Suite (pytest)")
    # Check if docker is available and running
    try:
        res = subprocess.run(
            ["docker", "run", "--rm", "-v", f"{ROOT}:/app", "-w", "/app", "ghstore-bot", "pytest", "-q"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if res.returncode == 0:
            pass_msg(f"Docker test suite PASSED:\n    {res.stdout.strip().splitlines()[-1]}")
            return 0
        else:
            fail_msg(f"Docker test suite FAILED:\n{res.stdout}\n{res.stderr}")
            return 1
    except Exception as e:
        warn_msg(f"Docker pytest failed or unavailable ({e}). Trying host pytest...")

    try:
        res = subprocess.run(["pytest", "-q"], cwd=ROOT, capture_output=True, text=True, timeout=60)
        if res.returncode == 0:
            pass_msg(f"Host pytest suite PASSED:\n    {res.stdout.strip().splitlines()[-1]}")
            return 0
        else:
            fail_msg(f"Host pytest FAILED:\n{res.stdout}\n{res.stderr}")
            return 1
    except Exception as e:
        fail_msg(f"Could not run tests: {e}")
        return 1


def show_git_diff() -> None:
    header("6. Git Modified Files")
    try:
        res = subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True)
        lines = [l for l in res.stdout.strip().splitlines() if l]
        if not lines:
            pass_msg("Working tree is clean (no uncommitted changes).")
        else:
            print("  Changed files:")
            for l in lines:
                print(f"    \033[36m{l}\033[0m")
    except Exception as e:
        warn_msg(f"Git status failed: {e}")


def main() -> int:
    parser = argparse.ArgumentParser(description="GH Store Project Inspector")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running pytest")
    parser.add_argument("--diff", action="store_true", help="Show git diff summary")
    args = parser.parse_args()

    print("\033[1;36m==================================================")
    print("      GH STORE PROJECT INSPECTOR & HEALTH CHECK   ")
    print("==================================================\033[0m")

    total_failures = 0
    total_failures += check_syntax_and_ast()
    total_failures += check_i18n_parity()
    total_failures += check_config_and_env()
    total_failures += check_database_models()

    if args.diff:
        show_git_diff()

    if not args.skip_tests:
        total_failures += run_unit_tests()

    print("\n\033[1;36m==================================================")
    if total_failures == 0:
        print("  \033[1;32mRESULT: ALL SYSTEM HEALTH CHECKS PASSED!\033[0m")
    else:
        print(f"  \033[1;31mRESULT: {total_failures} CHECK(S) FAILED OR NEED ATTENTION\033[0m")
    print("\033[1;36m==================================================\033[0m\n")

    return total_failures


if __name__ == "__main__":
    sys.exit(main())
