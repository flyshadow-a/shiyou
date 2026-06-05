# client_api/remote_strategy_service.py
from __future__ import annotations

from typing import Any

from client_api.api_client import ApiClient


class RemoteSpecialStrategyResultService:
    def __init__(self, api: ApiClient | None = None):
        self.api = api or ApiClient()

    def load_result_bundle(
        self,
        facility_code: str,
        run_id: int | None = None,
    ) -> dict[str, Any] | None:
        try:
            return self.api.get_strategy_result(facility_code, run_id)
        except Exception as exc:
            print("[RemoteSpecialStrategyResultService] load_result_bundle failed:", exc)
            return None