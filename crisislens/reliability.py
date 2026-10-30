"""Conservative structured evidence checks; not semantic truth verification."""
import re
from collections import defaultdict
from datetime import datetime, timezone, timedelta

UNITS = {"food": "kits", "water": "litres", "medical": "kits", "shelter": "places", "other": "items"}


def current(report):
    try:
        at = datetime.fromisoformat(report["observed_at"].replace("Z", "+00:00"))
        return at.tzinfo is not None and timedelta(minutes=-5) <= datetime.now(timezone.utc)-at <= timedelta(hours=6)
    except (KeyError, ValueError, TypeError):
        return False


def annotate_reports(reports):
    """Compare exact normalized landmarks only. Never infer free-text agreement."""
    groups = defaultdict(list)
    for r in reports:
        r["conflicts"] = []
        r["missing_checks"] = []
        if r.get("access_status", "unknown") == "unknown":
            r["missing_checks"].append("Current access is not recorded")
        if not r.get("resources"):
            r["missing_checks"].append("Requested quantities are not recorded")
        if r.get("status") not in ("rejected", "resolved") and current(r):
            key = (r.get("location"), re.sub(r"\W+", " ", r.get("landmark", "").casefold()).strip())
            groups[key].append(r)
    for group in groups.values():
        for r in group:
            for other in group:
                if r["id"] == other["id"]:
                    continue
                reasons = []
                a, b = r.get("access_status", "unknown"), other.get("access_status", "unknown")
                if "unknown" not in (a, b) and a != b:
                    reasons.append("Reports disagree about access")
                a, b = r.get("demand_status", "unknown"), other.get("demand_status", "unknown")
                if "unknown" not in (a, b) and a != b:
                    reasons.append("Reports disagree about whether help is needed")
                quantities = {v["kind"]: v["quantity"] for v in other.get("resources", [])}
                if any(v["kind"] in quantities and v["quantity"] != quantities[v["kind"]] for v in r.get("resources", [])):
                    reasons.append("Reported quantities differ; do not add them together")
                if reasons:
                    r["conflicts"].append({"report_id": other["id"], "reasons": reasons})
    return reports


def resource_check(report, available):
    """One selected request only: no cross-site summation, extrapolation or unit conversion."""
    usable = bool(report and report.get("status") == "reviewed" and current(report)
                  and not report.get("pending_updates") and not report.get("conflicts")
                  and report.get("access_status") != "blocked" and report.get("demand_status") != "not_needed")
    recorded = (report or {}).get("resources", [])
    if len({r["kind"] for r in recorded}) != len(recorded):
        usable = False
    stock = defaultdict(float)
    for item in available:
        stock[item["kind"]] += item["quantity"]
    rows = []
    for item in (report or {}).get("resources", []):
        kind, need = item["kind"], item["quantity"]
        amount = min(need, stock[kind]) if usable else None
        rows.append({"kind": kind, "unit": UNITS[kind], "requested": need, "available": stock[kind],
                     "suggested_max": amount, "uncovered": max(0, need-stock[kind]) if usable else None})
    missing = list((report or {}).get("missing_checks", []))
    if not report:
        missing.append("No current selected report")
    else:
        if report.get("access_status", "unknown") == "unknown":
            missing.append("Current access is not recorded")
        if report.get("demand_status", "unknown") == "unknown":
            missing.append("Current demand status is not recorded")
        if not recorded:
            missing.append("Requested quantities are not recorded")
    return {"report_id": (report or {}).get("id"),
            "source_id": "F"+report["id"] if report else None,
            "access_status": (report or {}).get("access_status", "unknown"),
            "demand_status": (report or {}).get("demand_status", "unknown"),
            "status": "bounded_proposal" if usable and rows else "hold_for_check",
            "rows": rows, "conflicts": (report or {}).get("conflicts", []),
            "missing_checks": list(dict.fromkeys(missing)),
            "note": "Per-request upper bounds, not allocations. Check contact, access and receiving time. No stock is reserved."}
