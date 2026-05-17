# 이 파일은 네이버 검색 결과를 이용해 최신 로또 회차 데이터를 보강합니다.
import json
import re
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


def update_latest_draw() -> dict:
    payload = load_data()
    draws = payload.get("draws", [])
    if not draws:
        raise RefreshError("No draws found in local data file")

    latest_local = int(draws[-1]["draw_no"])
    latest_expected = estimate_latest_draw_no()

    updated = []
    skipped_missing_draws = max(0, latest_expected - latest_local - 1)
    if latest_local < latest_expected:
        html = fetch_naver_search_html(latest_expected)
        draw = parse_draw_from_html(latest_expected, html)
        draws.append(draw)
        updated.append(draw)
        payload["draws"] = draws
        save_data(payload)

    return {
        "latest_local_before": latest_local,
        "latest_expected": latest_expected,
        "updated_count": len(updated),
        "updated_draws": updated,
        "skipped_missing_draws": skipped_missing_draws,
        "latest_local_after": int(payload.get("draws", draws)[-1]["draw_no"]),
    }


if __name__ == "__main__":
    result = update_latest_draw()
    print(json.dumps(result, ensure_ascii=False))
