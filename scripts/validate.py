#!/usr/bin/env python3
"""Local Pre-Flight Validator for Media Hue Sync.

Runs all Hassfest-style manifest/translation rules, Python syntax checks,
JSON validation, Pytest suite, and palette regression tests before pushing.
"""

from __future__ import annotations

import glob
import json
from pathlib import Path
import py_compile
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
COMPONENT_DIR = ROOT / "custom_components" / "media_hue_sync"


def print_step(name: str) -> None:
    print(f"\n==> \033[1;34m{name}\033[0m")


def print_success(msg: str) -> None:
    print(f"  \033[32m✓\033[0m {msg}")


def print_error(msg: str) -> None:
    print(f"  \033[31m✗\033[0m {msg}", file=sys.stderr)


def check_python_syntax() -> bool:
    print_step("Checking Python Syntax Compilation")
    py_files = list(ROOT.glob("custom_components/media_hue_sync/**/*.py")) + list(ROOT.glob("tests/**/*.py")) + [Path(__file__)]
    failed = False
    for py_file in py_files:
        try:
            py_compile.compile(str(py_file), doraise=True)
        except py_compile.PyCompileError as err:
            print_error(f"Syntax error in {py_file.relative_to(ROOT)}: {err}")
            failed = True
    if not failed:
        print_success(f"All {len(py_files)} Python files compiled cleanly.")
    return not failed


def check_json_files() -> bool:
    print_step("Checking JSON Files")
    json_files = [Path(p) for p in glob.glob(f"{ROOT}/**/*.json", recursive=True) if ".venv" not in p and ".pytest_cache" not in p]
    failed = False
    for json_file in json_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                json.load(f)
        except Exception as err:
            print_error(f"Invalid JSON in {json_file.relative_to(ROOT)}: {err}")
            failed = True
    if not failed:
        print_success(f"All {len(json_files)} JSON files are valid.")
    return not failed


def check_manifest() -> bool:
    print_step("Checking manifest.json (Hassfest Rules)")
    manifest_path = COMPONENT_DIR / "manifest.json"
    if not manifest_path.exists():
        print_error("manifest.json not found.")
        return False

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    keys = list(data.keys())
    if len(keys) < 2 or keys[0] != "domain" or keys[1] != "name":
        print_error("Manifest keys must start with 'domain' followed by 'name'.")
        return False

    remaining_keys = keys[2:]
    sorted_remaining = sorted(remaining_keys)
    if remaining_keys != sorted_remaining:
        print_error(f"Manifest keys are not in alphabetical order after 'name'.\n    Current: {remaining_keys}\n    Expected: {sorted_remaining}")
        return False

    required = ["domain", "name", "codeowners", "config_flow", "dependencies", "documentation", "iot_class", "version"]
    missing = [k for k in required if k not in data]
    if missing:
        print_error(f"manifest.json is missing required fields: {missing}")
        return False

    print_success(f"manifest.json satisfies Hassfest structure and sorting (v{data.get('version')}).")
    return True


def check_translations() -> bool:
    print_step("Checking strings.json & Translations (Hassfest Rules)")
    files = [COMPONENT_DIR / "strings.json", COMPONENT_DIR / "translations" / "en.json"]
    failed = False

    for file_path in files:
        if not file_path.exists():
            continue
        rel = file_path.relative_to(ROOT)
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Check config and options step data_description vs data
        for section in ["config", "options"]:
            steps = data.get(section, {}).get("step", {})
            for step_name, step_data in steps.items():
                fields = set(step_data.get("data", {}).keys())
                descriptions = set(step_data.get("data_description", {}).keys())
                extra = descriptions - fields
                if extra:
                    print_error(f"{rel}: {section}.step.{step_name}.data_description has keys not present in data: {extra}")
                    failed = True

        # Check select entities do not contain 'options' key
        selects = data.get("entity", {}).get("select", {})
        for select_name, select_data in selects.items():
            if "options" in select_data:
                print_error(f"{rel}: entity.select.{select_name} contains disallowed 'options' dictionary. Move options to selector.{select_name}.options or use entity.select.{select_name}.state.")
                failed = True

    if not failed:
        print_success("strings.json and translations pass Hassfest schema checks.")
    return not failed


def run_tests() -> bool:
    print_step("Running Unit & Palette Regression Tests")
    pytest_bin = ROOT / ".venv" / "bin" / "pytest"
    cmd = [str(pytest_bin) if pytest_bin.exists() else "pytest", "-v"]

    res = subprocess.run(cmd, cwd=str(ROOT))
    if res.returncode != 0:
        print_error("Pytest test suite failed.")
        return False

    print_success("All pytest unit and regression tests passed.")
    return True


def main() -> int:
    print("\n\033[1;36m=== Media Hue Sync Pre-Flight Validation ===\033[0m")
    checks = [
        check_python_syntax,
        check_json_files,
        check_manifest,
        check_translations,
        run_tests,
    ]

    for check in checks:
        if not check():
            print(f"\n\033[1;31mPre-flight validation FAILED. Fix errors before pushing.\033[0m\n")
            return 1

    print(f"\n\033[1;32m=== Pre-flight validation PASSED cleanly! ===\033[0m\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
