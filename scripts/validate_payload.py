"""
scripts/validate_payload.py

Validate 1 file JSON payload theo contracts/fragility_alert.schema.json.
Chi dung thu vien chuan - khong can cai them package (khong dung jsonschema).

Cach dung:
    python scripts/validate_payload.py sample_alert.json
    python scripts/validate_payload.py sample_alert.json --schema contracts/fragility_alert.schema.json

Exit code 0 neu hop le, 1 neu khong hop le.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def validate(payload: dict, schema: dict) -> list[str]:
    errors: list[str] = []

    required = schema.get("required", [])
    properties = schema.get("properties", {})
    additional_allowed = schema.get("additionalProperties", True)

    if not isinstance(payload, dict):
        return ["Payload phai la 1 JSON object."]

    for field in required:
        if field not in payload:
            errors.append(f"Thieu field bat buoc: '{field}'")

    if not additional_allowed:
        extra = set(payload.keys()) - set(properties.keys())
        if extra:
            errors.append(f"Co field khong duoc phep: {sorted(extra)}")

    # timestamp: string + pattern (neu schema co khai bao pattern)
    if "timestamp" in payload:
        ts = payload["timestamp"]
        ts_schema = properties.get("timestamp", {})
        if not isinstance(ts, str):
            errors.append("'timestamp' phai la string.")
        elif "pattern" in ts_schema and not re.match(ts_schema["pattern"], ts):
            errors.append(f"'timestamp' khong khop pattern: {ts_schema['pattern']}")

    # fragility_score: number, doi chieu min/max tu schema
    if "fragility_score" in payload:
        score = payload["fragility_score"]
        score_schema = properties.get("fragility_score", {})
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            errors.append("'fragility_score' phai la number.")
        else:
            lo = score_schema.get("minimum", float("-inf"))
            hi = score_schema.get("maximum", float("inf"))
            if not (lo <= score <= hi):
                errors.append(f"'fragility_score' phai trong khoang [{lo}, {hi}], nhan duoc {score}.")

    # alert_level: doc dong enum tu schema, khong hard-code
    if "alert_level" in payload:
        level = payload["alert_level"]
        allowed_levels = properties.get("alert_level", {}).get("enum", [])
        if allowed_levels and level not in allowed_levels:
            errors.append(f"'alert_level' phai la mot trong {allowed_levels}, nhan duoc: {level!r}")

    # trigger_protocols: array, doc dong enum item tu schema
    if "trigger_protocols" in payload:
        protocols = payload["trigger_protocols"]
        tp_schema = properties.get("trigger_protocols", {})
        allowed_items = tp_schema.get("items", {}).get("enum", [])
        min_items = tp_schema.get("minItems", 0)
        if not isinstance(protocols, list) or len(protocols) < min_items:
            errors.append(f"'trigger_protocols' phai la array co it nhat {min_items} phan tu.")
        elif allowed_items:
            invalid = [p for p in protocols if p not in allowed_items]
            if invalid:
                errors.append(f"Cac gia tri khong duoc phep trong 'trigger_protocols': {invalid} (chi cho phep {allowed_items})")

    # allOf: rang buoc fragility_score theo alert_level (neu schema co khai bao)
    for rule in schema.get("allOf", []):
        cond = rule.get("if", {}).get("properties", {}).get("alert_level", {}).get("const")
        if cond is not None and payload.get("alert_level") == cond:
            then_score = rule.get("then", {}).get("properties", {}).get("fragility_score", {})
            score = payload.get("fragility_score")
            if score is not None:
                lo = then_score.get("minimum", float("-inf"))
                hi = then_score.get("maximum", then_score.get("exclusiveMaximum", float("inf")))
                is_exclusive = "exclusiveMaximum" in then_score
                ok = (lo <= score < hi) if is_exclusive else (lo <= score <= hi)
                if not ok:
                    bound = f"[{lo}, {hi})" if is_exclusive else f"[{lo}, {hi}]"
                    errors.append(
                        f"Voi alert_level='{cond}', 'fragility_score' phai trong {bound}, nhan duoc {score}."
                    )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload_file", help="Duong dan file JSON can validate")
    parser.add_argument(
        "--schema",
        default="contracts/fragility_alert.schema.json",
        help="Duong dan schema (mac dinh: contracts/fragility_alert.schema.json)",
    )
    args = parser.parse_args()

    payload_path = Path(args.payload_file)
    schema_path = Path(args.schema)

    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    errors = validate(payload, schema)

    if errors:
        print(f"INVALID: {payload_path} khong khop {schema_path}")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"OK: {payload_path} khop {schema_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())