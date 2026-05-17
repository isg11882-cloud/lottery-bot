import copy
import datetime
import requests
import json
import base64
import binascii
import time
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
from HttpClient import HttpClientSingleton

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

class AuthController:
    _REQ_HEADERS = {
        "User-Agent": USER_AGENT,
        "Connection": "keep-alive",
        "Cache-Control": "max-age=0",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "Upgrade-Insecure-Requests": "1",
        "Origin": "https://www.dhlottery.co.kr",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Referer": "https://www.dhlottery.co.kr/",
        "Sec-Fetch-Site": "same-site",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-User": "?1",
        "Sec-Fetch-Dest": "document",
        "Accept-Language": "ko,en-US;q=0.9,en;q=0.8,ko-KR;q=0.7",
    }

    _AUTH_CRED = ""

    def __init__(self):
        self.http_client = HttpClientSingleton.get_instance()

    def login(self, user_id: str, password: str):
        assert isinstance(user_id, str)
        assert isinstance(password, str)

        max_retries = 5
        for attempt in range(max_retries):
            try:
                # 1. Warm-up
                self.http_client.get("https://www.dhlottery.co.kr/")
                self.http_client.get("https://www.dhlottery.co.kr/user.do?method=login", headers=self._REQ_HEADERS)
                
                # 2. RSA Key Fetch
                modulus, exponent = self._get_rsa_key()

                # 3. Encrypt
                enc_user_id = self._rsa_encrypt(user_id, modulus, exponent)
                enc_password = self._rsa_encrypt(password, modulus, exponent)

                # 4. Prepare Login Request
                headers = copy.deepcopy(self._REQ_HEADERS)
                headers.update({
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "https://www.dhlottery.co.kr",
                    "Referer": "https://www.dhlottery.co.kr/user.do?method=login"
                })
                
                data = {
                    "userId": enc_user_id,
                    "userPswdEncn": enc_password, 
                    "inpUserId": user_id
                }

                # 5. Execute Login
                self._try_login(headers, data)
                return # Success
                
            except requests.RequestException as e:
                time.sleep(2)
                if attempt == max_retries - 1:
                     print(f"[Error] Login sequence failed after {max_retries} attempts: {e}")
                     raise
                print(f"[Retry] Login failed ({attempt+1}/{max_retries}): {e}. Retrying...")
        
    def add_auth_cred_to_headers(self, headers: dict) -> str:
        assert isinstance(headers, dict)

        copied_headers = copy.deepcopy(headers)
        return copied_headers

    def _get_default_auth_cred(self):
        res = self.http_client.get(
            "https://www.dhlottery.co.kr/common.do?method=main"
        )
        return self._get_j_session_id_from_response(res)

    def _get_rsa_key(self):
        headers = copy.deepcopy(self._REQ_HEADERS)
        headers.update({
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.dhlottery.co.kr/user.do?method=login"
        })
        headers.pop("Upgrade-Insecure-Requests", None)

        res = self.http_client.get(
            "https://www.dhlottery.co.kr/login/selectRsaModulus.do",
            headers=headers
        )
        
        try:
            data = res.json()
        except ValueError:
             raise ValueError(f"Failed to parse JSON. St: {res.status_code}")
        
        if "data" in data and "rsaModulus" in data["data"]:
            modulus = data["data"]["rsaModulus"]
            exponent = data["data"]["publicExponent"]
            return modulus, exponent
        
        if "rsaModulus" in data:
            return data["rsaModulus"], data["publicExponent"]
            
        raise KeyError("rsaModulus not found")

    def _rsa_encrypt(self, text, modulus, exponent):
        key_spec = RSA.construct((int(modulus, 16), int(exponent, 16)))
        cipher = PKCS1_v1_5.new(key_spec)
        ciphertext = cipher.encrypt(text.encode('utf-8'))
        return binascii.hexlify(ciphertext).decode('utf-8')

    def _get_j_session_id_from_response(self, res: requests.Response):
        assert isinstance(res, requests.Response)

        for cookie in res.cookies:
            if cookie.name == "JSESSIONID":
                return cookie.value
        
        return self.get_current_session_id()

    def _generate_req_headers(self):
        return copy.deepcopy(self._REQ_HEADERS)

    def _try_login(self, headers: dict, data: dict):
        assert isinstance(headers, dict)
        assert isinstance(data, dict)
        
        res = self.http_client.post(
            "https://www.dhlottery.co.kr/login/securityLoginCheck.do",
            headers=headers,
            data=data,
        )
        
        new_jsessionid = self._get_j_session_id_from_response(res)
        if new_jsessionid:
             self._update_auth_cred(new_jsessionid)

        try:
             self.http_client.get("https://www.dhlottery.co.kr/main", headers=self._REQ_HEADERS)
        except Exception as e:
             print(f"[Warning] Failed to check main page after login: {e}")
             
        return res

    def _update_auth_cred(self, j_session_id: str) -> None:
        assert isinstance(j_session_id, str)
        self._AUTH_CRED = j_session_id
        
        self.http_client.session.cookies.set("JSESSIONID", j_session_id, domain=".dhlottery.co.kr")

        wmonid = None
        for cookie in self.http_client.session.cookies:
             if cookie.name == "WMONID":
                 wmonid = cookie.value
                 break
        
        if wmonid:
             self.http_client.session.cookies.set("WMONID", wmonid, domain=".dhlottery.co.kr")

    def get_current_session_id(self) -> str:
        for cookie in self.http_client.session.cookies:
            if cookie.name in ["JSESSIONID", "DHJSESSIONID", "WMONID"]:
                return cookie.value
        
        if self._AUTH_CRED:
            return self._AUTH_CRED

        return ""
            
    def _fetch_user_mndp(self) -> dict:
        try:
            self.http_client.get("https://www.dhlottery.co.kr/mypage/home")
        except requests.RequestException:
            pass

        timestamp = int(datetime.datetime.now().timestamp() * 1000)
        url = f"https://www.dhlottery.co.kr/mypage/selectUserMndp.do?_={timestamp}"

        headers = copy.deepcopy(self._REQ_HEADERS)
        headers.update({
            "Referer": "https://www.dhlottery.co.kr/mypage/home",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "requestMenuUri": "/mypage/home",
            "AJAX": "true",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Dest": "empty"
        })

        res = self.http_client.get(url, headers=headers)
        txt = res.text.strip()
        if txt.startswith("<"):
            raise RuntimeError("확인 불가 (로그인/설정)")

        data = json.loads(txt)
        if 'data' in data and isinstance(data['data'], dict):
            data = data['data']
        if 'userMndp' in data:
            data = data['userMndp']
        return data

    def get_user_balance_amount(self) -> int:
        last_error = None

        for _ in range(3):
            try:
                data = self._fetch_user_mndp()
                if 'crntEntrsAmt' in data:
                    return int(str(data['crntEntrsAmt']).replace(',', ''))
                if 'totalAmt' in data:
                    return int(str(data['totalAmt']).replace(',', ''))
                return 0
            except Exception as e:
                last_error = e
                time.sleep(1)

        print(f"[Error] 잔액 조회에 실패했습니다: {last_error}")
        raise RuntimeError("정보 로드 실패 (로그 확인)")

    def get_user_balance(self) -> str:
        try:
            return f"{self.get_user_balance_amount():,}원"
        except Exception:
            return "정보 로드 실패 (로그 확인)"

    def assign_virtual_account(self, amount: int) -> dict:
        if amount <= 0:
            raise ValueError("amount must be positive")

        def _get_tomorrow() -> str:
            tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
            return tomorrow.strftime("%Y%m%d")

        params = {
            "VbankExpDate": _get_tomorrow(),
            "PayMethod": "VBANK",
            "VbankBankCode": "089",
            "Price": str(amount),
        }

        resp = self.http_client.get("https://www.dhlottery.co.kr/mypage/kbankInit.do", params=params)
        req = resp.json().get("data", {}).get("reqVO", {})
        if not req:
            raise RuntimeError("가상계좌 초기화 정보 조회 실패")

        resp2 = self.http_client.get(
            "https://www.dhlottery.co.kr/mypage/kbankProcess.do",
            params={
                "PayMethod": req.get("payMethod", "VBANK"),
                "GoodsName": req.get("goodsName"),
                "Moid": req.get("moid"),
                "UserIP": req.get("userIP"),
                "MallUserID": req.get("mallUserID"),
                "VbankExpDate": req.get("vbankExpDate"),
                "Amt": req.get("amt"),
                "VbankBankCode": req.get("vbankBankCode"),
                "VbankNum": req.get("fxVrAccountNo"),
                "FxVrAccountNo": req.get("fxVrAccountNo"),
                "VBankAccountName": req.get("buyerName"),
            },
        )
        res = resp2.json().get("data", {}).get("resVO", {})
        if res.get("resultCode") == "FAIL":
            raise RuntimeError("가상계좌 발급이 거절되었습니다")

        vbank_num = res.get("vbankNum", "")
        if not vbank_num:
            raise RuntimeError("가상계좌 번호를 받지 못했습니다")

        formatted = f"{vbank_num[:3]}-{vbank_num[3:7]}-{vbank_num[7:10]}-{vbank_num[10:]}"
        return {
            "bank_name": res.get("vbankBankName", "케이뱅크"),
            "account_number": formatted,
            "account_number_raw": vbank_num,
            "amount": int(req.get("amt") or amount),
            "expires_on": req.get("vbankExpDate") or params["VbankExpDate"],
            "account_holder": req.get("buyerName") or "동행복권",
        }
