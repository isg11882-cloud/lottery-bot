import os
import re
import sys
from dotenv import load_dotenv

import auth
import lotto645
import win720
import notification
import recommendation
import time


def _setup_and_login():
    load_dotenv(override=True)
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
    load_dotenv(override=True)
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
        rec = recommendation.recommend_lotto_numbers(count=count, strategy=recommendation_strategy)
        return 'MANUAL', len(rec['numbers']), rec['numbers'], rec

    return lotto_mode, count, [], None


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
    
    response = buy_lotto645(auth_ctrl, count, mode, manual_numbers)
    if recommendation_info:
        response['recommendation'] = recommendation_info
    send_message(1, 0, response=response, webhook_url=discord_webhook_url)

def win720_buy():
    auth_ctrl, username, discord_webhook_url = _setup_and_login()

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

def lotto_recommend():
    count = int(os.environ.get('COUNT') or '1')
    strategy = (os.environ.get('LOTTO_STRATEGY') or 'balanced_mix').strip().lower()
    recommendation_info = recommendation.recommend_lotto_numbers(count=count, strategy=strategy)
    print(recommendation_info)


def run():
    if len(sys.argv) < 2:
        print("Usage: python controller.py [buy|check|recommend_lotto]")
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
  

if __name__ == "__main__":
    run()
