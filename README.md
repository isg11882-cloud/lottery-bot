# 소개 

동행복권 사이트내에 계정에 예치금만 넣어두시면 이후 매주 로또와 연금복권을 구입하고 당첨을 체크하여 알려드려요!  

## 이번 적용사항

- GitHub Marketplace의 `rich-automation/lotto-action` 구성을 참고해 1장 구매 워크플로우를 정리했습니다.
- 다만 해당 Marketplace 액션 저장소는 현재 GitHub에서 비활성화되어 있어, 실제 실행은 이 저장소의 Python 구매 로직으로 우회합니다.
- `lastjung/lotto` 아이디어를 참고한 번호 추천 엔진을 추가했습니다.
- 워크플로우 파일: `.github/workflows/lotto_action_purchase.yml`
- 기본 구매 수량은 **1장**으로 설정했습니다.

# 사용법 

![](./.github/images/check.png)

## 방법 1. 1장 자동구매 워크플로우 실행

1. 레포지토리를 `fork` 또는 새로 생성합니다.
2. `Settings > Secrets and variables > Actions` 에 아래 시크릿을 등록합니다.
   - `USERNAME`: 동행복권 아이디
   - `PASSWORD`: 동행복권 비밀번호
3. 동행복권 계정 예치금을 미리 충전합니다.
4. `.github/workflows/lotto_action_purchase.yml` 워크플로우를 활성화합니다.
5. 필요하면 `workflow_dispatch` 로 수동 실행해서 먼저 테스트합니다.

현재 스케줄은 **매주 월요일 19:00 KST** 기준으로 맞춰져 있습니다.

> 참고: Marketplace의 `rich-automation/lotto-action` 저장소는 현재 비활성화 상태라, 실제 구매는 저장소 내 Python 자동화로 실행됩니다.

## 방법 2. 추천 번호 기반 구매

환경 변수 예시:

- `LOTTO_MODE=RECOMMENDED`
- `COUNT=1`
- `LOTTO_STRATEGY=balanced_mix`

지원 전략:
- `balanced_mix`: 홀짝/고저/합계 균형형
- `physics_bias`: 최근 빈도/위치/핫넘버 반영형
- `cold_theory`: 오래 안 나온 번호 가중형
- `hybrid`: 위 3개를 섞어서 중복 제거 후 추천

추천 번호만 확인하려면:
- `python controller.py recommend_lotto`

## 방법 3. 기존 Python 스크립트 방식 유지

- 기존 `buy_lotto.yml`, `check_winning.yml` 도 그대로 남겨두었습니다.
- 기존 환경 변수들은 `.env.sample` 을 참고하면 됩니다.

# Reference 
- https://github.com/roeniss/dhlottery-api
- https://github.com/marketplace/actions/lotto-action (현재 원본 저장소 비활성화 상태)
