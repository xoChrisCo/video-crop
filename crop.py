import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import cv2


WINDOW = "Drag to draw rectangle, adjust corners/edges, Enter to submit, Esc to abort"
HANDLE = 10


def parse_rect(s: str) -> tuple[int, int, int, int]:
    parts = s.split(":")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("expected x:y:w:h")
    try:
        x, y, w, h = (int(p) for p in parts)
    except ValueError:
        raise argparse.ArgumentTypeError("all parts must be integers")
    if w <= 0 or h <= 0:
        raise argparse.ArgumentTypeError("width and height must be > 0")
    return x, y, w, h


def parse_aspect(s: str) -> float:
    parts = s.split(":")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("expected W:H")
    try:
        w, h = (float(p) for p in parts)
    except ValueError:
        raise argparse.ArgumentTypeError("W and H must be numeric")
    if w <= 0 or h <= 0:
        raise argparse.ArgumentTypeError("W and H must be > 0")
    return w / h


def get_frame(video_path: Path, seconds: float | None, frame_index: int | None, percent: float | None):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        sys.exit(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    duration = frame_count / fps if fps else 0

    if frame_index is not None:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        label = f"frame {frame_index}"
    else:
        if seconds is not None:
            target = seconds
        elif percent is not None:
            target = duration * (percent / 100.0)
        else:
            target = duration / 2
        cap.set(cv2.CAP_PROP_POS_MSEC, target * 1000)
        label = f"{target:.2f}s"

    ok, frame = cap.read()
    cap.release()
    if not ok:
        sys.exit(f"Could not read frame at {label}")
    return frame


def pick_rectangle(frame, aspect: float | None, show_grid: bool, display_scale: float):
    fh, fw = frame.shape[:2]
    if display_scale != 1.0:
        disp_w = max(1, int(fw * display_scale))
        disp_h = max(1, int(fh * display_scale))
        scaled = cv2.resize(frame, (disp_w, disp_h))
    else:
        scaled = frame

    rect = {"x1": None, "y1": None, "x2": None, "y2": None}
    drag = {"mode": None, "anchor_x": 0, "anchor_y": 0, "ox": 0, "oy": 0,
            "rx1": 0, "ry1": 0, "rx2": 0, "ry2": 0}

    def to_frame(x: int, y: int):
        if display_scale == 1.0:
            return x, y
        return int(x / display_scale), int(y / display_scale)

    def to_disp(x: int, y: int):
        if display_scale == 1.0:
            return x, y
        return int(x * display_scale), int(y * display_scale)

    def has_rect():
        return rect["x1"] is not None

    def norm():
        x1, y1, x2, y2 = rect["x1"], rect["y1"], rect["x2"], rect["y2"]
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)

    def clamp_to_frame():
        rect["x1"] = max(0, min(fw - 1, rect["x1"]))
        rect["y1"] = max(0, min(fh - 1, rect["y1"]))
        rect["x2"] = max(0, min(fw - 1, rect["x2"]))
        rect["y2"] = max(0, min(fh - 1, rect["y2"]))

    def apply_aspect_corner(anchor_x: int, anchor_y: int, x: int, y: int):
        dx = x - anchor_x
        dy = y - anchor_y
        if dx == 0 or dy == 0:
            return x, y
        target_h = abs(dx) / aspect
        target_w = abs(dy) * aspect
        if target_h <= abs(dy):
            new_w = abs(dx)
            new_h = target_h
        else:
            new_w = target_w
            new_h = abs(dy)
        sx = 1 if dx >= 0 else -1
        sy = 1 if dy >= 0 else -1
        return anchor_x + int(sx * new_w), anchor_y + int(sy * new_h)

    def redraw():
        img = scaled.copy()
        if has_rect():
            x1, y1, x2, y2 = norm()
            dx1, dy1 = to_disp(x1, y1)
            dx2, dy2 = to_disp(x2, y2)
            cv2.rectangle(img, (dx1, dy1), (dx2, dy2), (0, 255, 0), 2)
            for cx, cy in [(dx1, dy1), (dx2, dy1), (dx1, dy2), (dx2, dy2)]:
                cv2.rectangle(img, (cx - 5, cy - 5), (cx + 5, cy + 5), (0, 255, 0), -1)
            if show_grid and dx2 - dx1 > 6 and dy2 - dy1 > 6:
                w3 = (dx2 - dx1) / 3
                h3 = (dy2 - dy1) / 3
                for i in (1, 2):
                    vx = int(dx1 + w3 * i)
                    hy = int(dy1 + h3 * i)
                    cv2.line(img, (vx, dy1), (vx, dy2), (0, 200, 0), 1)
                    cv2.line(img, (dx1, hy), (dx2, hy), (0, 200, 0), 1)
        cv2.imshow(WINDOW, img)

    def hit_test(x: int, y: int):
        if not has_rect():
            return None
        x1, y1, x2, y2 = norm()
        hr = HANDLE / max(display_scale, 0.001)
        corners = {"nw": (x1, y1), "ne": (x2, y1), "sw": (x1, y2), "se": (x2, y2)}
        for name, (cx, cy) in corners.items():
            if abs(x - cx) <= hr and abs(y - cy) <= hr:
                return name
        on_left = abs(x - x1) <= hr and y1 <= y <= y2
        on_right = abs(x - x2) <= hr and y1 <= y <= y2
        on_top = abs(y - y1) <= hr and x1 <= x <= x2
        on_bot = abs(y - y2) <= hr and x1 <= x <= x2
        if on_left: return "w"
        if on_right: return "e"
        if on_top: return "n"
        if on_bot: return "s"
        if x1 < x < x2 and y1 < y < y2:
            return "move"
        return None

    def on_mouse(event, dx, dy, flags, _):
        x, y = to_frame(dx, dy)
        if event == cv2.EVENT_LBUTTONDOWN:
            mode = hit_test(x, y) if has_rect() else None
            if mode is None:
                rect["x1"], rect["y1"] = x, y
                rect["x2"], rect["y2"] = x, y
                drag["mode"] = "new"
                drag["anchor_x"], drag["anchor_y"] = x, y
            else:
                drag["mode"] = mode
                drag["ox"], drag["oy"] = x, y
                drag["rx1"], drag["ry1"] = rect["x1"], rect["y1"]
                drag["rx2"], drag["ry2"] = rect["x2"], rect["y2"]
                x1, y1, x2, y2 = norm()
                if mode in ("nw",): drag["anchor_x"], drag["anchor_y"] = x2, y2
                elif mode == "ne": drag["anchor_x"], drag["anchor_y"] = x1, y2
                elif mode == "sw": drag["anchor_x"], drag["anchor_y"] = x2, y1
                elif mode == "se": drag["anchor_x"], drag["anchor_y"] = x1, y1
            redraw()
        elif event == cv2.EVENT_MOUSEMOVE and drag["mode"]:
            m = drag["mode"]
            if m == "new":
                nx, ny = x, y
                if aspect is not None:
                    nx, ny = apply_aspect_corner(drag["anchor_x"], drag["anchor_y"], x, y)
                rect["x2"], rect["y2"] = nx, ny
            elif m == "move":
                dx_ = x - drag["ox"]
                dy_ = y - drag["oy"]
                rect["x1"] = drag["rx1"] + dx_
                rect["y1"] = drag["ry1"] + dy_
                rect["x2"] = drag["rx2"] + dx_
                rect["y2"] = drag["ry2"] + dy_
            elif m in ("nw", "ne", "sw", "se"):
                nx, ny = x, y
                if aspect is not None:
                    nx, ny = apply_aspect_corner(drag["anchor_x"], drag["anchor_y"], x, y)
                if "n" in m: rect["y1"] = ny
                if "s" in m: rect["y2"] = ny
                if "w" in m: rect["x1"] = nx
                if "e" in m: rect["x2"] = nx
            else:
                if aspect is not None:
                    x1, y1, x2, y2 = norm()
                    cx_mid = (x1 + x2) / 2
                    cy_mid = (y1 + y2) / 2
                    if m in ("n", "s"):
                        if m == "n": rect["y1"] = y
                        else: rect["y2"] = y
                        nh = abs(rect["y2"] - rect["y1"])
                        nw = nh * aspect
                        rect["x1"] = int(cx_mid - nw / 2)
                        rect["x2"] = int(cx_mid + nw / 2)
                    else:
                        if m == "w": rect["x1"] = x
                        else: rect["x2"] = x
                        nw = abs(rect["x2"] - rect["x1"])
                        nh = nw / aspect
                        rect["y1"] = int(cy_mid - nh / 2)
                        rect["y2"] = int(cy_mid + nh / 2)
                else:
                    if "n" in m: rect["y1"] = y
                    if "s" in m: rect["y2"] = y
                    if "w" in m: rect["x1"] = x
                    if "e" in m: rect["x2"] = x
            redraw()
        elif event == cv2.EVENT_LBUTTONUP:
            drag["mode"] = None
            if has_rect():
                clamp_to_frame()
                redraw()

    cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(WINDOW, on_mouse)
    redraw()

    while True:
        key = cv2.waitKey(20) & 0xFF
        if key == 27:
            close_window()
            sys.exit("Cancelled.")
        if key in (13, 10) and has_rect():
            x1, y1, x2, y2 = norm()
            if x2 - x1 > 0 and y2 - y1 > 0:
                break
    close_window()
    return norm()


def close_window():
    cv2.destroyAllWindows()
    for _ in range(4):
        cv2.waitKey(1)


def finalize_crop(x1, y1, x2, y2, frame_w, frame_h, padding: int, snap: int):
    x = min(x1, x2) - padding
    y = min(y1, y2) - padding
    w = abs(x2 - x1) + 2 * padding
    h = abs(y2 - y1) + 2 * padding
    x = max(0, x)
    y = max(0, y)
    w = min(frame_w - x, w)
    h = min(frame_h - y, h)
    if snap > 1:
        x = (x // snap) * snap
        y = (y // snap) * snap
        w = (w // snap) * snap
        h = (h // snap) * snap
    w -= w % 2
    h -= h % 2
    if w <= 0 or h <= 0:
        sys.exit("Rectangle has zero area.")
    return x, y, w, h


def build_ffmpeg_cmd(args, crop, in_path: Path, out_path: Path) -> list[str]:
    cmd = [args.ffmpeg]
    cmd.append("-y" if args.overwrite else "-n")
    if not args.verbose:
        cmd += ["-loglevel", "error", "-stats"]
    if args.start is not None:
        cmd += ["-ss", str(args.start)]
    cmd += ["-i", str(in_path)]
    if args.end is not None:
        cmd += ["-to", str(args.end)]
    if args.duration is not None:
        cmd += ["-t", str(args.duration)]

    cx, cy, cw, ch = crop
    cmd += ["-vf", f"crop={cw}:{ch}:{cx}:{cy}"]

    if args.copy_video:
        cmd += ["-c:v", "copy"]
    elif args.codec:
        cmd += ["-c:v", args.codec]
    if args.crf is not None:
        cmd += ["-crf", str(args.crf)]
    if args.preset:
        cmd += ["-preset", args.preset]

    if args.no_audio:
        cmd += ["-an"]
    elif args.reencode_audio:
        pass
    else:
        cmd += ["-c:a", "copy"]

    cmd.append(str(out_path))
    return cmd


def resolve_stitch_inputs(value: str) -> list[Path]:
    p = Path(value)
    if p.is_dir():
        video_exts = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}
        files = sorted(
            f for f in p.iterdir()
            if f.is_file() and f.suffix.lower() in video_exts
        )
        if not files:
            sys.exit(f"No video files found in {p}")
        return files
    parts = [Path(s.strip()) for s in value.split(",") if s.strip()]
    if not parts:
        sys.exit("--stitch needs at least one file or a directory")
    for f in parts:
        if not f.is_file():
            sys.exit(f"File not found: {f}")
    return parts


def build_stitch_cmd(args, inputs: list[Path], list_file: Path, out_path: Path) -> list[str]:
    cmd = [args.ffmpeg]
    cmd.append("-y" if args.overwrite else "-n")
    if not args.verbose:
        cmd += ["-loglevel", "error", "-stats"]
    cmd += ["-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out_path)]
    return cmd


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="crop.py",
        description="Crop a video to a rectangle you draw on a still frame.",
    )
    p.add_argument("video", type=Path, nargs="?",
                   help="path to input video (omit when using --stitch)")

    stitch_g = p.add_argument_group("stitch")
    stitch_g.add_argument("--stitch", metavar="LIST_OR_DIR",
                          help="concat videos into one. Comma-separated paths in order, "
                               "or a directory (files joined in alphabetical order). "
                               "Output suffix: _stitched on the first file's name.")

    frame_g = p.add_argument_group("frame selection")
    fx = frame_g.add_mutually_exclusive_group()
    fx.add_argument("-t", "--time", type=float, metavar="SECONDS",
                    help="timestamp of the preview frame (default: middle)")
    fx.add_argument("--frame", type=int, metavar="N",
                    help="preview frame by index")
    fx.add_argument("--percent", type=float, metavar="P",
                    help="preview frame at P%% of duration (0-100)")

    out_g = p.add_argument_group("output")
    out_g.add_argument("-o", "--output", type=Path, metavar="PATH",
                       help="explicit output path")
    out_g.add_argument("--suffix", default="_cropped",
                       help="suffix when --output not given (default: _cropped)")
    out_g.add_argument("--overwrite", dest="overwrite", action="store_true", default=True,
                       help="overwrite output if it exists (default)")
    out_g.add_argument("--no-overwrite", dest="overwrite", action="store_false",
                       help="fail if output exists")

    crop_g = p.add_argument_group("crop shape")
    crop_g.add_argument("--rect", type=parse_rect, metavar="x:y:w:h",
                        help="skip UI; crop to these pixel coords")
    ax = crop_g.add_mutually_exclusive_group()
    ax.add_argument("--aspect", type=parse_aspect, metavar="W:H",
                    help="constrain UI rectangle to this aspect ratio")
    ax.add_argument("--square", action="store_true",
                    help="constrain to 1:1 (shortcut for --aspect 1:1)")
    crop_g.add_argument("--padding", type=int, default=0, metavar="PX",
                        help="expand chosen rectangle by N px on each side")
    crop_g.add_argument("--snap", type=int, default=0, metavar="N",
                        help="snap final crop coords to multiples of N")

    enc_g = p.add_argument_group("encoding")
    enc_g.add_argument("--codec", metavar="NAME", help="video codec (e.g. libx265)")
    enc_g.add_argument("--crf", type=int, help="quality (lower = better)")
    enc_g.add_argument("--preset", metavar="NAME", help="ffmpeg preset")
    enc_g.add_argument("--copy-video", dest="copy_video", action="store_true",
                       help="stream-copy video (will usually fail with crop filter)")
    enc_g.add_argument("--no-audio", dest="no_audio", action="store_true",
                       help="drop audio")
    enc_g.add_argument("--reencode-audio", dest="reencode_audio", action="store_true",
                       help="re-encode audio with ffmpeg defaults")

    trim_g = p.add_argument_group("trim")
    trim_g.add_argument("--start", type=float, metavar="SECONDS",
                        help="trim start of output")
    tx = trim_g.add_mutually_exclusive_group()
    tx.add_argument("--end", type=float, metavar="SECONDS",
                    help="trim end of output (absolute time)")
    tx.add_argument("--duration", type=float, metavar="SECONDS",
                    help="limit output length")

    ui_g = p.add_argument_group("ui / behavior")
    ui_g.add_argument("--no-ui", dest="no_ui", action="store_true",
                      help="require --rect; do not open a window")
    ui_g.add_argument("--show-grid", dest="show_grid", action="store_true",
                      help="overlay rule-of-thirds in the rectangle")
    ui_g.add_argument("--scale", type=float, default=1.0, metavar="FACTOR",
                      help="scale the preview window (e.g. 0.5)")
    ui_g.add_argument("--dry-run", dest="dry_run", action="store_true",
                      help="print the ffmpeg command and exit")
    ui_g.add_argument("-v", "--verbose", action="store_true",
                      help="show full ffmpeg output")
    ui_g.add_argument("--ffmpeg", default="ffmpeg", metavar="PATH",
                      help="path to ffmpeg binary")

    return p


def run_stitch(args):
    import tempfile
    inputs = resolve_stitch_inputs(args.stitch)
    first = inputs[0]
    if args.output is not None:
        out_path = args.output
    else:
        out_path = first.with_name(f"{first.stem}_stitched{first.suffix}")

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        list_file = Path(f.name)
        for inp in inputs:
            escaped = str(inp.resolve()).replace("'", r"'\''")
            f.write(f"file '{escaped}'\n")

    try:
        cmd = build_stitch_cmd(args, inputs, list_file, out_path)
        print("Running:", " ".join(cmd))
        if args.dry_run:
            return
        result = subprocess.run(cmd)
        if result.returncode != 0:
            sys.exit("ffmpeg failed. Inputs may have mismatched codecs; "
                     "try re-encoding them to a common format first.")
        print(f"Wrote {out_path}")
    finally:
        try:
            list_file.unlink()
        except OSError:
            pass


def main():
    args = build_parser().parse_args()

    if args.stitch is None and args.video is None:
        sys.exit("video is required (or pass --stitch)")
    if args.no_ui and args.rect is None and args.stitch is None:
        sys.exit("--no-ui requires --rect")
    if args.no_audio and args.reencode_audio:
        print("warning: --no-audio overrides --reencode-audio", file=sys.stderr)
    if args.copy_video:
        print("warning: --copy-video with a crop filter will usually fail", file=sys.stderr)

    ffmpeg_bin = shutil.which(args.ffmpeg) or (args.ffmpeg if Path(args.ffmpeg).is_file() else None)
    if not ffmpeg_bin:
        sys.exit(f"ffmpeg not found: {args.ffmpeg}")
    args.ffmpeg = ffmpeg_bin

    if args.stitch is not None:
        run_stitch(args)
        return

    if not args.video.is_file():
        sys.exit(f"File not found: {args.video}")

    aspect = args.aspect
    if args.square:
        aspect = 1.0

    if args.rect is not None:
        rx, ry, rw, rh = args.rect
        x1, y1, x2, y2 = rx, ry, rx + rw, ry + rh
        cap = cv2.VideoCapture(str(args.video))
        fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
    else:
        frame = get_frame(args.video, args.time, args.frame, args.percent)
        fh, fw = frame.shape[:2]
        x1, y1, x2, y2 = pick_rectangle(frame, aspect, args.show_grid, args.scale)

    crop = finalize_crop(x1, y1, x2, y2, fw, fh, args.padding, args.snap)

    if args.output is not None:
        out_path = args.output
    else:
        out_path = args.video.with_name(f"{args.video.stem}{args.suffix}{args.video.suffix}")

    cmd = build_ffmpeg_cmd(args, crop, args.video, out_path)
    print("Running:", " ".join(cmd))
    if args.dry_run:
        return

    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit("ffmpeg failed.")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
