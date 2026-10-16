# 🤖 Claude 모델을 위한 초저지연 멀티플레이어 구현 & 인수인계 가이드

> **문서 대상**: Antigravity Claude 모델 (Claude 3.5 Sonnet / 3.7 Sonnet)  
> **프로젝트 위치**: `c:\Users\박민성\Desktop\the spike launcher creation`  
> **목표**: 기존 PyQt6 런처 및 Oracle Cloud 서버에 **파섹 이상의 초저지연 2인 원격 멀티플레이 시스템**을 완벽하게 추가/통합하는 작업 가이드

---

## 1. 현재 프로젝트 상태 및 핵심 컨텍스트

### 1.1 현재 인프라 & 파일 맵
* **오라클 클라우드 (OCI) 중계 서버**:
  * IP: `146.56.101.107`, 포트: `5555` (TCP 로비 서버 구동 중)
  * 서비스: `sudo systemctl status the-spike-server`
  * 포트 자동 개방: `ssh -i "C:\Users\박민성\Desktop\oracle cloud\ssh-key-2026-10-08.key" ubuntu@146.56.101.107 "port-manager open <포트>"`
* **게임 정보**:
  * 게임명: **The Spike Cross (더 스파이크 크로스)**
  * Steam App ID: `3983810` (실행 명령: `os.startfile("steam://run/3983810")`)
  * 멀티플레이 방식: 원래 단일 PC에서 2개의 컨트롤러(1P, 2P)로 즐기는 로컬 대전
* **기존 소스코드 구조**:
  ```plaintext
  the spike launcher creation/
  ├── TheSpikeLauncher.exe          # 현재 빌드된 단일 실행 파일
  ├── 실행하기.bat                  # python src/main.py 실행기
  ├── src/main.py                   # PyQt6 런처 메인 (방 목록, 대기실, 채팅 구현 완료)
  ├── server/server.py              # TCP 로비 서버 (JSON Lines \n 프로토콜)
  ├── server/bot.py                 # 가상 접속 테스트 봇
  ├── scripts/build_exe.bat         # PyInstaller 원클릭 빌드 스크립트
  ├── requirements.txt              # 현재: PyQt6, pyinstaller
  └── README.md
  ```

---

## 2. 작업 목표 및 요구사항 요약

1. **2인 매칭 & 호스트 전환**:
   * 대기실에 유저가 2명이 되면 양쪽 화면에 **`[ 🚀 내가 호스트로 시작하기 ]`** 버튼 표시.
   * 둘 중 한 명이 누르면 그 유저가 **Host**, 상대방이 **Guest**로 확정.
2. **호스트(Host) 동작**:
   * 스팀 게임 자동 실행 (`steam://run/3983810`).
   * 가상 Xbox 360 패드(2P) 생성 (`vgamepad` / ViGEmBus).
   * 게임 화면/오디오 초저지연 캡처 및 스트리밍 송신 (Sunshine 또는 DXGI+NVENC/AMF/QSV).
3. **게스트(Guest) 동작**:
   * 호스트 화면/오디오를 수신하는 초저지연 렌더러 창 실행 (Moonlight 또는 D3D11 저지연 뷰어).
   * 로컬 키보드/패드 입력을 실시간으로 캡처하여 호스트의 가상 2P 패드로 전송.
4. **키 매핑(Key Remapping) 기능**:
   * 게스트가 키보드로 플레이할 때, 원하는 키(기본: W/A/S/D + K/L/I/J/ESC)를 가상 Xbox 360 패드 버튼에 매핑할 수 있는 설정 창 제공.
5. **국내 초저지연 (파섹 이상 체감, < 20ms)**:
   * P2P UDP 직결 우선, 실패 시 OCI 춘천 서버(`146.56.101.107`) 고속 릴레이.

---

## 3. 구현 단계별 가이드 (Step-by-Step Instructions)

### Step 1: 의존성 패키지 추가 (`requirements.txt`)
다음 패키지를 `requirements.txt`에 추가하고 `pip install` 합니다:
```text
PyQt6>=6.5.0
pyinstaller>=6.0.0
vgamepad>=0.1.0
pywin32>=306
```
> [!NOTE]
> `vgamepad`는 Windows에서 `ViGEmBus` 드라이버를 통해 가상 Xbox 360 및 DualShock 4 패드를 생성하는 파이썬 라이브러리입니다.

---

### Step 2: 키 매핑 및 가상 패드 모듈 작성 (`src/streaming/`)
새로운 디렉토리 `src/streaming/` 및 `src/ui/`를 생성하고 다음 파일들을 구현합니다.

#### 1) `config/keymap.json`
게스트 키보드 -> 2P Xbox 360 패드 기본 매핑 프리셋:
```json
{
  "UP": "W",
  "DOWN": "S",
  "LEFT": "A",
  "RIGHT": "D",
  "RECEIVE_SLIDE": "K",
  "JUMP_SPIKE": "L",
  "BLOCK": "I",
  "SPECIAL_TOSS": "J",
  "PAUSE": "ESCAPE"
}
```

#### 2) `src/streaming/virtual_controller.py`
호스트 측에서 게스트의 패킷을 받아 가상 패드를 움직이는 래퍼 클래스:
```python
import vgamepad as vg

class VirtualGamepadManager:
    def __init__(self):
        self.gamepad = None

    def initialize(self):
        try:
            self.gamepad = vg.VX360Gamepad()
            return True, "가상 Xbox 360 패드가 정상적으로 생성되었습니다."
        except Exception as e:
            return False, f"ViGEmBus 드라이버 오류: {e}"

    def update_input(self, button_name, is_pressed):
        if not self.gamepad:
            return
        mapping = {
            "A": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
            "B": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
            "X": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
            "Y": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
            "START": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
            "DPAD_UP": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
            "DPAD_DOWN": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
            "DPAD_LEFT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
            "DPAD_RIGHT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
        }
        if button_name in mapping:
            btn = mapping[button_name]
            if is_pressed:
                self.gamepad.press_button(button=btn)
            else:
                self.gamepad.release_button(button=btn)
            self.gamepad.update()

    def release_all(self):
        if self.gamepad:
            self.gamepad.reset()
            self.gamepad.update()
```

#### 3) `src/ui/keymap_dialog.py`
사용자가 키 매핑을 커스텀할 수 있는 PyQt6 QDialog 모달 제작.

---

### Step 3: OCI 서버 프로토콜 확장 (`server/server.py`)
기존 JSON Lines 프로토콜에 2인 도달 및 호스트 선점 액션을 추가합니다:

```python
# 방에 유저가 입장할 때 인원이 2명이면 양쪽에 브로드캐스트
if len(room["users"]) == 2:
    broadcast_to_room(room_id, {
        "action": "room_ready_for_host",
        "room_id": room_id,
        "users": room["users"]
    })

# 클라이언트가 호스트 버튼을 눌렀을 때 (claim_host)
elif action == "claim_host":
    if room.get("host") is None:
        room["host"] = username
        guest = [u for u in room["users"] if u != username][0]
        room["guest"] = guest
        broadcast_to_room(room_id, {
            "action": "session_started",
            "room_id": room_id,
            "host": username,
            "guest": guest,
            "relay_server": "146.56.101.107:7777"
        })

# P2P ICE / 연결 정보 교환 중계 (signal_exchange)
elif action == "signal_exchange":
    target_user = data.get("to")
    send_to_user(target_user, {
        "action": "signal_exchange",
        "from": username,
        "payload": data.get("payload")
    })
```

---

### Step 4: 런처 UI (`src/main.py`) 대기실 연동
1. **대기실 패널에 호스트 버튼 추가**:
   * 기본 상태: `self.host_btn.setVisible(False)` (1명일 때는 숨김)
   * 서버로부터 `room_ready_for_host` 수신 시:
     * `self.host_btn.setVisible(True)`
     * `self.host_btn.setText("🚀 내가 호스트로 시작하기")`
     * 세련된 오렌지-바이올렛 그라데이션 스타일 적용.
2. **버튼 클릭 이벤트**:
   * `self.send_packet({"action": "claim_host", "room_id": self.current_room_id})`
   * 버튼 비활성화 및 로딩 스피너/상태 메시지 표시 (*"호스트 환경을 준비하고 있습니다..."*).
3. **`session_started` 수신 시 분기**:
   * 내가 `host`인 경우:
     * `HostRunner.start_session(guest_ip, room_id)` 실행.
     * 스팀 게임 실행 `os.startfile("steam://run/3983810")`.
     * `VirtualGamepadManager` 초기화.
   * 내가 `guest`인 경우:
     * `GuestRunner.start_session(host_ip, room_id)` 실행.
     * 초저지연 수신 화면 활성화 및 키보드 입력 후킹 시작.

---

### Step 5: 스트리밍 엔진 통합 방식 가이드 (Sunshine / Moonlight Headless)
파섹보다 빠른 반응속도를 달성하기 위해 `tools/` 디렉토리에 Sunshine 및 Moonlight 포터블 바이너리를 활용하거나, 경량 WebRTC C++ 엔진을 백그라운드 프로세스로 호출하도록 구현합니다.

* **호스트 실행 커맨드 (예시)**:
  ```python
  # Sunshine을 헤드리스 모드로 구동 (런처가 서브프로세스로 관리)
  sunshine_cmd = [
      "tools/sunshine/sunshine.exe",
      "--flags", "..."
  ]
  self.host_proc = subprocess.Popen(sunshine_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
  ```
* **게스트 실행 커맨드 (예시)**:
  ```python
  # Moonlight 클라이언트를 저지연 옵션으로 호스트 IP에 자동 다이렉트 연결
  moonlight_cmd = [
      "tools/moonlight/Moonlight.exe",
      "stream", host_ip, "The Spike Cross",
      "--fps", "60",
      "--bitrate", "20000",
      "--surround", "2.0"
  ]
  self.guest_proc = subprocess.Popen(moonlight_cmd)
  ```

---

## 4. Claude 코딩 시 엄격 준수 규칙 (Non-Negotiable Rules)

1. **기존 한국어 UI 문구 변경 금지**:
   * 기존 `src/main.py`에 작성되어 있는 UI 텍스트(방 목록, 대기실, 유저 목록 등)는 사용자가 승인한 원본입니다. 임의로 영어로 바꾸거나 다른 마케팅 문구로 대체하지 마세요.
2. **PyInstaller 번들 경로 호환성 (`sys._MEIPASS`)**:
   * 단일 `.exe`로 빌드할 때 번들된 파일(설정 파일, 아이콘, 바이너리)을 찾을 수 있도록 다음 헬퍼 함수를 반드시 사용하세요:
     ```python
     def resource_path(relative_path):
         if hasattr(sys, '_MEIPASS'):
             return os.path.join(sys._MEIPASS, relative_path)
         return os.path.join(os.path.abspath("."), relative_path)
     ```
3. **서버 반영 후 데몬 재시작**:
   * `server/server.py`를 수정한 후 OCI 서버에 반영할 경우 반드시 다음 명령을 수행해야 합니다:
     ```bash
     ssh -i "C:\Users\박민성\Desktop\oracle cloud\ssh-key-2026-10-08.key" ubuntu@146.56.101.107 "sudo systemctl restart the-spike-server"
     ```

---

이 문서를 기반으로 `src/streaming/`, `src/ui/keymap_dialog.py`, `server/server.py`, `src/main.py` 순서로 작업을 진행하시면 안전하고 완벽하게 멀티플레이 시스템이 완성됩니다.
