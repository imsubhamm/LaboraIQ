"""Catalogue validation helpers for specimen meta, price, and clinical ranges."""

from __future__ import annotations

from decimal import Decimal

from app.models import TestCatalogItem, TestCatalogParameter

PLACEHOLDER_SPECIMENS = {"", "specimen", "unspecified", "n/a", "na", "none"}
PLACEHOLDER_CONTAINERS = {"", "unspecified", "n/a", "na", "none"}


def is_placeholder_specimen(value: str | None) -> bool:
    return (value or "").strip().lower() in PLACEHOLDER_SPECIMENS


def is_placeholder_container(value: str | None) -> bool:
    return (value or "").strip().lower() in PLACEHOLDER_CONTAINERS


def parameter_has_limits(parameter: TestCatalogParameter) -> bool:
    return bool(
        parameter.reference_low
        or parameter.reference_high
        or parameter.reference_text
        or parameter.critical_low
        or parameter.critical_high
    )


def parameter_limits_need_source(parameter: TestCatalogParameter) -> bool:
    return parameter_has_limits(parameter) and not (parameter.reference_source or "").strip()


def catalogue_needs_review(item: TestCatalogItem) -> bool:
    if is_placeholder_specimen(item.specimen_type):
        return True
    if is_placeholder_container(item.container_type):
        return True
    if Decimal(str(item.price or 0)) <= 0:
        return True
    for parameter in item.parameters:
        if parameter_limits_need_source(parameter):
            return True
    return False


def recompute_validation_status(item: TestCatalogItem) -> str:
    item.validation_status = "needs_review" if catalogue_needs_review(item) else "validated"
    return item.validation_status
