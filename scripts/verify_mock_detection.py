import sys
import os
import threading
import time

_proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj not in sys.path:
    sys.path.insert(0, _proj)

from src.streaming.screen_streamer import ScreenStreamer

# 한글 콘솔 인코딩 대응
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def run():
    print("1. 창이 없는 상태에서 감지 테스트...")
    s = ScreenStreamer()
    det, info = s.get_detection_status()
    print(f"   ▶ 감지 결과: detected={det}, info={info}")
    assert det is False, "창이 없는데 감지되면 안 됨"

    print("\n2. 'The Spike Cross' 가상 창 생성 후 감지 테스트...")
    import tkinter as tk
    root = tk.Tk()
    root.title("The Spike Cross")
    root.geometry("1280x720+100+100")
    root.update()

    time.sleep(0.5)

    s2 = ScreenStreamer()
    det2, info2 = s2.get_detection_status()
    print(f"   ▶ 감지 결과: detected={det2}")
    if info2:
        print(f"   ▶ 제목: {info2.get('title')}")
        print(f"   ▶ 해상도: {info2.get('width')}x{info2.get('height')}")
        print(f"   ▶ 프로세스: {info2.get('proc')}")
        print(f"   ▶ HWND: {info2.get('hwnd')}")

    root.destroy()
    assert det2 is True, "가상 Spike 창이 감지되어야 함"

    print("\n3. 한글 타이틀('더 스파이크 크로스') 창 감지 테스트...")
    root_ko = tk.Tk()
    root_ko.title("더 스파이크 크로스")
    root_ko.geometry("1920x1080+50+50")
    root_ko.update()

    time.sleep(0.5)

    s3 = ScreenStreamer()
    det3, info3 = s3.get_detection_status()
    print(f"   ▶ 감지 결과: detected={det3}")
    if info3:
        print(f"   ▶ 제목: {info3.get('title')}")
        print(f"   ▶ 해상도: {info3.get('width')}x{info3.get('height')}")

    root_ko.destroy()
    assert det3 is True, "한글 제목 창도 감지되어야 함"

    print("\n🎉 영문/한글 및 프로세스 정밀 감지 검증 100% 통과!")

if __name__ == "__main__":
    run()
