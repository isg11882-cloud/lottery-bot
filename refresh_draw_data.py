# 이 파일은 네이버 검색 결과를 이용해 최신 로또 회차 데이터를 보강합니다.
import json
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

DATA_PATH = Path(__file__).resolve().parent / "data" / "korea_645_draws.json"
NAVER_SEARCH_URL = "https://search.naver.com/search.naver"
FIRST_DRAW_DATE = date(2002, 12, 7)


class RefreshError(Exception):
    pass


def estimate_latest_draw_no(today: date | None = None) -> int:
    today = today or datetime.now().date()
    days_since_first = (today - FIRST_DRAW_DATE).days
    weeks_since_first = days_since_first // 7
    # 토요일 추첨 완료 이후 일요일~금요일은 직전 토요일 회차가 최신
    return weeks_since_first + 1


def estimate_draw_date(draw_no: int) -> str:
    return (FIRST_DRAW_DATE + timedelta(weeks=draw_no - 1)).isoformat()


def load_data() -> dict:
    if not DATA_PATH.exists():
        raise RefreshError(f"Data file not found: {DATA_PATH}")
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def save_data(payload: dict) -> None:
    payload["updated_at"] = datetime.now().isoformat()
    payload["total_draws"] = len(payload.get("draws", []))
    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_naver_search_html(draw_no: int) -> str:
    params = {"query": f"{draw_no}회 로또 당첨번호"}
    resp = requests.get(
        NAVER_SEARCH_URL,
        params=params,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.text


def parse_draw_from_html(draw_no: int, html: str) -> dict:
    patterns = [
        rf"{draw_no}회[^\n\r]*?당첨[^\n\r]*?['‘\"]?(\d{{1,2}})[·,]\s*(\d{{1,2}})[·,]\s*(\d{{1,2}})[·,]\s*(\d{{1,2}})[·,]\s*(\d{{1,2}})[·,]\s*(\d{{1,2}})['’\"]?.{{0,80}}?보너스[^\d]*(\d{{1,2}})",
        rf"{draw_no}회[^\n\r]*?당첨번호[^\n\r]*?(\d{{1,2}})\s+(\d{{1,2}})\s+(\d{{1,2}})\s+(\d{{1,2}})\s+(\d{{1,2}})\s+(\d{{1,2}})\s*\+\s*(\d{{1,2}})",
    ]
    for pattern in patterns:
        m = re.search(pattern, html, flags=re.IGNORECASE)
        if m:
            vals = [int(x) for x in m.groups()]
            return {
                "draw_no": draw_no,
                "draw_date": estimate_draw_date(draw_no),
                "numbers": sorted(vals[:6]),
                "bonus": vals[6],
                "total_sell_amount": None,
                "first_prize_amount": None,
                "first_prize_winners": None,
                "source": "naver-search",
            }
    raise RefreshError(f"Could not parse draw {draw_no} from Naver search results")


def _normalize_draws(draws: list[dict]) -> list[dict]:
    deduped = {int(draw["draw_no"]): draw for draw in draws}
    return [deduped[draw_no] for draw_no in sorted(deduped)]


def backfill_missing_draws(start_draw_no: int | None = None, end_draw_no: int | None = None, pause_seconds: float = 0.25) -> dict:
    payload = load_data()
    draws = payload.get("draws", [])
    if not draws:
        raise RefreshError("No draws found in local data file")

    latest_expected = estimate_latest_draw_no()
    existing = {int(draw["draw_no"]) for draw in draws}
    start_draw_no = start_draw_no or int(draws[0]["draw_no"])
    end_draw_no = end_draw_no or latest_expected

    missing_draws = [draw_no for draw_no in range(start_draw_no, end_draw_no + 1) if draw_no not in existing]
    added = []
    failed = []

    for draw_no in missing_draws:
        try:
            html = fetch_naver_search_html(draw_no)
            draw = parse_draw_from_html(draw_no, html)
            draws.append(draw)
            added.append(draw)
            if pause_seconds > 0:
                time.sleep(pause_seconds)
        except Exception as exc:
            failed.append({"draw_no": draw_no, "error": str(exc)})

    payload["draws"] = _normalize_draws(draws)
    save_data(payload)

    return {
        "requested_range": [start_draw_no, end_draw_no],
        "missing_before": missing_draws,
        "added_count": len(added),
        "added_draws": added,
        "failed": failed,
        "latest_local_after": int(payload["draws"][-1]["draw_no"]),
    }


def update_latest_draw() -> dict:
    payload = load_data()
    draws = payload.get("draws", [])
    if not draws:
        raise RefreshError("No draws found in local data file")

    latest_local = int(draws[-1]["draw_no"])
    latest_expected = estimate_latest_draw_no()
    result = backfill_missing_draws(start_draw_no=latest_local + 1, end_draw_no=latest_expected)

    return {
        "latest_local_before": latest_local,
        "latest_expected": latest_expected,
        "updated_count": result["added_count"],
        "updated_draws": result["added_draws"],
        "failed": result["failed"],
        "latest_local_after": result["latest_local_after"],
    }


if __name__ == "__main__":
    result = backfill_missing_draws()
    print(json.dumps(result, ensure_ascii=False))
