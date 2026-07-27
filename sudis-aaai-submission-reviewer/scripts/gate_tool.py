#!/usr/bin/env python3
"""Record manual gate evidence and oral advisor approval for one audit directory."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def load(directory: Path) -> tuple[Path, dict]:
    state_path = directory / "GATE_STATE.json"
    if not state_path.exists():
        raise SystemExit("GATE_STATE.json not found")
    return state_path, json.loads(state_path.read_text(encoding="utf-8"))


def unchanged(state: dict) -> list[str]:
    changed = []
    for raw, expected in state.get("manifest", {}).items():
        path = Path(raw)
        if not path.exists() or digest(path) != expected:
            changed.append(raw)
    return changed


def save(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def dashboard(directory: Path, state: dict, filename: str) -> None:
    rows = ["AAAI-27 GATE DASHBOARD", ""] + [f"{gate}: {data['status']}" for gate, data in state["gates"].items()]
    rows += ["", "Approval: " + (state.get("approval") or {}).get("status", "NOT APPROVED")]
    try:
        from PIL import Image, ImageDraw
        image = Image.new("RGB", (1300, 160 + len(rows) * 42), "white")
        draw = ImageDraw.Draw(image)
        for index, row in enumerate(rows):
            color = "#0a7d32" if "PASS" in row or "APPROVED" in row else "#b42318" if "FAIL" in row or "BLOCKED" in row else "#222222"
            draw.text((40, 32 + index * 42), row, fill=color)
        image.save(directory / filename)
    except ImportError:
        (directory / filename.replace(".png", ".txt")).write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    set_gate = sub.add_parser("set-gate")
    set_gate.add_argument("--audit-dir", required=True, type=Path)
    set_gate.add_argument("--gate", choices=[f"G{i}" for i in range(8)], required=True)
    set_gate.add_argument("--status", choices=["PASS", "FAIL", "BLOCKED"], required=True)
    set_gate.add_argument("--evidence", required=True)
    approve = sub.add_parser("approve")
    approve.add_argument("--audit-dir", required=True, type=Path)
    approve.add_argument("--approver", required=True)
    approve.add_argument("--confirmation", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--audit-dir", required=True, type=Path)
    args = parser.parse_args()
    directory = args.audit_dir.resolve()
    state_path, state = load(directory)
    if args.command == "set-gate":
        state["gates"][args.gate] = {"status": args.status, "reason": args.evidence, "manual_reviewed_at": datetime.now(timezone.utc).isoformat()}
        state["approval"] = None
        save(state_path, state)
        dashboard(directory, state, "GATE_DASHBOARD.png")
        return 0
    changed = unchanged(state)
    all_pass = all(data["status"] == "PASS" for data in state["gates"].values())
    if args.command == "verify":
        approved = bool(state.get("approval", {}).get("status") == "APPROVED")
        valid = all_pass and not changed and approved and (directory / "FINAL_APPROVED.png").exists()
        print(json.dumps({"valid": valid, "all_gates_pass": all_pass, "changed_files": changed, "approved": approved}, indent=2))
        return 0 if valid else 1
    if not all_pass:
        raise SystemExit("Cannot approve: every gate must be PASS.")
    if changed:
        raise SystemExit("Cannot approve: tracked files changed since audit: " + ", ".join(changed))
    state["approval"] = {"status": "APPROVED", "mode": "oral approval, self-recorded", "approver": args.approver, "confirmation": args.confirmation, "approved_at": datetime.now(timezone.utc).isoformat()}
    save(state_path, state)
    (directory / "FINAL_APPROVAL.md").write_text("# Final Approval\n\nApproved for submission for this exact manifest.\n\n- Mode: oral approval, self-recorded\n- Approver: " + args.approver + "\n- Confirmation: " + args.confirmation + "\n", encoding="utf-8")
    dashboard(directory, state, "FINAL_APPROVED.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
