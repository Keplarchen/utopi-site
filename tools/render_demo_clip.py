"""Render a UTOPI demo clip for the project page.

Input: a token-selection json exported by `scripts/eval_egoeye.py --drop_vis_dir`
(from the utopi-code repo), the source video, and the question/answer text.
Output: an H.264 mp4 (1280x720) and a poster jpg.

Layout: left 720x720 video frame with the selection overlay, right panel with
question, answer, legend and a live token counter.

Usage:
  python tools/render_demo_clip.py vis.json --video clip.mp4 \
      --question "..." --answer "..." --correct --out public/demo/clip1
"""
import argparse, json, subprocess, textwrap
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument("vis_json")
ap.add_argument("--video", required=True)
ap.add_argument("--question", required=True)
ap.add_argument("--answer", required=True)
ap.add_argument("--correct", action="store_true")
ap.add_argument("--budget", default="15%")
ap.add_argument("--out", required=True, help="output path without extension")
ap.add_argument("--fps", type=int, default=24)
ap.add_argument("--hold", type=float, default=2.0, help="seconds to hold the last frame")
ap.add_argument("--reveal", type=float, default=0.7, help="fraction of the clip after which the answer shows")
ap.add_argument("--ffmpeg", default="ffmpeg")
a = ap.parse_args()

d = json.load(open(a.vis_json))
H, W = d["frame_h"], d["frame_w"]
hp, wp, ts = d["h_patches"], d["w_patches"], d["token_size"]
N = hp * wp
idx = d["sampled_indices"]
F = len(idx)
keep = np.zeros(F * N, bool); keep[d["keep_flat_indices"]] = True
red = np.zeros(F * N, bool); red[d["redundant_flat_indices"]] = True
keep = keep.reshape(F, hp, wp); red = red.reshape(F, hp, wp)
gaze = d["gaze_model_px"]

CW, CH = 1280, 720          # canvas
VS = 720                    # video panel size (square)
PX = VS + 40                # text panel x
PW = CW - PX - 40           # text panel width
PAPER = (246, 244, 239); INK = (17, 17, 17); MUTED = (109, 106, 99)
LINE = (216, 213, 204); COOL = (56, 88, 255); WARM = (230, 80, 47)
YELLOW = (255, 214, 10)

def font(size, bold=False):
    try:
        return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size, index=1 if bold else 0)
    except Exception:
        return ImageFont.load_default()
F_EYE = font(15, True); F_Q = font(26, True); F_A = font(22); F_S = font(17); F_NUM = font(30, True)

def wrap(text, fnt, width, draw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=fnt) <= width: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

# Decode the video sequentially at VS x VS and keep only the sampled frames.
cmd = [a.ffmpeg, "-v", "error", "-i", a.video, "-vf",
       f"scale={VS}:{VS}:force_original_aspect_ratio=decrease,pad={VS}:{VS}:-1:-1:color=black",
       "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
want = set(idx); nbytes = VS * VS * 3; frames = {}
dec = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
n = 0
while True:
    buf = dec.stdout.read(nbytes)
    if len(buf) < nbytes: break
    if n in want: frames[n] = np.frombuffer(buf, np.uint8).reshape(VS, VS, 3)
    n += 1
    if n > max(idx): break
dec.stdout.close(); dec.kill(); dec.wait()
missing = [i for i in idx if i not in frames]
if missing:  # clamp indices past the end of the decoded stream to the last frame
    last = max(frames); frames.update({i: frames[last] for i in missing})
frames = np.stack([frames[i] for i in idx])
assert frames.shape[0] == F, f"decoded {frames.shape[0]} frames, expected {F}"

enc = subprocess.Popen([a.ffmpeg, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                        "-s", f"{CW}x{CH}", "-r", str(a.fps), "-i", "-",
                        "-c:v", "libx264", "-preset", "slow", "-crf", "26", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", a.out + ".mp4"], stdin=subprocess.PIPE)

sx, sy = VS / W, VS / H
total_kept = int(keep.sum()); total_tokens = F * N
poster = None
hold_frames = int(a.hold * a.fps)
for fi in range(F + hold_frames):
    f = min(fi, F - 1)
    img = frames[f].astype(np.float32)
    # dropped tokens: dim to 30 %; IVOC-removed foreground: red tint; kept: untouched
    kmask = np.kron(keep[f], np.ones((ts, ts), bool))[:H, :W]
    rmask = np.kron(red[f], np.ones((ts, ts), bool))[:H, :W]
    kmask = np.array(Image.fromarray(kmask).resize((VS, VS), Image.NEAREST), bool)
    rmask = np.array(Image.fromarray(rmask).resize((VS, VS), Image.NEAREST), bool)
    dim = ~kmask
    img[dim] = img[dim] * 0.3
    img[rmask] = img[rmask] * 0.5 + np.array(WARM, np.float32) * 0.5
    canvas = Image.new("RGB", (CW, CH), PAPER)
    canvas.paste(Image.fromarray(img.astype(np.uint8)), (0, 0))
    dr = ImageDraw.Draw(canvas)
    gx, gy = gaze[f]
    if gx >= 0:
        cx, cy = gx * sx, gy * sy
        dr.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], outline=YELLOW, width=4)
        dr.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=YELLOW)
    # text panel
    y = 44
    dr.text((PX, y), f"UTOPI  /  {a.budget} TOKEN BUDGET", font=F_EYE, fill=COOL); y += 34
    for ln in wrap(a.question, F_Q, PW, dr):
        dr.text((PX, y), ln, font=F_Q, fill=INK); y += 34
    y += 14; dr.line([(PX, y), (PX + PW, y)], fill=LINE, width=1); y += 22
    if fi >= a.reveal * F:
        dr.text((PX, y), "MODEL ANSWER", font=F_EYE, fill=MUTED); y += 26
        for ln in wrap(a.answer, F_A, PW, dr):
            dr.text((PX, y), ln, font=F_A, fill=INK); y += 30
        if a.correct:
            y += 6; dr.text((PX, y), "✓ correct", font=F_S, fill=COOL); y += 24
    else:
        dr.text((PX, y), "MODEL ANSWER", font=F_EYE, fill=MUTED); y += 26
        dr.text((PX, y), "watching...", font=F_A, fill=MUTED); y += 30
    # legend + counter at the bottom
    ly = CH - 150
    for col, lab in [(None, "kept tokens (full brightness)"), ((60, 60, 60), "dropped by AGTS (dimmed)"),
                     (WARM, "redundant foreground removed by IVOC"), (YELLOW, "gaze point")]:
        if col is None: dr.rectangle([PX, ly + 3, PX + 14, ly + 17], outline=INK, width=2)
        else: dr.rectangle([PX, ly + 3, PX + 14, ly + 17], fill=col)
        dr.text((PX + 24, ly), lab, font=F_S, fill=MUTED); ly += 26
    kept_f = int(keep[f].sum())
    dr.text((PX, CH - 46), f"frame {f + 1}/{F}   kept {kept_f}/{N} tokens   clip total {total_kept}/{total_tokens}",
            font=F_S, fill=MUTED)
    enc.stdin.write(canvas.tobytes())
    if fi == int(F * 0.35): poster = canvas.copy()
enc.stdin.close(); enc.wait()
assert enc.returncode == 0, "ffmpeg encode failed"
poster.save(a.out + ".jpg", quality=85)
print("wrote", a.out + ".mp4", a.out + ".jpg", f"kept {total_kept}/{total_tokens} = {100*total_kept/total_tokens:.1f}%")
