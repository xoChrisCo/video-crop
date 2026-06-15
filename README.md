# video-crop

Interactive video cropper: pick a frame, drag a rectangle, get a cropped video.

A tiny Python CLI that opens a still frame from your video, lets you draw and adjust a crop rectangle with the mouse, then crops the entire video to that region using `ffmpeg`. Audio is preserved.

## How it works

1. Extracts one frame from the video (middle by default, or at a timestamp you pass).
2. Opens an OpenCV window so you can drag out a rectangle and fine-tune it.
3. Calls `ffmpeg` with a `crop` filter to produce `<name>_cropped.<ext>` next to the original.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) — for environment & dependency management
- `ffmpeg` available on your `PATH`
  - macOS: `brew install ffmpeg`
  - Debian/Ubuntu: `sudo apt install ffmpeg`
  - Windows: [ffmpeg.org/download](https://ffmpeg.org/download.html)

## Install

```sh
git clone https://github.com/<you>/video-crop.git
cd video-crop
uv sync
```

## Usage

```sh
uv run python crop.py <video_path> [seconds]
```

| Argument        | Description                                                                  |
| --------------- | ---------------------------------------------------------------------------- |
| `<video_path>`  | Path to the input video.                                                     |
| `[seconds]`     | Optional. Timestamp of the frame to draw on. Defaults to the middle frame.   |

### Drawing the crop

A window opens showing the chosen frame:

- **Drag on empty space** to draw a rectangle.
- **Drag a corner or edge** to resize.
- **Drag inside the rectangle** to move it.
- **Enter** to submit and start cropping.
- **Esc** to abort.

### Output

The cropped file is written next to the input with a `_cropped` suffix:

```
clip.mp4  →  clip_cropped.mp4
```

Video is re-encoded with `ffmpeg`'s defaults (typically libx264). Audio is copied as-is.

## Example

```sh
uv run python crop.py clip.mp4 5
# Opens the frame at 5s. Drag a rectangle, press Enter.
# → clip_cropped.mp4
```

## Notes

- Crop dimensions are rounded down to even numbers so common encoders (H.264) accept them.
- If the bounding box has zero area, the script aborts without writing a file.
- Tested on macOS. Should work anywhere OpenCV's GUI and `ffmpeg` work.

## License

MIT
