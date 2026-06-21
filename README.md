# video-crop

Interactive video cropper: pick a frame, drag a rectangle, get a cropped video. Also stitches videos end-to-end.

A tiny Python CLI that opens a still frame from your video, lets you draw and adjust a crop rectangle with the mouse, then crops the entire video to that region using `ffmpeg`. Audio is preserved by default.

## How it works

1. Extracts one frame from the video (middle by default, or wherever you point it).
2. Opens an OpenCV window so you can drag out a rectangle and fine-tune it.
3. Calls `ffmpeg` with a `crop` filter (and any trim/encode flags) to produce `<name>_cropped.<ext>` next to the original.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) — for environment & dependency management
- `ffmpeg` on your `PATH`
  - macOS: `brew install ffmpeg`
  - Debian/Ubuntu: `sudo apt install ffmpeg`
  - Windows: [ffmpeg.org/download](https://ffmpeg.org/download.html)

## Install

```sh
git clone https://github.com/xoChrisCo/video-crop.git
cd video-crop
uv sync
```

## Usage

```sh
uv run python crop.py <video> [flags]
uv run python crop.py --stitch <list-or-dir> [flags]
uv run python crop.py --help
```

### Drawing the crop

A window opens showing the chosen frame:

- **Drag on empty space** to draw a rectangle.
- **Drag a corner or edge** to resize.
- **Drag inside the rectangle** to move it.
- **Enter** to submit, **Esc** to abort.

### Output

Default output is written next to the input with a suffix:

```
clip.mp4  →  clip_cropped.mp4
first.mp4 → first_stitched.mp4   (when using --stitch)
```

Override with `-o/--output PATH` or change the suffix with `--suffix STR`.

## Flags

### Frame selection (mutually exclusive)
| Flag | Description |
| ---- | ----------- |
| `-t, --time SECONDS` | Timestamp of the preview frame. |
| `--frame N` | Preview by frame index. |
| `--percent P` | Preview at P% of the duration (0–100). |

Default: middle of the video.

### Screenshot
| Flag | Description |
| ---- | ----------- |
| `--screenshot` | Save a frame as an image and exit (no cropping). With a frame selector (`-t`/`--frame`/`--percent`) or `-o`, saves that single frame — defaults to `<video>_<tag>.png` beside the source, where `<tag>` reflects the frame selection (format from the `-o` extension, default `.png`). With **no selector and no `-o`**, extracts frames to `<video>_frames/` (`frame_000000.png`, …) at the `--every` interval. Respects `-o` and `--dry-run`. |
| `--every SECONDS` | When extracting to `<video>_frames/`, sample one frame every N seconds (default: `1`), or pass `all` for every frame. |

### Output
| Flag | Description |
| ---- | ----------- |
| `-o, --output PATH` | Explicit output path. |
| `--suffix STR` | Suffix when `-o` isn't given. Default: `_cropped` (or `_stitched` for stitch). |
| `--overwrite / --no-overwrite` | Pass `-y` or `-n` to ffmpeg. Default: overwrite. |

### Crop shape
| Flag | Description |
| ---- | ----------- |
| `--rect x:y:w:h` | Skip the UI; crop to these pixel coords. |
| `--aspect W:H` | Constrain the UI rectangle to this aspect ratio. |
| `--square` | Shortcut for `--aspect 1:1`. |
| `--padding PX` | Expand the chosen rectangle by N pixels each side. |
| `--snap N` | Round final crop coords to multiples of N. |

### Encoding
| Flag | Description |
| ---- | ----------- |
| `--codec NAME` | Video codec (e.g. `libx265`). |
| `--crf N` | Quality (lower = better). |
| `--preset NAME` | ffmpeg preset (e.g. `fast`, `slow`). |
| `--copy-video` | Stream-copy video. Usually fails with a crop filter — escape hatch only. |
| `--no-audio` | Drop the audio track. |
| `--reencode-audio` | Re-encode audio with ffmpeg defaults instead of copying. |

### Trim
| Flag | Description |
| ---- | ----------- |
| `--start SECONDS` | Trim start of output. |
| `--end SECONDS` | Trim end (absolute time). Mutually exclusive with `--duration`. |
| `--duration SECONDS` | Limit output length. |

### Stitch
| Flag | Description |
| ---- | ----------- |
| `--stitch LIST_OR_DIR` | Concat videos end-to-end. Comma-separated paths in order, or a directory (joined alphabetically). Output is `<first>_stitched.<ext>`. |
| `--reencode` / `--no-reencode` | Force re-encode (normalize size/fps/codec) or force fast stream-copy. Default: auto — copy when inputs are uniform, re-encode otherwise. |
| `--fps N` | Target frame rate when re-encoding (default: 30). |
| `--stitch-size WxH` | Target size when re-encoding (default: largest input; smaller clips are letterboxed to fit). |

By default stitch probes the inputs with `ffprobe`. If they share codec, resolution, and timebase it stream-copies (instant, lossless). If they differ — different resolutions, frame rates, or variable-frame-rate recordings — a plain `-c copy` concat plays only the first clip and then freezes on its last frame, so the tool automatically re-encodes through the concat filter to normalize them. Pass `--no-reencode` to override.

### UI / behavior
| Flag | Description |
| ---- | ----------- |
| `--no-ui` | Require `--rect`; don't open a window. |
| `--show-grid` | Overlay rule-of-thirds inside the rectangle. |
| `--scale FACTOR` | Scale the preview window (e.g. `0.5` for 4K sources). Clicks map back to full resolution. |
| `--dry-run` | Print the ffmpeg command and exit. |
| `-v, --verbose` | Show full ffmpeg output. |
| `--ffmpeg PATH` | Override the ffmpeg binary. |
| `-h, --help` | Show help. |

## Examples

```sh
# Default: middle frame, draw freely
uv run python crop.py clip.mp4

# Pick the frame at 5s
uv run python crop.py clip.mp4 -t 5

# Grab a screenshot at 1:30 (90s), no cropping
uv run python crop.py clip.mp4 --screenshot -t 90

# Screenshot to a specific file
uv run python crop.py clip.mp4 --screenshot still.jpg --percent 25

# Extract one frame per second to clip_frames/
uv run python crop.py clip.mp4 --screenshot

# One frame every 5 seconds
uv run python crop.py clip.mp4 --screenshot --every 5

# Every single frame
uv run python crop.py clip.mp4 --screenshot --every all

# Headless crop to exact coords
uv run python crop.py clip.mp4 --rect 100:50:640:360 --no-ui

# 16:9-locked crop with rule-of-thirds overlay
uv run python crop.py clip.mp4 --aspect 16:9 --show-grid

# Crop, trim from 2s for 3s, drop audio, smaller file
uv run python crop.py clip.mp4 --start 2 --duration 3 --no-audio --crf 28 --preset fast

# Stitch a folder of clips in alphabetical order
uv run python crop.py --stitch ./clips/

# Stitch specific files in order
uv run python crop.py --stitch intro.mp4,part1.mp4,outro.mp4 -o final.mp4

# Stitch mismatched clips, normalizing to 1080x1920 at 30fps
uv run python crop.py --stitch ./clips/ --reencode --stitch-size 1080x1920 --fps 30
```

## Notes

- Crop dimensions are rounded down to even numbers so common encoders (H.264) accept them.
- Stitching uses `ffmpeg -f concat -c copy` (no re-encode). If inputs have different codecs, resolutions, or framerates, ffmpeg will refuse — normalize them first.
- Tested on macOS. Should work anywhere OpenCV's GUI and `ffmpeg` work.

## License

MIT
