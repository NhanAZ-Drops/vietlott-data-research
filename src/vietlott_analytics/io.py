from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from .catalog import AnalysisKind, AnalyticsProduct


@dataclass(frozen=True, slots=True)
class Observation:
    draw_id: str
    draw_date: date
    values: tuple[int, ...] = ()
    special_values: tuple[int, ...] = ()
    outcomes: tuple[str, ...] = ()

    @property
    def ordering_key(self) -> tuple[date, int | str]:
        numeric_id: int | str = int(self.draw_id) if self.draw_id.isdigit() else self.draw_id
        return self.draw_date, numeric_id


@dataclass(slots=True)
class ProductDataset:
    product: AnalyticsProduct
    observations: list[Observation] = field(default_factory=list)
    source_counts: Counter[str] = field(default_factory=Counter)
    data_source_counts: Counter[str] = field(default_factory=Counter)
    status_counts: Counter[str] = field(default_factory=Counter)
    validation_counts: Counter[str] = field(default_factory=Counter)
    latest_fetched_at: str = ""
    jackpot_values: list[tuple[str, int]] = field(default_factory=list)

    @property
    def latest(self) -> Observation:
        if not self.observations:
            raise ValueError(f"No confirmed observations for {self.product.slug}")
        return self.observations[-1]

    @property
    def fingerprint(self) -> str:
        latest = self.latest
        if self.product.kind is AnalysisKind.NUMBER_SET:
            payload = ",".join(str(value) for value in latest.values)
            special = ",".join(str(value) for value in latest.special_values)
        else:
            payload = ",".join(latest.outcomes)
            special = ""
        return f"{self.product.slug}|{latest.draw_id}|{latest.draw_date}|{payload}|{special}"


def load_product_dataset(root: Path, product: AnalyticsProduct) -> ProductDataset:
    dataset = ProductDataset(product=product)
    paths = sorted((root / "draws" / product.slug).glob("*.csv"))
    if not paths:
        raise FileNotFoundError(f"No draw partitions found for {product.slug}")

    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                status = row.get("draw_status", "confirmed") or "confirmed"
                dataset.status_counts[status] += 1
                dataset.validation_counts[row.get("validation_status", "unchecked")] += 1
                dataset.latest_fetched_at = max(
                    dataset.latest_fetched_at,
                    row.get("fetched_at", ""),
                )
                source_host = urlparse(row.get("source_url", "")).netloc or "unknown"
                dataset.source_counts[source_host] += 1
                if status != "confirmed":
                    continue

                result = json.loads(row["result_json"])
                attributes = json.loads(row.get("attributes_json") or "{}")
                observation = _to_observation(product, row, result)
                dataset.observations.append(observation)
                dataset.data_source_counts[str(attributes.get("data_source", "unknown"))] += 1
                jackpots = attributes.get("jackpots_vnd")
                if isinstance(jackpots, dict):
                    for value in jackpots.values():
                        if isinstance(value, int):
                            dataset.jackpot_values.append((observation.draw_id, value))

    dataset.observations.sort(key=lambda item: item.ordering_key)
    return dataset


def load_prize_summary(root: Path, product: AnalyticsProduct) -> dict[str, object]:
    path = root / "prizes" / product.slug / "all.csv"
    if not path.exists():
        return {
            "rows": 0,
            "draws_with_prizes": 0,
            "reported_winners": 0,
            "estimated_payout_vnd": 0,
            "largest_prize_value_vnd": None,
            "largest_prize_draw_id": None,
        }

    rows = 0
    draw_ids: set[str] = set()
    reported_winners = 0
    estimated_payout = 0
    largest_value: int | None = None
    largest_draw_id: str | None = None
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            rows += 1
            draw_ids.add(row["draw_id"])
            winner_count = _optional_int(row.get("winner_count"))
            prize_value = _optional_int(row.get("prize_value_vnd"))
            if winner_count is not None:
                reported_winners += winner_count
            if winner_count is not None and prize_value is not None:
                estimated_payout += winner_count * prize_value
            if prize_value is not None and (largest_value is None or prize_value > largest_value):
                largest_value = prize_value
                largest_draw_id = row["draw_id"]

    return {
        "rows": rows,
        "draws_with_prizes": len(draw_ids),
        "reported_winners": reported_winners,
        "estimated_payout_vnd": estimated_payout,
        "largest_prize_value_vnd": largest_value,
        "largest_prize_draw_id": largest_draw_id,
    }


def _to_observation(
    product: AnalyticsProduct,
    row: dict[str, str],
    result: dict[str, object],
) -> Observation:
    common = {
        "draw_id": row["draw_id"],
        "draw_date": date.fromisoformat(row["draw_date"]),
    }
    if product.kind is AnalysisKind.NUMBER_SET:
        numbers = tuple(int(value) for value in result.get("numbers", []))
        special = tuple(int(value) for value in result.get("special_numbers", []))
        return Observation(**common, values=numbers, special_values=special)

    if product.slug == "bingo18":
        digits = result.get("digits", [])
        outcome = "".join(str(int(value)) for value in digits)
        return Observation(**common, outcomes=(outcome,))

    tiers = result.get("tiers")
    outcomes: list[str] = []
    if isinstance(tiers, dict):
        for values in tiers.values():
            if not isinstance(values, list):
                continue
            for value in values:
                text = str(value)
                if text.isdigit() and len(text) == product.sequence_length:
                    outcomes.append(text)
    return Observation(**common, outcomes=tuple(outcomes))


def _optional_int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    try:
        return int(value)
    except ValueError:
        return None
