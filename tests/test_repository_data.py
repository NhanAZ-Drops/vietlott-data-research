import csv
import json
from datetime import date

from vietlott_collector.models import DrawRecord, PrizeRecord
from vietlott_collector.repository_data import (
    hydrate_repository_data,
    publish_repository_data,
    validate_repository_data,
)
from vietlott_collector.storage import SqliteDatasetStore


def test_publish_and_hydrate_partitioned_dataset(tmp_path) -> None:
    data_dir = tmp_path / "data"
    dataset_dir = tmp_path / "datasets"
    weather_dir = dataset_dir / "weather"
    weather_dir.mkdir(parents=True)
    (weather_dir / "daily.csv").write_text("date,temp\n2026-06-01,30\n", encoding="utf-8")
    store = SqliteDatasetStore(data_dir)
    try:
        store.upsert(
            [
                _draw("keno", "0000001", date(2026, 5, 31)),
                _draw("keno", "0000002", date(2026, 6, 1)),
                _draw("mega645", "00001", date(2026, 6, 1)),
            ],
            [_prize()],
        )
        store.export_csv()
    finally:
        store.close()

    report = publish_repository_data(data_dir, dataset_dir)

    assert report["valid"] is True
    assert report["draw_rows"] == 3
    assert (dataset_dir / "draws" / "keno" / "2026-05.csv").exists()
    assert (dataset_dir / "draws" / "keno" / "2026-06.csv").exists()
    assert (dataset_dir / "draws" / "mega645" / "all.csv").exists()
    assert (dataset_dir / "weather" / "daily.csv").exists()
    quality_path = dataset_dir / "metadata" / "quality-report.json"
    snapshot_path = dataset_dir / "metadata" / "snapshot-manifest.json"
    assert quality_path.exists()
    assert snapshot_path.exists()
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    assert quality["totals"]["draw_rows"] == 3
    assert quality["products"]["keno"]["result_coverage"]["rate"] == 1.0
    manifest = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert manifest["dataset_rows"] == {"draws": 3, "prizes": 1}
    assert "weather/daily.csv" in manifest["files"]
    (dataset_dir / "weather" / "daily.csv").write_bytes(b"date,temp\r\n2026-06-01,30\r\n")
    assert validate_repository_data(dataset_dir)["valid"] is True

    hydrated = tmp_path / "hydrated"
    counts = hydrate_repository_data(dataset_dir, hydrated)
    assert counts == {"draw_rows": 3, "prize_rows": 1}

    with (hydrated / "draws.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert {(row["product"], row["draw_id"]) for row in rows} == {
        ("keno", "0000001"),
        ("keno", "0000002"),
        ("mega645", "00001"),
    }
    assert validate_repository_data(dataset_dir)["valid"] is True


def test_reconcile_unchanged_official_row_is_stable(tmp_path) -> None:
    store = SqliteDatasetStore(tmp_path)
    try:
        record = _draw("mega645", "00001", date(2026, 6, 1))
        record.attributes["data_source"] = "official_vietlott"
        store.upsert([record], [])
        before = store.load_draws().iloc[0].to_dict()

        report = store.reconcile_official_draws([record])
        after = store.load_draws().iloc[0].to_dict()

        assert report["changed"] == 0
        assert before == after
    finally:
        store.close()


def test_reconcile_preserves_previous_source_observation(tmp_path) -> None:
    store = SqliteDatasetStore(tmp_path)
    try:
        record = _draw("mega645", "00001", date(2026, 6, 1))
        record.attributes.update(
            {
                "data_source": "community_mirror",
                "secondary_source_url": "https://example.test/mirror",
            }
        )
        store.upsert([record], [])
        official = _draw("mega645", "00001", date(2026, 6, 1))
        official.attributes["data_source"] = "official_vietlott"

        store.reconcile_official_draws([official])

        row = store.load_draws().iloc[0]
        attributes = json.loads(row["attributes_json"])
        assert attributes["data_source"] == "official_vietlott"
        assert attributes["source_history"] == [
            {
                "data_source": "community_mirror",
                "draw_date": "2026-06-01",
                "observed_at": record.fetched_at,
                "result_json": record.to_row()["result_json"],
                "source_url": record.source_url,
            }
        ]
        assert "secondary_source_url" not in attributes
    finally:
        store.close()


def _draw(product: str, draw_id: str, draw_date: date) -> DrawRecord:
    result = (
        {"numbers": list(range(1, 21))}
        if product == "keno"
        else {"numbers": [1, 2, 3, 4, 5, 6], "special_numbers": []}
    )
    return DrawRecord(
        product=product,
        draw_id=draw_id,
        draw_date=draw_date,
        result=result,
        source_url=f"https://vietlott.vn/example?id={draw_id}",
        prize_status="rules_available" if product == "keno" else "complete",
        validation_status="valid",
    )


def _prize() -> PrizeRecord:
    return PrizeRecord(
        product="mega645",
        draw_id="00001",
        game_variant="Mega 6/45",
        prize_tier="Jackpot",
        winning_rule="6 numbers",
        winner_count=0,
        prize_value_vnd=12_000_000_000,
        details={},
        source_url="https://vietlott.vn/example?id=00001",
    )
