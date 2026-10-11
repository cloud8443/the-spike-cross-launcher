# 🏐 The Spike Cross - Multiplayer Launcher

배구 게임 **더 스파이크 크로스(The Spike Cross)**를 위한 온라인 멀티플레이어 매칭 런처 및 실시간 로비 시스템입니다.

---

## 📁 프로젝트 디렉토리 구조

```plaintext
├── src/                          # 클라이언트 소스코드
│   └── main.py                   # PyQt6 기반 런처 GUI 애플리케이션
├── server/                       # 중앙 매칭 및 중계 백엔드
│   ├── server.py                 # 비동기(asyncio) TCP 로비/채팅 중계 서버
│   ├── the-spike-server.service  # Linux systemd 데몬 등록 파일
│   └── bot.py                    # 원격 테스트용 AI 봇 스크립트
├── scripts/                      # 자동화 스크립트
│   ├── build_exe.bat             # PyInstaller를 이용한 단일 .exe 빌드 스크립트
│   └── run_dev.bat               # 개발용 클라이언트 실행 스크립트
├── dist/                         # 빌드 완료된 배포용 실행 파일 (TheSpikeLauncher.exe)
├── requirements.txt              # 개발 환경 필수 라이브러리 목록
├── .gitignore                    # Git 버전 관리 제외 목록
└── 실행하기.bat                  # 루트 실행용 바로가기 배치 파일
```

---

## 🚀 빠른 시작 (개발 환경 세팅)

### 1. 필수 요구사항
* Python 3.10 이상 권장
* Windows 환경 (클라이언트 기준)

### 2. 가상환경 및 라이브러리 설치
```bash
pip install -r requirements.txt
```

### 3. 클라이언트 실행 (개발 모드)
```bash
# 스크립트 이용
scripts\run_dev.bat

# 또는 직접 실행
python src/main.py
```

---

## 📦 단일 실행 파일 (.exe) 빌드 방법

파이썬이 설치되지 않은 일반 유저에게 배포하기 위한 독립형 `.exe` 빌드:

```bash
scripts\build_exe.bat
```

빌드가 완료되면 `dist/TheSpikeLauncher.exe` 파일이 생성됩니다. 이 파일 하나만 유저들에게 전달하면 설치 과정 없이 즉시 실행됩니다.

---

## 🌐 중앙 서버 아키텍처

* **서버 IP**: `146.56.101.107` (포트 `5555`, TCP)
* **프로토콜**: JSON Lines (`\n` 구분자 기반 경량 프레이밍)
* **핵심 기능**:
  * 실시간 공개 방 목록 생성 및 브로드캐스트
  * 1:1 대기실 매칭 및 참가자 관리
  * 실시간 대기실 채팅 중계
  * 비정상 종료(Disconnect) 시 유령 방 자동 정리 및 대기실 복구

### 서버 데몬 관리 (Ubuntu / OCI)
```bash
# 상태 확인
sudo systemctl status the-spike-server

# 실시간 로그 확인
sudo journalctl -u the-spike-server -f

# 서비스 재시작
sudo systemctl restart the-spike-server
```

---

## 🤝 공동 작업 가이드라인
1. `src/main.py`는 클라이언트 UI 및 사용자 인터랙션을 담당합니다.
2. `server/server.py`는 패킷 중계 및 방 상태 머신을 담당합니다.
3. 새로운 패킷 액션(예: 게임 시작 신호, 키 입력 패킷 등)을 추가할 때는 `action` 필드명을 정의하여 양쪽 모두에서 처리하도록 구현합니다.
