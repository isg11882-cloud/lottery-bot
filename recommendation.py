# 이 파일은 lastjung/lotto 아이디어를 반영한 로또 번호 추천 엔진입니다.
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

import requests

LOTTO_API_URL = "https://www.dhlottery.co.kr/common.do"
DEFAULT_DRAW_COUNT = 180
FALLBACK_DATA_PATH = Path(__file__).resolve().parent / "data" / "korea_645_draws.json"


class DrawDataError(Exception):
    pass


def fetch_korea_645_draws(limit: int = DEFAULT_DRAW_COUNT) -> List[Dict]:
    try:
        latest = _get_latest_draw_no()
        start = max(1, latest - limit + 1)
        draws: List[Dict] = []

        for draw_no in range(start, latest + 1):
            draw = _fetch_draw(draw_no)
            if draw:
                draws.append(draw)

        if len(draws) >= 30:
            return draws
    except Exception:
        pass

    draws = _load_fallback_draws()
    if len(draws) < 30:
        raise DrawDataError(f"Not enough fallback draw data: {len(draws)}")
    return draws[-limit:]


def _get_latest_draw_no() -> int:
    from datetime import datetime

    lotto_start = datetime(2002, 12, 7)
    estimated = (datetime.now() - lotto_start).days // 7

    for draw_no in range(estimated + 3, max(estimated - 10, 1), -1):
        draw = _fetch_draw(draw_no)
        if draw:
            return int(draw["draw_no"])

    raise DrawDataError("Failed to determine latest draw number")


def _fetch_draw(draw_no: int) -> Dict | None:
    resp = requests.get(
        LOTTO_API_URL,
        params={"method": "getLottoNumber", "drwNo": draw_no},
        headers=_make_headers(),
        timeout=20,
    )
    resp.raise_for_status()
    try:
        data = resp.json()
    except Exception:
        return None

    if data.get("returnValue") != "success":
        return None

    return {
        "draw_no": int(data["drwNo"]),
        "draw_date": data["drwNoDate"],
        "numbers": sorted([
            int(data["drwtNo1"]),
            int(data["drwtNo2"]),
            int(data["drwtNo3"]),
            int(data["drwtNo4"]),
            int(data["drwtNo5"]),
            int(data["drwtNo6"]),
        ]),
        "bonus": int(data["bnusNo"]),
    }


def _make_headers() -> Dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "Referer": "https://www.dhlottery.co.kr/",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
    }


def _load_fallback_draws() -> List[Dict]:
    if not FALLBACK_DATA_PATH.exists():
        raise DrawDataError(f"Fallback draw file not found: {FALLBACK_DATA_PATH}")

    payload = json.loads(FALLBACK_DATA_PATH.read_text(encoding="utf-8"))
    draws = payload.get("draws", payload)
    return draws


def estimate_target_draw_no() -> int:
    from datetime import datetime

    lotto_start = datetime(2002, 12, 7)
    weeks_since_start = (datetime.now() - lotto_start).days // 7
    return weeks_since_start + 2


class PhysicsBiasModel:
    def __init__(self, draws: List[Dict], ball_count: int = 6, max_number: int = 45):
        self.draws = draws
        self.ball_count = ball_count
        self.max_number = max_number
        self.frequency_bias: Dict[int, float] = {}
        self.position_bias: defaultdict[int, Dict[int, float]] = defaultdict(dict)
        self.recent_hot: List[int] = []
        self.recent_cold: List[int] = []
        self._analyze()

    def _analyze(self):
        all_numbers: List[int] = []
        for draw in self.draws:
            all_numbers.extend(draw.get("numbers", []))

        counter = Counter(all_numbers)
        expected = len(self.draws) * self.ball_count / self.max_number
        for num in range(1, self.max_number + 1):
            count = counter.get(num, 0)
            self.frequency_bias[num] = count / expected if expected else 1.0

        for pos in range(self.ball_count):
            position_numbers = []
            for draw in self.draws:
                numbers = sorted(draw.get("numbers", []))
                if pos < len(numbers):
                    position_numbers.append(numbers[pos])
            position_counter = Counter(position_numbers)
            total = len(position_numbers)
            for num in range(1, self.max_number + 1):
                self.position_bias[pos][num] = position_counter.get(num, 0) / total if total else 0.0

        recent_draws = self.draws[-30:] if len(self.draws) >= 30 else self.draws
        recent_numbers: List[int] = []
        for draw in recent_draws:
            recent_numbers.extend(draw.get("numbers", []))
        recent_counter = Counter(recent_numbers)
        sorted_nums = sorted(range(1, self.max_number + 1), key=lambda x: recent_counter.get(x, 0), reverse=True)
        quarter = self.max_number // 4
        self.recent_hot = sorted_nums[:quarter]
        self.recent_cold = sorted_nums[-quarter:]

    def generate(self, count: int = 5, strategy: str = "balanced") -> List[List[int]]:
        results: List[List[int]] = []
        seen = set()
        attempts = 0
        max_attempts = count * 80

        while len(results) < count and attempts < max_attempts:
            attempts += 1
            if strategy == "frequency":
                numbers = self._generate_by_frequency()
            elif strategy == "position":
                numbers = self._generate_by_position()
            elif strategy == "hot":
                numbers = self._generate_hot_numbers()
            else:
                numbers = self._generate_balanced()

            numbers = sorted(numbers)
            key = tuple(numbers)
            if len(set(numbers)) == self.ball_count and key not in seen:
                seen.add(key)
                results.append(numbers)

        return results

    def _generate_by_frequency(self) -> List[int]:
        numbers = []
        available = list(range(1, self.max_number + 1))
        while len(numbers) < self.ball_count:
            weights = [self.frequency_bias.get(n, 1.0) if n in available else 0 for n in range(1, self.max_number + 1)]
            chosen = random.choices(range(1, self.max_number + 1), weights=weights, k=1)[0]
            if chosen in available:
                numbers.append(chosen)
                available.remove(chosen)
        return numbers

    def _generate_by_position(self) -> List[int]:
        numbers = []
        available = list(range(1, self.max_number + 1))
        for pos in range(self.ball_count):
            weights = [self.position_bias[pos].get(n, 0.01) if n in available else 0 for n in range(1, self.max_number + 1)]
            chosen = random.choices(range(1, self.max_number + 1), weights=weights, k=1)[0]
            if chosen in available:
                numbers.append(chosen)
                available.remove(chosen)
        return numbers

    def _generate_hot_numbers(self) -> List[int]:
        hot_count = min(self.ball_count - 1, len(self.recent_hot))
        hot_picks = random.sample(self.recent_hot, hot_count)
        remaining = [n for n in range(1, self.max_number + 1) if n not in hot_picks]
        other_picks = random.sample(remaining, self.ball_count - hot_count)
        return hot_picks + other_picks

    def _generate_balanced(self) -> List[int]:
        return random.choice([
            self._generate_by_frequency,
            self._generate_by_position,
            self._generate_hot_numbers,
        ])()


class ColdTheoryModel:
    def __init__(self, draws: List[Dict], ball_count: int = 6, max_number: int = 45):
        self.draws = draws
        self.ball_count = ball_count
        self.max_number = max_number
        self.overdue_counts: Dict[int, int] = {}
        self._analyze()

    def _analyze(self):
        total_draws = len(self.draws)
        last_appearance = {num: 0 for num in range(1, self.max_number + 1)}
        for idx, draw in enumerate(self.draws):
            for num in draw.get("numbers", []):
                last_appearance[num] = idx + 1
        for num in range(1, self.max_number + 1):
            self.overdue_counts[num] = total_draws - last_appearance[num] if last_appearance[num] else total_draws

    def generate(self, count: int = 5, strategy: str = "weighted") -> List[List[int]]:
        results: List[List[int]] = []
        seen = set()
        attempts = 0
        max_attempts = count * 80

        while len(results) < count and attempts < max_attempts:
            attempts += 1
            if strategy == "pure_cold":
                numbers = self._generate_pure_cold()
            elif strategy == "mixed":
                numbers = self._generate_mixed()
            else:
                numbers = self._generate_weighted()
            numbers = sorted(numbers)
            key = tuple(numbers)
            if len(set(numbers)) == self.ball_count and key not in seen:
                seen.add(key)
                results.append(numbers)
        return results

    def _generate_pure_cold(self) -> List[int]:
        sorted_nums = sorted(range(1, self.max_number + 1), key=lambda x: self.overdue_counts.get(x, 0), reverse=True)
        return random.sample(sorted_nums[: self.ball_count * 3], self.ball_count)

    def _generate_weighted(self) -> List[int]:
        numbers = []
        available = list(range(1, self.max_number + 1))
        while len(numbers) < self.ball_count:
            weights = [self.overdue_counts.get(n, 1) + 1 if n in available else 0 for n in range(1, self.max_number + 1)]
            chosen = random.choices(range(1, self.max_number + 1), weights=weights, k=1)[0]
            if chosen in available:
                numbers.append(chosen)
                available.remove(chosen)
        return numbers

    def _generate_mixed(self) -> List[int]:
        cold_count = self.ball_count // 2
        sorted_nums = sorted(range(1, self.max_number + 1), key=lambda x: self.overdue_counts.get(x, 0), reverse=True)
        cold_picks = random.sample(sorted_nums[: cold_count * 3], cold_count)
        remaining = [n for n in range(1, self.max_number + 1) if n not in cold_picks]
        random_picks = random.sample(remaining, self.ball_count - cold_count)
        return cold_picks + random_picks


class BalancedMixModel:
    def __init__(self, draws: List[Dict], ball_count: int = 6, max_number: int = 45):
        self.draws = draws
        self.ball_count = ball_count
        self.max_number = max_number
        self.ideal_sum = (1 + self.max_number) / 2 * self.ball_count
        self.midpoint = max_number // 2

    def generate(self, count: int = 5, tolerance: float = 0.15) -> List[List[int]]:
        results: List[List[int]] = []
        seen = set()
        max_attempts = count * 120
        attempts = 0
        min_sum = int(self.ideal_sum * (1 - tolerance))
        max_sum = int(self.ideal_sum * (1 + tolerance))

        while len(results) < count and attempts < max_attempts:
            attempts += 1
            numbers = sorted(self._generate_balanced())
            key = tuple(numbers)
            if key in seen or len(set(numbers)) != self.ball_count:
                continue
            total = sum(numbers)
            odd_count = sum(1 for n in numbers if n % 2 == 1)
            low_count = sum(1 for n in numbers if n <= self.midpoint)
            if not (min_sum <= total <= max_sum):
                continue
            if abs(odd_count - (self.ball_count // 2)) > 1:
                continue
            if abs(low_count - (self.ball_count // 2)) > 1:
                continue
            seen.add(key)
            results.append(numbers)
        return results

    def _generate_balanced(self) -> List[int]:
        low_count = self.ball_count // 2
        high_count = self.ball_count - low_count
        low_range = list(range(1, self.midpoint + 1))
        high_range = list(range(self.midpoint + 1, self.max_number + 1))
        numbers = random.sample(low_range, low_count) + random.sample(high_range, high_count)
        while len(numbers) < self.ball_count:
            remaining = [n for n in range(1, self.max_number + 1) if n not in numbers]
            numbers.append(random.choice(remaining))
        return numbers


def recommend_lotto_numbers(count: int = 1, strategy: str = "balanced_mix") -> Dict:
    draws = fetch_korea_645_draws()
    latest_draw_no = draws[-1]["draw_no"]
    estimated_target_draw_no = estimate_target_draw_no()

    if strategy == "physics_bias":
        model = PhysicsBiasModel(draws)
        numbers = model.generate(count=count, strategy="balanced")
    elif strategy == "cold_theory":
        model = ColdTheoryModel(draws)
        numbers = model.generate(count=count, strategy="weighted")
    elif strategy == "hybrid":
        physics = PhysicsBiasModel(draws).generate(count=max(count * 2, 3), strategy="balanced")
        cold = ColdTheoryModel(draws).generate(count=max(count * 2, 3), strategy="weighted")
        balanced = BalancedMixModel(draws).generate(count=max(count * 2, 3))
        pool = physics + cold + balanced
        deduped = []
        seen = set()
        for nums in pool:
            key = tuple(nums)
            if key not in seen:
                seen.add(key)
                deduped.append(nums)
        numbers = deduped[:count]
    else:
        model = BalancedMixModel(draws)
        numbers = model.generate(count=count)

    if len(numbers) < count:
        raise DrawDataError(f"Failed to generate enough recommendation sets: {len(numbers)}/{count}")

    return {
        "strategy": strategy,
        "source": "lastjung/lotto-inspired",
        "latest_draw_no": latest_draw_no,
        "target_draw_no": estimated_target_draw_no,
        "numbers": numbers,
        "used_fallback_data": latest_draw_no < estimated_target_draw_no - 2,
    }
