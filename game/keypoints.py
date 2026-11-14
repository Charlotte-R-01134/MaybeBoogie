import json
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from scipy.signal import savgol_filter

TARGET_FPS = 8       # samples per second of video
MIN_CONF = 0.4
INTERP_CONF = 0.5
MAX_GAP_S = 0.4 
MAX_JUMP = 0.25 
MIN_JOINTS = 6
IMGSZ = 480


def _device():
    if torch.cuda.is_available():
        return 0, True
    if torch.backends.mps.is_available():
        return "mps", False
    return "cpu", False


_model = None
_lock = threading.Lock()


def _get_model():
    """Load lazily so Django startup (and the autoreloader) doesn't load weights."""
    global _model
    with _lock:
        if _model is None:
            from ultralytics import YOLO
            device, _ = _device()
            _model = YOLO("yolo11m-pose.pt" if device != "cpu" else "yolo11s-pose.pt")
        return _model


def _pick_dancer(boxes, prev):
    if prev is not None:
        d = np.hypot(boxes[:, 0] - prev[0], boxes[:, 1] - prev[1])
        i = int(np.argmin(d))
        if d[i] < MAX_JUMP:
            return i
    return int(np.argmax(boxes[:, 2] * boxes[:, 3]))


def _clean(raw, fps):
    a = np.stack(raw)
    n = len(a)
    xy, conf = a[:, :, :2].copy(), a[:, :, 2].copy()
    missing = np.isnan(conf) | (conf < MIN_CONF)
    xy[missing] = np.nan

    t = np.arange(n)
    max_gap = max(1, int(MAX_GAP_S * fps))
    win, order = (5, 2) if fps >= 12 else (3, 1)   # lighter smoothing at low sample rates
    if n < win:
        win = 0
    out_xy, out_conf = np.zeros_like(xy), np.zeros_like(conf)
    for j in range(17):
        ok = ~missing[:, j]
        if ok.sum() < 3:
            continue
        idx = t[ok]
        keep = np.abs(t[:, None] - idx[None, :]).min(axis=1) <= max_gap   # near a real sample?
        for axis in (0, 1):
            s = np.interp(t, idx, xy[ok, j, axis])
            if win:
                s = savgol_filter(s, win, order) # smoothing cv magic
            out_xy[:, j, axis] = np.where(keep, s, 0.0)
        out_conf[:, j] = np.where(keep, np.where(ok, conf[:, j], INTERP_CONF), 0.0)
    return out_xy, out_conf


def extract_keypoints(video_path, on_progress=None):
    cap = cv2.VideoCapture(str(video_path))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w, h = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    cap.release()

    stride = max(1, round(src_fps / TARGET_FPS))
    fps = src_fps / stride
    device, half = _device()

    stream = _get_model().predict(
        str(video_path), stream=True, vid_stride=stride, imgsz=IMGSZ,
        device=device, half=half, conf=0.3, max_det=8, verbose=False,
    )

    raw, prev = [], None
    for i, r in enumerate(stream):
        pose = np.full((17, 3), np.nan, dtype=np.float32)
        if r.boxes is not None and len(r.boxes) and r.keypoints is not None:
            boxes = r.boxes.xywhn.cpu().numpy()
            k = _pick_dancer(boxes, prev)
            prev = boxes[k, :2]
            pose[:, :2] = r.keypoints.xyn[k].cpu().numpy()
            pose[:, 2] = r.keypoints.conf[k].cpu().numpy() if r.keypoints.conf is not None else 1.0
        raw.append(pose)
        if on_progress and total and i % 10 == 0:
            on_progress(min(1.0, i * stride / total))

    if not raw:
        return {"aspect": round(w / h, 4), "fps": round(fps, 2), "frames": []}

    xy, conf = _clean(raw, fps)
    frames = []
    for i in range(len(raw)):
        if (conf[i] > 0).sum() < MIN_JOINTS:
            j = None
        else:
            j = [[round(float(xy[i, k, 0]), 4), round(float(xy[i, k, 1]), 4), round(float(conf[i, k]), 2)]
                 for k in range(17)]
        frames.append({"t": round(i * stride / src_fps, 3), "j": j})
    return {"aspect": round(w / h, 4), "fps": round(fps, 2), "frames": frames}


if __name__ == "__main__":
    start = time.time()
    data = extract_keypoints(sys.argv[1], lambda f: print(f"\r{f:.0%}", end="", flush=True))
    with_dancer = sum(f["j"] is not None for f in data["frames"])
    print(f"\n{with_dancer}/{len(data['frames'])} frames have a dancer. Took {time.time() - start:.0f}s")
    Path("keypoints_test.json").write_text(json.dumps(data, separators=(",", ":")))