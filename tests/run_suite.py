"""
Resource-safe test runner: every test file in its own pytest process, one after another, under a memory cap.

    python tests/run_suite.py                      # all test files
    python tests/run_suite.py --layer regression   # one layer (see LAYERS; --list shows them)
    python tests/run_suite.py tests/test_drift.py tests/test_pseudo3d.py
    python tests/run_suite.py --layer integration -- -k pipeline   # arguments after -- go to pytest

Why (2026-10-21): pytest -n 8 / -n 2 on a 14 GiB machine was killed by the kernel OOM killer (one worker reached
11.8 GiB on a DXF fuzz case). This runner never runs two files at once, caps each process's address space (RLIMIT_AS),
kills a process whose resident memory passes --max-rss-gib or when the machine's available memory falls below
--min-free-gib, and records wall time and peak RSS per file.

Exit status 0 only when every selected file ran to completion with no failure or error. A timeout, a kill, a crash
(signal), "no tests collected" or missing results is reported as INTERRUPTED / ERROR and gives exit status 1 - an
incomplete run is never reported as a success. Skips and xfails are listed with their reasons. Logs, JUnit XML and
summary.md go to --out (default: a new directory in the system temp folder), never into the repository; files that
the tests leave in the repository (git status before / after) are reported as an error.
"""
import argparse
import glob
import os
import resource
import signal
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GIB = 1024 ** 3

# Test layers (a file may be in several). New test files not listed here still run with --layer all and are
# reported as unclassified so that the table is kept up to date.
LAYERS = {
    "unit": ["test_materials", "test_bbs_module", "test_grid_manager", "test_cad_parser", "test_wall_design",
             "test_estimation_refinements", "test_dxf_exporter", "test_site_tools", "test_new_modules",
             "test_risk_management", "test_risk_safeguards", "test_ui_tables", "test_column_editor",
             "test_column_placer", "test_beam_placer", "test_audit", "test_member_design", "test_analysis_config",
             "test_calculations", "test_sections", "test_quantity_takeoff", "test_slab_generator",
             "test_layout_scorer", "test_validators"],
    "geometry": ["test_geometry_validation", "test_dxf_corpus", "test_dxf_layers", "test_dxf_conventions", "test_cad_parser",
                 "test_beam_placer", "test_column_placer", "test_grid_manager"],
    "engineering": ["test_section_design", "test_sp16_benchmarks", "test_is456_tables", "test_is1893_2016",
                    "test_is13920_2016", "test_is875_wind", "test_durability", "test_fea_benchmarks", "test_fea_repro",
                    "test_pseudo3d", "test_lateral_sharing", "test_drift", "test_foundation_eng", "test_load_modeling",
                    "test_wall_width_columns"],
    "integration": ["test_pipeline_e2e", "test_realistic_buildings", "test_drawings", "test_streamlit_app",
                    "test_ui_tables", "test_new_modules"],
    "regression": ["test_audit_findings", "test_geometry_validation", "test_dxf_robustness", "test_dxf_corpus",
                   "test_invariants",
                   "test_metamorphic", "test_design_matrix"],
    "reference": ["test_hand_check_complex_house", "test_sp16_benchmarks", "test_fea_benchmarks", "test_is456_tables",
                  "test_section_design", "test_pseudo3d", "test_drift"],
}


def all_files():
    return sorted(Path(p).stem for p in glob.glob(str(ROOT / "tests" / "test_*.py")))


def mem_available_gib():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024 / GIB
    except OSError:
        pass
    return None


def rss_gib(pid):
    """Resident memory of a process and its children (pytest may start subprocesses)."""
    total = 0
    pids = [pid]
    try:
        out = subprocess.run(["ps", "-o", "pid=", "--ppid", str(pid)], capture_output=True, text=True).stdout
        pids += [int(p) for p in out.split()]
    except (OSError, ValueError):
        pass
    for p in pids:
        try:
            with open(f"/proc/{p}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        total += int(line.split()[1]) * 1024
        except OSError:
            continue
    return total / GIB


def git_status():
    """{path: content hash} of every modified or untracked file, so that a test changing a file that was already
    modified before the run is caught too (the porcelain line alone would not change)."""
    import hashlib
    try:
        lines = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        return None
    snap = {}
    for line in lines:
        path = line[3:].split(" -> ")[-1].strip('"')
        try:
            snap[path] = hashlib.sha1((ROOT / path).read_bytes()).hexdigest()
        except OSError:
            snap[path] = "deleted"
    return snap


def parse_junit(path):
    """(counts, skip reasons) from pytest's JUnit XML; None when the file is missing or unreadable."""
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None, []
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    c = {k: sum(int(s.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
    reasons = []
    for case in root.iter("testcase"):
        for sk in case.findall("skipped"):
            reasons.append(f"{case.get('name')}: {sk.get('type', '')} {sk.get('message', '')}".strip())
    c["passed"] = c["tests"] - c["failures"] - c["errors"] - c["skipped"]
    return c, reasons


def run_file(stem, args, out, extra):
    log, xml = out / f"{stem}.log", out / f"{stem}.xml"
    xml.unlink(missing_ok=True)                           # a stale result must never be read for a killed run
    for _ in range(30):                                   # wait up to 60 s for memory to come back
        free = mem_available_gib()
        if free is None or free >= args.min_free_gib:
            break
        time.sleep(2)
    else:
        return dict(file=stem, status="INTERRUPTED", note=f"not started: only {free:.1f} GiB available", wall=0.0,
                    rss=0.0, counts=None, skips=[])
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    cmd = [sys.executable, "-m", "pytest", f"tests/{stem}.py", "-p", "no:cacheprovider", "-p", "no:xdist",
           "-o", "addopts=", "-q", "-rsx", f"--junitxml={xml}"] + extra
    cap = int(args.as_limit_gib * GIB)

    def limit():
        resource.setrlimit(resource.RLIMIT_AS, (cap, cap))

    t0, note, peak = time.time(), "", 0.0
    with open(log, "w") as fh:
        fh.write("$ " + " ".join(cmd) + "\n")
        fh.flush()
        proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT, preexec_fn=limit,
                                start_new_session=True)
        status_code, usage = None, None
        while True:
            pid, st, usage = os.wait4(proc.pid, os.WNOHANG)
            if pid:
                status_code = st
                break
            peak = max(peak, rss_gib(proc.pid))
            free = mem_available_gib()
            reason = None
            if time.time() - t0 > args.timeout:
                reason = f"timeout after {args.timeout:.0f} s"
            elif peak > args.max_rss_gib:
                reason = f"resident memory {peak:.1f} GiB > {args.max_rss_gib} GiB"
            elif free is not None and free < args.kill_free_gib:
                reason = f"machine memory available {free:.1f} GiB < {args.kill_free_gib} GiB"
            if reason:
                note = "killed: " + reason
                os.killpg(proc.pid, signal.SIGKILL)
                _, status_code, usage = os.wait4(proc.pid, 0)
                break
            time.sleep(0.5)
        proc.returncode = os.waitstatus_to_exitcode(status_code)
    wall = time.time() - t0
    peak = max(peak, usage.ru_maxrss * 1024 / GIB if usage else 0.0)
    counts, skips = parse_junit(xml)
    rc = proc.returncode
    if note:
        status = "INTERRUPTED"
    elif rc < 0:
        status, note = "INTERRUPTED", f"terminated by signal {-rc} ({signal.Signals(-rc).name})"
    elif rc == 0 and counts is not None:
        status = "PASS"
    elif rc == 1:
        status = "FAIL"
    elif rc == 5:
        status, note = "ERROR", "no tests collected"
    else:
        status, note = "ERROR", f"pytest exit code {rc}" + ("" if counts else "; no JUnit result")
    return dict(file=stem, status=status, note=note, wall=wall, rss=peak, counts=counts, skips=skips)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("files", nargs="*", help="test files (default: the selected layer)")
    ap.add_argument("--layer", default="all", choices=["all"] + sorted(LAYERS))
    ap.add_argument("--list", action="store_true", help="show layers and unclassified files, then exit")
    ap.add_argument("--as-limit-gib", type=float, default=6.0, help="RLIMIT_AS per test process (default 6)")
    ap.add_argument("--max-rss-gib", type=float, default=4.0, help="kill a file above this resident memory (4)")
    ap.add_argument("--min-free-gib", type=float, default=3.0, help="do not start a file below this available (3)")
    ap.add_argument("--kill-free-gib", type=float, default=1.0, help="kill a file below this available memory (1)")
    ap.add_argument("--timeout", type=float, default=900.0, help="seconds per file (default 900)")
    ap.add_argument("--out", help="directory for logs, JUnit XML and summary.md (default: new temp directory)")
    argv = sys.argv[1:] if argv is None else argv
    extra = argv[argv.index("--") + 1:] if "--" in argv else []
    args = ap.parse_args(argv[:argv.index("--")] if "--" in argv else argv)

    every = all_files()
    unclassified = [f for f in every if not any(f in v for v in LAYERS.values())]
    if args.list:
        for k, v in LAYERS.items():
            print(f"{k:12s} {' '.join(v)}")
        print(f"{'unclassified':12s} {' '.join(unclassified) or '-'}")
        return 0
    if args.files:
        stems = [Path(f).stem for f in args.files]
    else:
        stems = every if args.layer == "all" else LAYERS[args.layer]
    missing = [s for s in stems if not (ROOT / "tests" / f"{s}.py").exists()]
    if missing:
        print("No such test file: " + ", ".join(missing), file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="structoptima-tests-"))
    out.mkdir(parents=True, exist_ok=True)
    if out.resolve().is_relative_to(ROOT):
        print("--out must be outside the repository", file=sys.stderr)
        return 2

    before = git_status()
    print(f"{len(stems)} file(s), sequential; logs in {out}", flush=True)
    results = []
    for s in stems:
        r = run_file(s, args, out, extra)
        results.append(r)
        c = r["counts"] or {}
        print(f"{r['status']:11s} {s:38s} {c.get('passed', '-'):>4} passed {c.get('failures', '-'):>3} "
              f"failed {c.get('errors', '-'):>2} err {c.get('skipped', '-'):>3} skip  {r['wall']:7.1f} s "
              f"{r['rss'] * 1024:7.0f} MB  {r['note']}", flush=True)
    after = git_status()
    written = sorted({p for p in after if before.get(p) != after[p]} | (set(before) - set(after))) \
        if before is not None and after is not None else []

    tot = {k: sum((r["counts"] or {}).get(k, 0) for r in results) for k in ("passed", "failures", "errors", "skipped")}
    bad = [r for r in results if r["status"] != "PASS"]
    lines = [f"# Test run {time.strftime('%Y-%m-%d %H:%M')}", "",
             f"Files: {len(results)}; passed tests {tot['passed']}, failed {tot['failures']}, errors {tot['errors']}, "
             f"skipped / xfailed {tot['skipped']}. Files not PASS: {len(bad)}.", "",
             "| File | Status | Passed | Failed | Errors | Skipped | Wall (s) | Peak RSS (MB) | Note |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        c = r["counts"] or {}
        lines.append(f"| {r['file']} | {r['status']} | {c.get('passed', '-')} | {c.get('failures', '-')} | "
                     f"{c.get('errors', '-')} | {c.get('skipped', '-')} | {r['wall']:.1f} | {r['rss'] * 1024:.0f} | "
                     f"{r['note']} |")
    skips = [(r["file"], s) for r in results for s in r["skips"]]
    if skips:
        lines += ["", "## Skipped / xfailed", ""] + [f"- {f}: {s}" for f, s in skips]
    if unclassified:
        lines += ["", "Unclassified test files (add them to LAYERS in tests/run_suite.py): " + ", ".join(unclassified)]
    if written:
        lines += ["", "## Files left in the repository by the tests (not allowed)", ""] + [f"- `{w}`" for w in written]
    (out / "summary.md").write_text("\n".join(lines) + "\n")

    print(f"\nTOTAL {tot['passed']} passed, {tot['failures']} failed, {tot['errors']} errors, {tot['skipped']} "
          f"skipped/xfailed in {len(results)} file(s); summary: {out / 'summary.md'}")
    for f, s in skips:
        print(f"  SKIP {f}: {s}")
    if unclassified and args.layer == "all" and not args.files:
        print("  unclassified: " + ", ".join(unclassified))
    for w in written:
        print(f"  WRITTEN INTO THE REPOSITORY: {w}")
    for r in bad:
        print(f"  NOT PASSED {r['file']}: {r['status']} {r['note']} (log {out / (r['file'] + '.log')})")
    ok = not bad and not written
    print("RESULT: " + ("PASS" if ok else "NOT PASSED - see above"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
