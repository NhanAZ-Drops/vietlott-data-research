import requests

from vietlott_collector.config import PRODUCT_SPECS
from vietlott_collector.sources.vietlott import AjaxContext, OfficialVietlottSource


def test_matrix_payload_uses_discovered_key() -> None:
    payload = OfficialVietlottSource._payload(
        PRODUCT_SPECS["mega645"],
        3,
        AjaxContext(first_page_html="", dynamic_key="e5d3a96f"),
    )

    assert payload["Key"] == "e5d3a96f"
    assert payload["PageIndex"] == 3
    assert len(payload["ArrayNumbers"]) == 6


def test_keno_payload_uses_current_total_rows() -> None:
    payload = OfficialVietlottSource._payload(
        PRODUCT_SPECS["keno"],
        4,
        AjaxContext(first_page_html="", total_rows=38_429),
    )

    assert payload["GameId"] == "6"
    assert payload["TotalRow"] == 38_429
    assert payload["PageIndex"] == 4


def test_max4d_payload_uses_historical_game_id() -> None:
    payload = OfficialVietlottSource._payload(
        PRODUCT_SPECS["max4d"],
        2,
        AjaxContext(first_page_html=""),
    )

    assert payload["GameId"] == "2"
    assert payload["number"] == "1234"
    assert payload["PageIndex"] == 2


def test_bootstrap_falls_back_to_ajax_when_list_page_is_blocked() -> None:
    source = OfficialVietlottSource(_BlockedClient())

    context = source.bootstrap(PRODUCT_SPECS["keno"])

    assert context.ajax_only is True
    assert context.first_page_html == ""
    assert context.total_rows == 10_000_000


def test_matrix_ajax_fallback_accepts_an_empty_dynamic_key() -> None:
    payload = OfficialVietlottSource._payload(
        PRODUCT_SPECS["mega645"],
        0,
        AjaxContext(first_page_html="", dynamic_key="", ajax_only=True),
    )

    assert payload["Key"] == ""
    assert payload["PageIndex"] == 0


class _BlockedClient:
    def get_text(self, _url: str) -> str:
        response = requests.Response()
        response.status_code = 403
        raise requests.HTTPError("blocked", response=response)
