from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import requests

from ..config import AjaxKind, ProductSpec
from ..http import HttpClient
from ..models import DetailResult, DrawRecord
from ..parsers import parse_detail_page, parse_list_page

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AjaxContext:
    first_page_html: str
    dynamic_key: str | None = None
    total_rows: int = 0
    ajax_only: bool = False


class OfficialVietlottSource:
    def __init__(self, client: HttpClient) -> None:
        self.client = client

    def bootstrap(self, spec: ProductSpec) -> AjaxContext:
        try:
            html = self.client.get_text(spec.list_url)
        except requests.RequestException as exc:
            LOGGER.warning(
                "%s list page is unavailable, using the official AjaxPro endpoint: %s",
                spec.slug,
                exc,
            )
            return self._ajax_only_context()
        if _is_cloudflare_challenge(html):
            LOGGER.warning(
                "%s list page returned a Cloudflare challenge, using the official "
                "AjaxPro endpoint",
                spec.slug,
            )
            return self._ajax_only_context()
        key_match = re.search(
            r"ServerSideDrawResult\s*\(\s*RenderInfo\s*,\s*'([0-9a-fA-F]+)'",
            html,
        )
        total_rows = [int(value) for value in re.findall(r"TotalRow\s*=\s*(\d+)", html)]
        return AjaxContext(
            first_page_html=html,
            dynamic_key=key_match.group(1) if key_match else None,
            total_rows=total_rows[-1] if total_rows else 0,
        )

    @staticmethod
    def _ajax_only_context() -> AjaxContext:
        return AjaxContext(
            first_page_html="",
            dynamic_key="",
            total_rows=10_000_000,
            ajax_only=True,
        )

    def fetch_page(
        self,
        spec: ProductSpec,
        page_index: int,
        context: AjaxContext,
    ) -> list[DrawRecord]:
        if page_index == 0 and not context.ajax_only:
            html = context.first_page_html
        else:
            payload = self._payload(spec, page_index, context)
            response = self.client.post_json(
                spec.ajax_url,
                body=payload,
                headers={
                    "Accept": "*/*",
                    "Content-Type": "text/plain; charset=utf-8",
                    "Origin": "https://vietlott.vn",
                    "Referer": spec.list_url,
                    "X-AjaxPro-Method": "ServerSideDrawResult",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
            html = self._response_html(response)
        records = parse_list_page(spec, html)
        if not records and re.search(r"[?&]id=\d+", html):
            raise RuntimeError(
                f"The {spec.slug} page contains draw links but no records were parsed; "
                "the official HTML structure may have changed"
            )
        if page_index == 0 and not records:
            raise RuntimeError(f"No current draw records were found for {spec.slug}")
        return records

    def fetch_detail(self, spec: ProductSpec, record: DrawRecord) -> DetailResult:
        html = self.client.get_text(record.source_url)
        return parse_detail_page(spec, record.draw_id, record.source_url, html)

    @staticmethod
    def _response_html(response: dict[str, Any]) -> str:
        value = response.get("value")
        html = value.get("HtmlContent") if isinstance(value, dict) else value
        if not isinstance(html, str):
            raise RuntimeError("AjaxPro response does not contain value.HtmlContent")
        return html

    @staticmethod
    def _payload(
        spec: ProductSpec,
        page_index: int,
        context: AjaxContext,
    ) -> dict[str, Any]:
        render_info = {
            "SiteId": "main.frontend.vi",
            "SiteAlias": "main.vi",
            "UserSessionId": "",
            "SiteLang": "vi",
            "IsPageDesign": False,
            "ExtraParam1": "",
            "ExtraParam2": "",
            "ExtraParam3": "",
            "SiteURL": "",
            "WebPage": None,
            "SiteName": "Vietlott",
            "OrgPageAlias": None,
            "PageAlias": None,
            "RefKey": None,
            "FullPageAlias": None,
            "System": 1,
        }
        if spec.ajax_kind is AjaxKind.MATRIX:
            return {
                "ORenderInfo": render_info,
                "Key": context.dynamic_key or "",
                "GameDrawId": "",
                "ArrayNumbers": [
                    ["" for _ in range(spec.array_columns or 18)] for _ in range(spec.array_rows or 5)
                ],
                "CheckMulti": False,
                "PageIndex": page_index,
            }
        if spec.ajax_kind is AjaxKind.THREE_DIGIT:
            payload = {
                "ORenderInfo": render_info,
                "GameId": spec.game_id,
                "GameDrawId": "",
                "number01": "123",
                "number02": "321",
                "PageIndex": page_index,
            }
            if spec.slug == "max3d":
                payload["CheckMulti"] = 0
            return payload
        if spec.ajax_kind is AjaxKind.FOUR_DIGIT:
            return {
                "ORenderInfo": render_info,
                "GameId": spec.game_id,
                "GameDrawId": "",
                "number": "1234",
                "CheckMulti": 0,
                "PageIndex": page_index,
            }
        if spec.ajax_kind is AjaxKind.KENO:
            return {
                "ORenderInfo": render_info,
                "GameId": spec.game_id,
                "GameDrawNo": "",
                "number": "",
                "DrawDate": "",
                "ProcessType": 0,
                "OddEven": 2,
                "UpperLower": 2,
                "PageIndex": page_index,
                "TotalRow": context.total_rows,
            }
        if spec.ajax_kind is AjaxKind.BINGO:
            return {
                "ORenderInfo": render_info,
                "GameId": spec.game_id,
                "GameDrawNo": "",
                "number": "",
                "DrawDate": "",
                "PageIndex": page_index,
                "TotalRow": context.total_rows,
            }
        raise ValueError(f"Unsupported Ajax kind: {spec.ajax_kind}")


def _is_cloudflare_challenge(html: str) -> bool:
    lowered = html.lower()
    return "just a moment" in lowered or "cf-chl-" in lowered
