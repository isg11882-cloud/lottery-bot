import os
import re
import sys
from dotenv import load_dotenv

import auth
import lotto645
import win720
import notification
import recommendation
import refresh_draw_data
import time


def _setup_and_login():
    load_dotenv(override=False)
    username = os.environ.get('USERNAME')
    password = os.environ.get('PASSWORD')
    slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
    if slack_webhook_url and slack_webhook_url.startswith("YOUR_"):
        slack_webhook_url = None

    discord_webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    if discord_webhook_url and discord_webhook_url.startswith("YOUR_"):
        discord_webhook_url = None

    telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if telegram_bot_token and telegram_bot_token.startswith("YOUR_"):
        telegram_bot_token = None

    if slack_webhook_url:
        webhook_url = slack_webhook_url
    else:
        webhook_url = discord_webhook_url

    auth_ctrl = auth.AuthController()
    auth_ctrl.login(username, password)

    return auth_ctrl, username, webhook_url

def parse_manual_lotto_numbers(raw: str | None) -> list[list[int]]:
    if not raw:
        return []

    normalized = raw.strip()
    if not normalized:
        return []

    chunks = [chunk.strip() for chunk in re.split(r"\s*[|;\n]+\s*", normalized) if chunk.strip()]
    games: list[list[int]] = []

    for chunk in chunks:
        if ":" in chunk:
            chunk = chunk.split(":", 1)[1].strip()

        nums = [part.strip() for part in chunk.split(",") if part.strip()]
        if len(nums) != 6:
            raise ValueError(f"Each manual game must contain exactly 6 numbers: {chunk}")

        try:
            game = [int(num) for num in nums]
        except ValueError as exc:
            raise ValueError(f"Manual numbers must be integers only: {chunk}") from exc

        if any(num < 1 or num > 45 for num in game):
            raise ValueError(f"Manual numbers must be between 1 and 45: {chunk}")
        if len(set(game)) != 6:
            raise ValueError(f"Manual numbers cannot contain duplicates: {chunk}")

        games.append(sorted(game))

    if not 1 <= len(games) <= 5:
        raise ValueError("LOTTO_NUMBERS must contain between 1 and 5 games.")

    return games


def resolve_lotto_purchase_mode() -> tuple[str, int, list[list[int]], dict | None]:
    load_dotenv(override=False)
    lotto_mode = (os.environ.get('LOTTO_MODE') or 'AUTO').strip().upper()
    manual_numbers = parse_manual_lotto_numbers(os.environ.get('LOTTO_NUMBERS'))
    recommendation_strategy = (os.environ.get('LOTTO_STRATEGY') or 'balanced_mix').strip().lower()

    if lotto_mode == 'MANUAL':
        if not manual_numbers:
            raise ValueError('LOTTO_MODE=MANUAL requires LOTTO_NUMBERS to be set.')
        return lotto_mode, len(manual_numbers), manual_numbers, None

    count = int(os.environ.get('COUNT'))
    if manual_numbers:
        return 'MANUAL', len(manual_numbers), manual_numbers, None

    if lotto_mode in {'RECOMMENDED', 'SMART', 'AI'}:
        try:
            refresh_draw_data.update_latest_draw()
        except Exception as exc:
            print(f"[Warning] draw refresh skipped: {exc}")
        rec = recommendation.recommend_lotto_numbers(count=count, strategy=recommendation_strategy)
        return 'MANUAL', len(rec['numbers']), rec['numbers'], rec

    return lotto_mode, count, [], None


def get_charge_config() -> tuple[int, int, bool]:
    threshold = int(os.environ.get('LOW_BALANCE_THRESHOLD') or '3000')
    charge_amount = int(os.environ.get('CHARGE_AMOUNT') or '10000')
    auto_charge_guide = (os.environ.get('AUTO_CHARGE_GUIDE') or 'true').strip().lower() in {'1', 'true', 'yes', 'y', 'on'}
    return threshold, charge_amount, auto_charge_guide


def send_charge_guide(auth_ctrl: auth.AuthController, webhook_url: str | None, reason: str, required_amount: int, threshold: int, charge_amount: int) -> dict:
    charge_guide = auth_ctrl.assign_virtual_account(charge_amount)
    body = {
        'reason': reason,
        'required_amount': required_amount,
        'threshold': threshold,
        'balance': auth_ctrl.get_user_balance(),
        'charge_guide': charge_guide,
    }

    if webhook_url:
        notification.Notification().send_charge_guide_message(body, webhook_url)
    else:
        print('[Info] Webhook URL not configured. Skip charge guide notification send.')
        print(body)

    return body


def ensure_balance(auth_ctrl: auth.AuthController, webhook_url: str | None, reason: str, required_amount: int):
    threshold, charge_amount, auto_charge_guide = get_charge_config()
    balance_amount = auth_ctrl.get_user_balance_amount()
    min_required = max(required_amount, threshold)

    if balance_amount < required_amount:
        charge_info = send_charge_guide(auth_ctrl, webhook_url, reason, required_amount, threshold, charge_amount)
        raise RuntimeError(
            f"잔액 부족: 현재 {balance_amount:,}원 / 필요 {required_amount:,}원. 충전 안내를 발급했습니다. 계좌: [{charge_info['charge_guide']['bank_name']}] {charge_info['charge_guide']['account_number']}"
        )

    if auto_charge_guide and balance_amount <= min_required:
        send_charge_guide(auth_ctrl, webhook_url, f'{reason} 후 잔액 부족 대비', required_amount, threshold, charge_amount)


def buy_lotto645(authCtrl: auth.AuthController, cnt: int, mode: str, manual_numbers: list[list[int]] | None = None):
    lotto = lotto645.Lotto645()
    _mode = lotto645.Lotto645Mode[mode.upper()]

    if manual_numbers:
        response = lotto.buy_lotto645(authCtrl, cnt, _mode, manual_numbers)
    else:
        response = lotto.buy_lotto645(authCtrl, cnt, _mode)

    response['balance'] = authCtrl.get_user_balance()
    return response

def check_winning_lotto645(authCtrl: auth.AuthController) -> dict:
    lotto = lotto645.Lotto645()
    item = lotto.check_winning(authCtrl)
    item['balance'] = authCtrl.get_user_balance()
    return item

def buy_win720(authCtrl: auth.AuthController, username: str):
    pension = win720.Win720()
    response = pension.buy_Win720(authCtrl, username)
    response['balance'] = authCtrl.get_user_balance()
    return response

def check_winning_win720(authCtrl: auth.AuthController) -> dict:
    pension = win720.Win720()
    item = pension.check_winning(authCtrl)
    item['balance'] = authCtrl.get_user_balance()
    return item

def send_message(mode: int, lottery_type: int, response: dict, webhook_url: str | None):
    if not webhook_url:
        print("[Info] Webhook URL not configured. Skip notification send.")
        print(response)
        return

    notify = notification.Notification()

    if mode == 0:
        if lottery_type == 0:
            notify.send_lotto_winning_message(response, webhook_url)
        else:
            notify.send_win720_winning_message(response, webhook_url)
    elif mode == 1: 
        if lottery_type == 0:
            notify.send_lotto_buying_message(response, webhook_url)
        else:
            notify.send_win720_buying_message(response, webhook_url)

def check():
    auth_ctrl, _, webhook_url = _setup_and_login()

    response = check_winning_lotto645(auth_ctrl)
    send_message(0, 0, response=response, webhook_url=webhook_url)

    time.sleep(10)
    
    response = check_winning_win720(auth_ctrl)
    send_message(0, 1, response=response, webhook_url=webhook_url)

def buy(): 
    mode, count, manual_numbers, recommendation_info = resolve_lotto_purchase_mode()

    auth_ctrl, username, webhook_url = _setup_and_login()
    ensure_balance(auth_ctrl, webhook_url, '통합 구매 실행', (1000 * count) + 5000)

    response = buy_lotto645(auth_ctrl, count, mode, manual_numbers)
    if recommendation_info:
        response['recommendation'] = recommendation_info
    send_message(1, 0, response=response, webhook_url=webhook_url)

    time.sleep(10)

    auth_ctrl.http_client.session.cookies.clear()
    auth_ctrl, username, webhook_url = _setup_and_login()

    response = buy_win720(auth_ctrl, username) 
    send_message(1, 1, response=response, webhook_url=webhook_url)

def lotto_buy():
    mode, count, manual_numbers, recommendation_info = resolve_lotto_purchase_mode()
    auth_ctrl, _, discord_webhook_url = _setup_and_login()
    ensure_balance(auth_ctrl, discord_webhook_url, '로또 구매 실행', 1000 * count)
    
    response = buy_lotto645(auth_ctrl, count, mode, manual_numbers)
    if recommendation_info:
        response['recommendation'] = recommendation_info
    send_message(1, 0, response=response, webhook_url=discord_webhook_url)

def win720_buy():
    auth_ctrl, username, discord_webhook_url = _setup_and_login()
    ensure_balance(auth_ctrl, discord_webhook_url, '연금복권 구매 실행', 5000)

    response = buy_win720(auth_ctrl, username)
    send_message(1, 1, response=response, webhook_url=discord_webhook_url)

def lotto_check():
    auth_ctrl, _, discord_webhook_url = _setup_and_login()

    response = check_winning_lotto645(auth_ctrl)
    send_message(0, 0, response=response, webhook_url=discord_webhook_url)

def win720_check():
    auth_ctrl, _, discord_webhook_url = _setup_and_login()

    response = check_winning_win720(auth_ctrl)
    send_message(0, 1, response=response, webhook_url=discord_webhook_url)

def show_balance():
    auth_ctrl, _, _ = _setup_and_login()
    print({'balance': auth_ctrl.get_user_balance()})


def assign_virtual_account():
    auth_ctrl, _, webhook_url = _setup_and_login()
    _, charge_amount, _ = get_charge_config()
    send_charge_guide(auth_ctrl, webhook_url, '수동 충전 요청', 0, 0, charge_amount)


def refresh_lotto_data():
    result = refresh_draw_data.update_latest_draw()
    print(result)


def lotto_recommend():
    count = int(os.environ.get('COUNT') or '1')
    strategy = (os.environ.get('LOTTO_STRATEGY') or 'balanced_mix').strip().lower()
    try:
        refresh_draw_data.update_latest_draw()
    except Exception as exc:
        print(f"[Warning] draw refresh skipped: {exc}")
    recommendation_info = recommendation.recommend_lotto_numbers(count=count, strategy=strategy)
    print(recommendation_info)


def run():
    if len(sys.argv) < 2:
        print("Usage: python controller.py [buy|check|buy_lotto|buy_win720|check_lotto|check_win720|recommend_lotto|refresh_lotto_data|show_balance|assign_virtual_account]")
        return

    if sys.argv[1] == "buy":
        buy()
    elif sys.argv[1] == "check":
        check()
    elif sys.argv[1] == "buy_lotto":
        lotto_buy()
    elif sys.argv[1] == "buy_win720":
        win720_buy()
    elif sys.argv[1] == "check_lotto":
        lotto_check()
    elif sys.argv[1] == "check_win720":
        win720_check()
    elif sys.argv[1] == "recommend_lotto":
        lotto_recommend()
    elif sys.argv[1] == "refresh_lotto_data":
        refresh_lotto_data()
    elif sys.argv[1] == "show_balance":
        show_balance()
    elif sys.argv[1] == "assign_virtual_account":
        assign_virtual_account()
  

if __name__ == "__main__":
    run()
