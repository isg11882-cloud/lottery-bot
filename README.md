# 소개 

동행복권 사이트내에 계정에 예치금만 넣어두시면 이후 매주 로또와 연금복권을 구입하고 당첨을 체크하여 알려드려요!  

## 이번 적용사항

- GitHub Marketplace의 `rich-automation/lotto-action` 기준 워크플로우를 추가했습니다.
- 신규 워크플로우 파일: `.github/workflows/lotto_action_purchase.yml`
- 기본 구매 수량은 **1장**으로 설정했습니다.
- 실행 시 지난 회차 당첨 확인과 신규 구매 이슈 기록을 액션이 처리합니다.

# 사용법 

![](./.github/images/check.png)

## 방법 1. Marketplace 액션으로 1장 자동구매

1. 레포지토리를 `fork` 또는 새로 생성합니다.
2. `Settings > Secrets and variables > Actions` 에 아래 시크릿을 등록합니다.
   - `ID`: 동행복권 아이디
   - `PASSWORD`: 동행복권 비밀번호
3. 동행복권 계정 예치금을 미리 충전합니다.
4. `Settings > Actions > General > Workflow permissions` 에서 기본 권한이 너무 제한적이면 이슈 작성이 가능하도록 확인합니다.
5. `.github/workflows/lotto_action_purchase.yml` 워크플로우를 활성화합니다.
6. 필요하면 `workflow_dispatch` 로 수동 실행해서 먼저 테스트합니다.

현재 스케줄은 **매주 월요일 19:00 KST** 기준으로 맞춰져 있습니다.

## 방법 2. 기존 Python 스크립트 방식 유지

- 기존 `buy_lotto.yml`, `check_winning.yml` 도 그대로 남겨두었습니다.
- 기존 환경 변수들은 `.env.sample` 을 참고하면 됩니다.

# Reference 
- https://github.com/roeniss/dhlottery-api
- https://github.com/marketplace/actions/lotto-action
