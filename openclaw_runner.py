import os
import sys
import traceback
from dotenv import load_dotenv, dotenv_values
import controller


def validate_env() -> list[str]:
    env_path = os.path.join(os.getcwd(), ".env")
    env_values = dotenv_values(env_path) if os.path.exists(env_path) else {}
    lotto_mode = str(env_values.get("LOTTO_MODE") or "AUTO").strip().upper()

    required = ["USERNAME", "PASSWORD"]
    if lotto_mode != "MANUAL":
        required.append("COUNT")

    missing = []
    for key in required:
        value = env_values.get(key)
        if not value or str(value).startswith("YOUR"):
            missing.append(key)

    if lotto_mode == "MANUAL":
        lotto_numbers = env_values.get("LOTTO_NUMBERS")
        if not lotto_numbers or str(lotto_numbers).startswith("YOUR"):
            missing.append("LOTTO_NUMBERS")

    return missing


def main() -> int:
    load_dotenv(override=False)

    if len(sys.argv) < 2 or sys.argv[1] not in {"buy", "check", "buy_lotto", "buy_win720", "check_lotto", "check_win720"}:
        print("Usage: python openclaw_runner.py [buy|check|buy_lotto|buy_win720|check_lotto|check_win720]")
        return 2

    missing = validate_env()
    if missing:
        print(f"ENV_MISSING: {', '.join(missing)}")
        return 2

    action = sys.argv[1]
    print(f"[lottery-bot] start: {action}")

    try:
        if action == "buy":
            controller.buy()
        elif action == "check":
            controller.check()
        elif action == "buy_lotto":
            controller.lotto_buy()
        elif action == "buy_win720":
            controller.win720_buy()
        elif action == "check_lotto":
            controller.lotto_check()
        elif action == "check_win720":
            controller.win720_check()

        print(f"[lottery-bot] done: {action}")
        return 0
    except Exception as exc:
        print(f"[lottery-bot] failed: {action}: {exc}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
