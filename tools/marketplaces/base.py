from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class TargetDefinition:
    key: str
    label: str
    description: str
    login_required: bool
    output_schema: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MarketplaceAdapter:
    slug: str = ""
    display_name: str = ""
    target_definitions: tuple[TargetDefinition, ...] = ()
    schema_version: str = "v1"

    def list_targets(self) -> list[dict[str, Any]]:
        return [target.to_dict() for target in self.target_definitions]

    def get_target(self, target_type: str) -> TargetDefinition:
        for target in self.target_definitions:
            if target.key == target_type:
                return target
        raise ValueError(f"Unsupported target type for {self.slug}: {target_type}")

    def normalize_url(self, url: str) -> str:
        cleaned = (url or "").strip()
        if not cleaned:
            raise ValueError(f"{self.display_name} target URL is required")
        return cleaned

    def selector_map(self, target_type: str) -> dict[str, list[str]]:
        raise NotImplementedError

    def extraction_script(self, target_type: str) -> str:
        raise NotImplementedError

    def login_url(self) -> str:
        raise NotImplementedError

    def login_selectors(self) -> dict[str, str]:
        return {
            "username": "input[type='email'],input[type='text'],input[name='username'],input[name='email']",
            "password": "input[type='password']",
        }

    def requires_scroll(self, target_type: str) -> bool:
        return target_type.endswith("search")

    def scroll_iterations(self, target_type: str) -> int:
        return 3 if self.requires_scroll(target_type) else 0

    def transform_extraction(
        self,
        target_type: str,
        target_url: str,
        structured_payload: dict[str, Any] | None,
        main_content: dict[str, Any],
        navigation: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError

    def build_plan(
        self,
        target_type: str,
        target_url: str,
        account_id: str | None = None,
        proxy_label: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        target = self.get_target(target_type)
        normalized_url = self.normalize_url(target_url)
        return {
            "marketplace": self.slug,
            "target_type": target.key,
            "target_url": normalized_url,
            "login_required": target.login_required,
            "schema": target.output_schema,
            "selectors": self.selector_map(target_type),
            "account_id": account_id,
            "proxy_label": proxy_label,
            "session_id": session_id,
            "steps": [
                "navigate",
                "check_session" if target.login_required else "snapshot",
                "detect_captcha",
                "extract_main",
            ],
        }

    def validate_payload(self, target_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        target = self.get_target(target_type)
        ok, error = _validate_against_schema(payload, target.output_schema)
        if not ok:
            raise ValueError(
                f"{self.display_name} structured extraction failed schema validation for "
                f"{target_type}: {error}"
            )
        payload.setdefault("schema_version", self.schema_version)
        payload.setdefault("record_type", f"{self.slug}.{target_type}")
        return payload

    @staticmethod
    def _as_string(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    @classmethod
    def _as_string_list(cls, values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        items: list[str] = []
        for value in values:
            cleaned = cls._as_string(value)
            if cleaned and cleaned not in items:
                items.append(cleaned)
        return items


def _validate_against_schema(data: Any, schema: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "response is not a dict"
    required = schema.get("required", [])
    for key in required:
        if key not in data:
            return False, f"missing required key: {key!r}"
    props = schema.get("properties", {})
    for key, value in data.items():
        if key not in props:
            continue
        declared = props[key].get("type")
        if declared == "string" and not isinstance(value, str):
            return False, f"{key!r} should be string"
        if declared == "number" and not isinstance(value, (int, float)):
            return False, f"{key!r} should be number"
        if declared == "integer" and not isinstance(value, int):
            return False, f"{key!r} should be integer"
        if declared == "boolean" and not isinstance(value, bool):
            return False, f"{key!r} should be boolean"
        if declared == "array" and not isinstance(value, list):
            return False, f"{key!r} should be array"
        if declared == "object" and not isinstance(value, dict):
            return False, f"{key!r} should be object"
    return True, ""
