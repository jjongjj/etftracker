# 📈 ETF Auto Tracker

ETF(상장지수펀드) 구성 종목들의 **편입 및 편출 내역을 매일 실시간으로 모니터링**하고, 변동 사항이 있을 때 텔레그램으로 푸시 알림을 보내주는 100% 무료 서버리스(Serverless) 자동화 툴입니다.

---

## 🚀 주요 기능 (Features)

- **자동화된 데이터 수집**: 매일 정해진 시간(GitHub Actions)에 한국거래소(KRX) 데이터를 기반으로 특정 ETF의 구성 종목(PDF)을 파악합니다.
- **스마트 텔레그램 알림**: 어제 기준 구성 종목과 비교하여 새롭게 **편입(Additions)** 되거나 **편출(Deletions)** 된 종목이 발생했을 때만 스마트폰으로 즉시 알림을 전송합니다.
- **아름다운 웹 대시보드 제공**: GitHub Pages를 이용해 언제 어디서나 [웹 대시보드(Demo)](https://jjongjj.github.io/etftracker/)에서 최근 변동 내역과 현재 포트폴리오를 시각적으로 확인할 수 있습니다 (다크모드 기본 지원).
- **무한한 확장성**: 파이썬 코드를 건드릴 필요 없이, `config.json` 파일에 추적하고자 하는 ETF 종목 코드(예: KODEX 200, TIGER 미국테크TOP10 등)만 추가하면 여러 ETF를 동시에 트래킹할 수 있습니다.

---

## ⚙️ 동작 원리 (Architecture)

1. **GitHub Actions 스케줄러**: `.github/workflows/tracker.yml`에 지정된 크론(Cron) 시간마다 깃허브의 클라우드 서버(Ubuntu)가 깨어나 파이썬 환경을 세팅하고 스크립트(`tracker.py`)를 실행합니다.
2. **pykrx (오픈 API 수집)**: 강력한 파이썬 라이브러리인 `pykrx`를 통해 최신 ETF 포트폴리오 리스트를 긁어옵니다. (주말/공휴일에는 거래일 기준으로 알아서 데이터를 탐색합니다.)
3. **히스토리 비교 연산**: 봇이 일한 뒤 저장해둔 `history/constituents.json` 와 오늘 가져온 데이터를 파이썬의 Set(집합) 연산을 이용해 순식간에 비교하여 변경점을 찾습니다.
4. **결과물 자동 반영 (CI/CD)**: 변동 사항을 `dashboard_data.json`으로 출력하고, 봇이 스스로 당신의 GitHub Repository에 자동 커밋(Commit) 및 푸시(Push) 합니다. 이 순간 GitHub Pages가 자동으로 업데이트됩니다!

---

## 🛠 5분 세팅 및 시작하기 (Quick Setup)

본인만의 트래커를 운영하려면 아래 단계만 따라 하시면 됩니다!

### 1단계: Repository 준비
본 저장소를 Fork 받아 자신의 계정으로 가져오거나, 로컬에서 코드를 다운로드한 뒤 본인의 GitHub Repository에 업로드(Push)합니다.

### 2단계: 텔레그램 봇 토큰 및 Chat ID 얻기
1. 텔레그램 앱에서 **BotFather**를 찾아 `/newbot` 명령어로 새 봇을 만들고 **API Token**을 발급 받습니다.
2. 만든 봇과 대화방을 열고 아무 문자나 하나 보냅니다.
3. 브라우저에서 `https://api.telegram.org/bot<나의토큰>/getUpdates` 로 접속해서 나오는 결과값 중 `"chat":{"id": (이 숫자들) }` 를 찾아 **Chat ID**를 메모합니다.

### 3단계: GitHub Secrets 등록 (★★★ 무조건 필수!)
소스코드에 절대 토큰을 적지 마세요.
1. 본인 GitHub Repository 상단의 **[Settings]** 탭 클릭
2. 좌측 메뉴에서 **[Secrets and variables]** -> **[Actions]** 클릭
3. **[New repository secret]** 버튼으로 두 가지를 만듭니다.
   - Name: `TELEGRAM_BOT_TOKEN`, Secret: (발급받은 봇 토큰 값)
   - Name: `TELEGRAM_CHAT_ID`, Secret: (발급받은 챗 아이디 넘버)

### 4단계: 봇에게 자동 기록 권한 부여
봇이 결과를 커밋하고 대시보드를 갱신할 수 있도록 허락해 주어야 합니다.
1. Repository -> **[Settings]** -> **[Actions]** -> **[General]**
2. 맨 밑의 **Workflow permissions** 에서 **"Read and write permissions"** 를 선택하고 Save.

### 5단계: 대시보드 웹페이지 켜기 (GitHub Pages)
1. Repository -> **[Settings]** -> **[Pages]**
2. **Build and deployment** 의 Source를 `Deploy from a branch`로 설정하고, Branch를 `main`으로 지정 후 Save.
3. 잠시 후 `https://[내아이디].github.io/[저장소명]/` 주소로 접속하면 나만의 대시보드가 완성됩니다!

---

## 💡 향후 확장 및 응용 아이디어 (Hack it!)

GitHub Actions와 Python 생태계를 활용하면 다음과 같이 무궁무진한 로봇들을 만들어 볼 수 있습니다.

- **알고리즘 트레이딩 연동**: 편입된 종목을 발견했을 때, 한국투자증권(KIS)이나 토스증권 API 등을 이용해 즉시 내 계좌에서 자동 매수하는 로직을 결합할 수 있습니다.
- **다양한 소스 크롤링**: `BeautifulSoup`, `Selenium` 등을 붙여서 뉴스 기사나 금융감독원 공시 데이터(DART)를 수집하고 텔레그램으로 요약본을 받아보세요.
- **나만의 퀀트 데이터베이스 구축**: 수집한 데이터를 GitHub 저장소의 JSON 파일뿐만 아니라, Firebase나 Supabase 같은 무료 클라우드 DB에 매일 적재하여 나만의 백테스팅 데이터로 활용할 수 있습니다.
- **AI 비서 (LLM) 결합**: OpenAI(ChatGPT)나 Anthropic(Claude) API를 붙여서 "이 종목이 왜 편입됐을까?"에 대한 AI의 요약 코멘트를 텔레그램 알림에 같이 첨부할 수도 있습니다.
