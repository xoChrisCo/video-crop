import shutil
import subprocess
import sys
from pathlib import Path

import cv2


WINDOW = "Drag to draw rectangle, adjust corners/edges, Enter to submit, Esc to abort"
HANDLE = 10


def get_frame(video_path: Path, seconds: float | None):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        sys.exit(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    duration = frame_count / fps if fps else 0

    target = seconds if seconds is not None else duration / 2
    cap.set(cv2.CAP_PROP_POS_MSEC, target * 1000)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        sys.exit(f"Could not read frame at {target:.2f}s")
    return frame


def pick_rectangle(frame):
    fh, fw = frame.shape[:2]
    rect = {"x1": None, "y1": None, "x2": None, "y2": None}
    drag = {"mode": None, "ox": 0, "oy": 0, "rx1": 0, "ry1": 0, "rx2": 0, "ry2": 0}

    def has_rect():
        return rect["x1"] is not None

    def norm():
        x1, y1, x2, y2 = rect["x1"], rect["y1"], rect["x2"], rect["y2"]
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)

    def redraw():
        img = frame.copy()
        if has_rect():
            x1, y1, x2, y2 = norm()
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            for cx, cy in [(x1, y1), (x2, y1), (x1, y2), (x2, y2)]:
                cv2.rectangle(img, (cx - 5, cy - 5), (cx + 5, cy + 5), (0, 255, 0), -1)
        cv2.imshow(WINDOW, img)

    def hit_test(x, y):
        if not has_rect():
            return None
        x1, y1, x2, y2 = norm()
        corners = {
            "nw": (x1, y1), "ne": (x2, y1),
            "sw": (x1, y2), "se": (x2, y2),
        }
        for name, (cx, cy) in corners.items():
            if abs(x - cx) <= HANDLE and abs(y - cy) <= HANDLE:
                return name
        on_left = abs(x - x1) <= HANDLE and y1 <= y <= y2
        on_right = abs(x - x2) <= HANDLE and y1 <= y <= y2
        on_top = abs(y - y1) <= HANDLE and x1 <= x <= x2
        on_bot = abs(y - y2) <= HANDLE and x1 <= x <= x2
        if on_left: return "w"
        if on_right: return "e"
        if on_top: return "n"
        if on_bot: return "s"
        if x1 < x < x2 and y1 < y < y2:
            return "move"
        return None

    def on_mouse(event, x, y, flags, _):
        if event == cv2.EVENT_LBUTTONDOWN:
            mode = hit_test(x, y) if has_rect() else None
            if mode is None:
                rect["x1"], rect["y1"] = x, y
                rect["x2"], rect["y2"] = x, y
                drag["mode"] = "new"
            else:
                drag["mode"] = mode
                drag["ox"], drag["oy"] = x, y
                drag["rx1"], drag["ry1"] = rect["x1"], rect["y1"]
                drag["rx2"], drag["ry2"] = rect["x2"], rect["y2"]
            redraw()
        elif event == cv2.EVENT_MOUSEMOVE and drag["mode"]:
            m = drag["mode"]
            if m == "new":
                rect["x2"], rect["y2"] = x, y
            elif m == "move":
                dx, dy = x - drag["ox"], y - drag["oy"]
                w = drag["rx2"] - drag["rx1"]
                h = drag["ry2"] - drag["ry1"]
                rect["x1"] = max(0, min(fw - 1 - abs(w), drag["rx1"] + dx)) if w >= 0 else drag["rx1"] + dx
                rect["y1"] = max(0, min(fh - 1 - abs(h), drag["ry1"] + dy)) if h >= 0 else drag["ry1"] + dy
                rect["x2"] = rect["x1"] + w
                rect["y2"] = rect["y1"] + h
            else:
                if "n" in m: rect["y1"] = y
                if "s" in m: rect["y2"] = y
                if "w" in m: rect["x1"] = x
                if "e" in m: rect["x2"] = x
            redraw()
        elif event == cv2.EVENT_LBUTTONUP:
            drag["mode"] = None

    cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(WINDOW, on_mouse)
    redraw()

    while True:
        key = cv2.waitKey(20) & 0xFF
        if key == 27:  # Esc
            close_window()
            sys.exit("Cancelled.")
        if key in (13, 10) and has_rect():  # Enter
            x1, y1, x2, y2 = norm()
            if x2 - x1 > 0 and y2 - y1 > 0:
                break
    close_window()
    return norm()


def close_window():
    cv2.destroyAllWindows()
    for _ in range(4):
        cv2.waitKey(1)


def bounding_box(rect, frame_w, frame_h):
    x1, y1, x2, y2 = rect
    x = max(0, x1)
    y = max(0, y1)
    w = min(frame_w, x2) - x
    h = min(frame_h, y2) - y
    w -= w % 2
    h -= h % 2
    if w <= 0 or h <= 0:
        sys.exit("Rectangle has zero area.")
    return x, y, w, h


def main():
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        sys.exit("Usage: crop.py <video_path> [seconds]")
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found on PATH.")

    video_path = Path(sys.argv[1])
    if not video_path.is_file():
        sys.exit(f"File not found: {video_path}")
    seconds = float(sys.argv[2]) if len(sys.argv) == 3 else None

    frame = get_frame(video_path, seconds)
    h, w = frame.shape[:2]
    rect = pick_rectangle(frame)
    cx, cy, cw, ch = bounding_box(rect, w, h)

    out_path = video_path.with_name(f"{video_path.stem}_cropped{video_path.suffix}")
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", f"crop={cw}:{ch}:{cx}:{cy}",
        "-c:a", "copy",
        str(out_path),
    ]
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit("ffmpeg failed.")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
