#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import argparse
import json
from pathlib import Path
import statistics


def primary_samples(path):
    text = path.read_text()
    decoder = json.JSONDecoder()
    captures = []
    for line in text.splitlines():
        if "PERFHERDER_DATA:" in line:
            try:
                captures.append(decoder.raw_decode(line.split("PERFHERDER_DATA:", 1)[1].strip())[0])
            except json.JSONDecodeError:
                pass
    if not captures:
        captures = [json.loads(text)]
    samples = {}
    for suite in captures[-1]["suites"]:
        for subtest in suite["subtests"]:
            if subtest["name"].endswith("-primary"):
                samples[subtest["name"][:-8]] = subtest["replicates"]
    if not samples or any(len(values) != 5 for values in samples.values()):
        raise ValueError(f"{path} must contain five primary samples for every subtest")
    return samples


def cov(values):
    return statistics.stdev(values)/statistics.mean(values)


def compare(baseline, current):
    rows = []
    for name in sorted(baseline.keys() & current.keys()):
        before, after = baseline[name], current[name]
        base, result = statistics.median(before), statistics.median(after)
        tolerance = max(.05, 2*cov(before))
        delta = result/base-1
        rows.append({"subtest": name, "baseline": base, "current": result,
            "baseline_cov": cov(before), "current_cov": cov(after),
            "tolerance": tolerance, "delta": delta, "outside": abs(delta) > tolerance})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--current", type=Path, default=Path("artifacts/navgauntlet_run5_phase3.log"))
    parser.add_argument("--out", type=Path, default=Path("artifacts/navgauntlet_phase3_drift.md"))
    parser.add_argument("--explanations", type=Path)
    args = parser.parse_args()
    baseline_path = args.baseline or Path("artifacts/navgauntlet_run5_net_quiet.log")
    if not baseline_path.exists():
        baseline_path = Path("artifacts/navgauntlet_results5_net.json")
    baseline, current = primary_samples(baseline_path), primary_samples(args.current)
    explanations = json.loads(args.explanations.read_text()) if args.explanations else {}
    rows = compare(baseline, current)
    lines = ["# Navigation gauntlet Phase 3 drift", "",
        f"Baseline: `{baseline_path}`. Current: `{args.current}`. Five cycles each; no samples discarded.", "",
        "Tolerance is max(5%, twice the baseline sample CoV). CoV is sample standard deviation / mean. "
        "This descriptive noise budget was selected before the Phase 3 browser run; it is not a significance test. "
        "The quiet baseline supersedes the older network report. All times are milliseconds.", "",
        "| Subtest | Baseline | Phase 3 | Delta % | Baseline CoV % | Phase 3 CoV % | Tolerance % | Assessment |",
        "|---|---:|---:|---:|---:|---:|---:|---|"]
    for row in rows:
        assessment = explanations.get(row["subtest"], "UNEXPLAINED") if row["outside"] else "Within tolerance"
        lines.append(f"| {row['subtest']} | {row['baseline']:.2f} | {row['current']:.2f} | {100*row['delta']:+.2f} | {100*row['baseline_cov']:.2f} | {100*row['current_cov']:.2f} | {100*row['tolerance']:.2f} | {assessment} |")
    outside = [row for row in rows if row["outside"]]
    missing = baseline.keys()-current.keys()
    lines += ["", f"{len(rows)-len(outside)}/{len(rows)} comparable subtests within tolerance; {len(outside)} outside.",
        "", "New diagnostics: "+(", ".join(sorted(current.keys()-baseline.keys())) or "none")+".",
        "Missing baseline diagnostics: "+(", ".join(sorted(missing)) or "none")+".",
        "", "Image changes are intentional: only catalogue→product and image-hero wait for decode. "
        "SPA/hydration rendering no longer waits for images; resource-specific network pages still wait for image load. "
        "The hero diagnostic is excluded from the unchanged 29-member composite.", ""]
    args.out.write_text("\n".join(lines))
    print(args.out)
    if missing or any(row["subtest"] not in explanations for row in outside):
        raise SystemExit("Missing samples or unexplained drift; see report")


if __name__ == "__main__":
    main()
