"""
test_spike_detection.py
The Spike Cross 게임 윈도우 정밀 감지 엔진 테스트 및 진단 도구
"""

import sys
import ctypes
from ctypes import wintypes
import time

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

# 한글 콘솔 인코딩 대응
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def get_process_name_by_pid(pid: int) -> str:
    """PID를 바탕으로 실행 파일 이름을 조회 (kernel32 API 활용, 무권한/초고속)."""
    if not pid:
        return ""
    h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h_proc:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
            return buf.value.split("\\")[-1]
    finally:
        kernel32.CloseHandle(h_proc)
    return ""

def scan_all_game_windows():
    """모든 데스크톱 윈도우를 탐색하여 The Spike 게임 윈도우를 정밀 감지."""
    # 대화형 데스크톱(WinSta0\Default) 접근 권한 확보
    winsta0 = user32.OpenWindowStationW('WinSta0', False, 0x10000000)
    if winsta0:
        user32.SetProcessWindowStation(winsta0)

    desk = user32.OpenDesktopW('Default', 0, False, 0x10000000)
    
    candidates = []
    
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def enum_callback(hwnd, _):
        if not user32.IsWindow(hwnd):
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        if user32.IsIconic(hwnd):  # 최소화 상태 제외
            return True

        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top

        # 너무 작은 보조/트레이 윈도우는 제외
        if w < 160 or h < 160:
            return True

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        pname = get_process_name_by_pid(pid.value)
        pname_lower = pname.lower()

        length = user32.GetWindowTextLengthW(hwnd)
        title = ""
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value
        title_lower = title.lower()

        # 런처 자체나 IDE, 웹 브라우저는 제외
        ignore_processes = ["thespikelauncher.exe", "antigravity.exe", "msedge.exe", "chrome.exe", "firefox.exe", "code.exe"]
        if pname_lower in ignore_processes or "launcher" in pname_lower:
            return True

        # 1순위: 프로세스 이름이 TheSpike 계열인 경우 (100% 확실)
        is_spike_process = ("spike" in pname_lower and "thespike" in pname_lower) or ("thespike-cross" in pname_lower)

        # 2순위: 윈도우 타이틀 매칭 (Steam 웹/상점창 제외)
        is_spike_title = (
            "the spike" in title_lower or 
            "spike cross" in title_lower or 
            "더 스파이크" in title_lower or 
            "더스파이크" in title_lower
        ) and "steam" not in pname_lower

        if is_spike_process or is_spike_title:
            score = 100 if is_spike_process else 80
            candidates.append({
                "hwnd": hwnd,
                "pid": pid.value,
                "process_name": pname,
                "title": title,
                "width": w,
                "height": h,
                "rect": (rect.left, rect.top, rect.right, rect.bottom),
                "score": score
            })

        return True

    cb = WNDENUMPROC(enum_callback)

    # 1. OpenDesktop 기반 열거
    if desk:
        user32.EnumDesktopWindows(desk, cb, 0)
    
    # 2. 기본 EnumWindows로도 2차 보완 열거
    if not candidates:
        user32.EnumWindows(cb, 0)

    # 점수 높은 순(프로세스 일치 우선), 해상도 큰 순으로 정렬
    candidates.sort(key=lambda x: (x["score"], x["width"] * x["height"]), reverse=True)
    return candidates

def run_diagnostics():
    print("=" * 65)
    print("🎯 The Spike Cross 게임 윈도우 감지 엔진 진단 테스트")
    print("=" * 65)

    print("🔍 실행 중인 The Spike 프로세스 및 윈도우를 스캔 중...")
    results = scan_all_game_windows()

    if results:
        best = results[0]
        print(f"\n🎉 [성공] The Spike 게임 창이 완벽하게 감지되었습니다!")
        print(f"   ▶ 최적 타겟 HWND: {best['hwnd']}")
        print(f"   ▶ 프로세스 이름:  {best['process_name']} (PID: {best['pid']})")
        print(f"   ▶ 윈도우 제목:    '{best['title']}'")
        print(f"   ▶ 해상도:        {best['width']} x {best['height']}")
        print(f"   ▶ 화면 좌표:      {best['rect']}")
        print(f"   ▶ 매칭 신뢰도:    {best['score']}%")

        if len(results) > 1:
            print(f"\n기타 감지된 후보 창 ({len(results)-1}개):")
            for c in results[1:]:
                print(f"   - HWND {c['hwnd']}: [{c['process_name']}] '{c['title']}' ({c['width']}x{c['height']})")
    else:
        print("\nℹ️ [대기] 현재 The Spike 게임 창이 감지되지 않았습니다.")
        print("   이유: 게임이 아직 실행되지 않았거나 최소화되어 있습니다.")
        print("   스트리머 동작 모드: 🖥️ 전체 데스크톱 화면 공유로 자동 전환 (안전 폴백)")

    print("=" * 65)
    return len(results) > 0

if __name__ == "__main__":
    run_diagnostics()
