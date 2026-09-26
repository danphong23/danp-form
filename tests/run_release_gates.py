"""Reproducible stdlib-only runner for DANP Form static/background gates.

Examples:
    python tests/run_release_gates.py --blender "C:/.../blender.exe"
    python tests/run_release_gates.py --blender "C:/.../blender.exe" --project custom.blend
    python tests/run_release_gates.py --self-test-fail

Blender UI/modal checks are listed as NOT RUN; this runner does not pretend a
background process can replace real mouse interaction.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "tests"
STATIC_FILES = sorted(STATIC_DIR.glob("test_*.py"))
BACKGROUND_SUITES = (
    "live_control_multiselect.py",
    "live_all_control_scale.py",
    "live_shape_key_support.py",
    "live_owned_object_safety.py",
    "live_topology_recovery.py",
    "live_shape_key_target_workflow.py",
    "live_agent_target_api.py",
    "live_runtime_boundaries.py",
    "live_operation_ownership.py",
    "live_initialize_modes.py",
)
TRACEBACK_MARKERS = ("Traceback (most recent call last)", "AssertionError:", "Error: Python:")


def _run(command: list[str], cwd: Path, timeout: int = 900) -> dict:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command, cwd=cwd, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=timeout, check=False,
        )
        output = completed.stdout
        exit_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        output += "\nTIMEOUT"
        exit_code = 124
    elapsed = time.perf_counter() - started
    has_exception = any(marker in output for marker in TRACEBACK_MARKERS)
    return {
        "exit_code": exit_code,
        "exception_in_log": has_exception,
        "elapsed_seconds": round(elapsed, 3),
        "output": output,
    }


def _parse_report(output: str):
    for line in reversed(output.splitlines()):
        candidate = line.strip()
        if candidate.startswith("DANP_RESULT_JSON="):
            candidate = candidate.partition("=")[2]
        if not (candidate.startswith("{") and candidate.endswith("}")):
            continue
        for parser in (json.loads, ast.literal_eval):
            try:
                value = parser(candidate)
                if isinstance(value, dict) and "status" in value:
                    return value
            except (SyntaxError, ValueError, json.JSONDecodeError):
                continue
    return None


def _static_runner_code(test_file: Path) -> str:
    escaped = str(test_file).replace("\\", "\\\\").replace("'", "\\'")
    return "\n".join((
        "import json, runpy",
        f"ns = runpy.run_path(r'{escaped}')",
        "tests = [(name, fn) for name, fn in ns.items() if name.startswith('test_') and callable(fn)]",
        "checks = []",
        "for name, fn in tests:",
        "    fn()",
        "    checks.append(name)",
        "print('DANP_STATIC_RESULT=' + json.dumps({'status':'PASS','checks':checks}))",
    ))


def _run_static() -> list[dict]:
    results = []
    for path in STATIC_FILES:
        run = _run([sys.executable, "-c", _static_runner_code(path)], ROOT)
        report = _parse_report(run["output"].replace("DANP_STATIC_RESULT=", ""))
        passed = run["exit_code"] == 0 and not run["exception_in_log"] and report is not None
        results.append({
            "name": path.name,
            "status": "PASS" if passed else "FAIL",
            "check_count": len(report.get("checks", [])) if report else 0,
            "exit_code": run["exit_code"],
            "elapsed_seconds": run["elapsed_seconds"],
            "output_tail": run["output"].splitlines()[-8:],
        })
    return results


def _python_wrapper(script: Path, register_addon: bool = False) -> str:
    script_literal = str(script).replace("\\", "\\\\").replace("'", "\\'")
    root_literal = str(ROOT).replace("\\", "\\\\").replace("'", "\\'")
    registration = "import dan_form; dan_form.register()" if register_addon else ""
    return (
        "import json, runpy, sys\n"
        f"sys.path.insert(0, r'{root_literal}')\n"
        f"{registration}\n"
        f"ns = runpy.run_path(r'{script_literal}')\n"
        "result = ns.get('result')\n"
        "if result is not None: print('DANP_RESULT_JSON=' + json.dumps(result, default=str))\n"
    )


def _blender_fixture(blender: Path, script: Path, project: Path | None = None,
                     register_addon: bool = False) -> dict:
    command = [str(blender), "--background", "--factory-startup"]
    if project is not None:
        command.append(str(project))
    command.extend(["--python-expr", _python_wrapper(script, register_addon)])
    run = _run(command, ROOT)
    report = _parse_report(run["output"])
    passed = (run["exit_code"] == 0 and not run["exception_in_log"]
              and report is not None and report.get("status") == "PASS")
    return {
        "name": script.name,
        "status": "PASS" if passed else "FAIL",
        "exit_code": run["exit_code"],
        "exception_in_log": run["exception_in_log"],
        "elapsed_seconds": run["elapsed_seconds"],
        "report": report,
        "output_tail": run["output"].splitlines()[-12:],
    }


def _blender_version(blender: Path) -> str:
    command = [str(blender), "--background", "--factory-startup", "--python-expr",
               "import bpy; print('DANP_BLENDER_VERSION=' + bpy.app.version_string)"]
    run = _run(command, ROOT, timeout=120)
    match = re.search(r"DANP_BLENDER_VERSION=(.+)", run["output"])
    if run["exit_code"] != 0 or run["exception_in_log"] or match is None:
        raise RuntimeError("Could not establish Blender version; see runner output")
    return match.group(1).strip()


def _source_commit() -> str:
    run = _run(["git", "-c", f"safe.directory={ROOT.as_posix()}", "rev-parse", "HEAD"], ROOT, timeout=30)
    return run["output"].strip() if run["exit_code"] == 0 else "UNKNOWN"


def _self_test_failure_detection() -> dict:
    run = _run([sys.executable, "-c", "raise AssertionError('intentional harness self-test')"], ROOT)
    detected = run["exit_code"] != 0 and run["exception_in_log"]
    return {
        "name": "intentional-failure-detection",
        "status": "PASS" if detected else "FAIL",
        "expected_failure_detected": bool(detected),
        "exit_code": run["exit_code"],
        "traceback_detected": run["exception_in_log"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, help="Blender executable to use")
    parser.add_argument("--project", type=Path, help="Optional disposable .blend with an initialized Source/Controller pair for H04; otherwise generate one")
    parser.add_argument("--report", type=Path, help="Write the JSON report to this path")
    parser.add_argument("--self-test-fail", action="store_true", help="Verify that a deliberate traceback is classified as FAIL")
    args = parser.parse_args()

    if args.self_test_fail:
        result = {"harness_self_test": _self_test_failure_detection()}
        result["status"] = "PASS" if result["harness_self_test"]["status"] == "PASS" else "FAIL"
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "PASS" else 1

    if args.blender is None or not args.blender.is_file():
        parser.error("--blender must name an existing Blender executable")
    if args.project is not None and not args.project.is_file():
        parser.error("--project must name an existing disposable .blend file")

    report = {
        "status": "RUNNING",
        "metadata": {
            "blender_version": _blender_version(args.blender),
            "addon_version": _addon_version(),
            "platform": platform.platform(),
            "commit": _source_commit(),
            "fixture_project": str(args.project) if args.project else "generated two-control strip",
        },
        "static_suites": _run_static(),
        "blender_background_suites": [],
        "ui_gates": {
            "H04_modal_mouse_grs": "PASS: user accepted; see docs/testing/2026-09-25-h04-native-transform.md",
            "H05_target_selector_and_new_key": "PASS: direct UI verification recorded in docs/testing/2026-09-25-h05-target-ux.md",
            "H07_repair_undo_redo": "PASS: user accepted; see docs/testing/2026-09-25-h07-topology-recovery.md",
            "H08_overlay_gpu_review": "NOT RUN: requires a GPU-backed Blender UI",
            "performance_p95_and_peak_memory": "NOT RUN: pending representative UI instrumentation",
        },
    }

    for name in BACKGROUND_SUITES:
        report["blender_background_suites"].append(
            _blender_fixture(args.blender, ROOT / "tests" / name)
        )
    with tempfile.TemporaryDirectory(prefix="danp-h04-safe-copy-") as directory:
        if args.project is not None:
            project_copy = Path(directory) / args.project.name
            shutil.copy2(args.project, project_copy)
        else:
            project_copy = Path(directory) / "native_transform_fixture.blend"
            generator = _run([
                str(args.blender), "--background", "--factory-startup", "--python",
                str(ROOT / "tests" / "create_native_transform_fixture.py"),
                "--", str(project_copy),
            ], ROOT)
            fixture_report = _parse_report(generator["output"])
            if (generator["exit_code"] != 0 or generator["exception_in_log"]
                    or fixture_report is None or fixture_report.get("status") != "PASS"
                    or not project_copy.is_file()):
                report["blender_background_suites"].append({
                    "name": "live_native_transform.py", "status": "FAIL",
                    "reason": "Could not generate disposable native-transform fixture",
                    "generator_output_tail": generator["output"].splitlines()[-12:],
                })
                project_copy = None
        if project_copy is not None:
            report["blender_background_suites"].append(
                _blender_fixture(args.blender, ROOT / "tests" / "live_native_transform.py",
                                 project_copy, register_addon=True)
            )

    checks = report["static_suites"] + report["blender_background_suites"]
    if any(item["status"] == "FAIL" for item in checks):
        report["status"] = "FAIL"
    elif (not all(item["status"] == "PASS" for item in checks)
          or any(value.startswith("NOT RUN") for value in report["ui_gates"].values())):
        report["status"] = "INCOMPLETE"
    else:
        report["status"] = "PASS"
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + os.linesep, encoding="utf-8")
    return {"PASS": 0, "INCOMPLETE": 2, "FAIL": 1}[report["status"]]


def _addon_version() -> str:
    source = (ROOT / "dan_form" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r"\"version\"\s*:\s*\(([^)]*)\)", source)
    return match.group(1).strip().replace(" ", "") if match else "UNKNOWN"


if __name__ == "__main__":
    raise SystemExit(main())
