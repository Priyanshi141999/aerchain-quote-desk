import os, random
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from spec import ITEMS, BUYER, PLY_GROUP
from truth import TRUTH, D_MISSING

OUT = "/home/claude/aerchain/dataset/vendors/D_sri_murugan"
os.makedirs(OUT, exist_ok=True)
FD = "/usr/share/fonts/truetype/dejavu/"
F = lambda n, s: ImageFont.truetype(FD + n, s)
HAND = ImageFont.truetype("/home/claude/aerchain/data_gen/Caveat.ttf", 46)
random.seed(7)

def inch(mm):
    return round(mm / 25.4, 1)

def d_desc(it):
    if it["form"] == "RSC":
        L, W, H = [int(x) for x in it["dims"].split(" mm")[0].split(" x ")]
        pr = "" if not it["print_colours"] else f" {it['print_colours']}clr"
        return f"{PLY_GROUP[it['board']].upper()} BOX {inch(L)}x{inch(W)}x{inch(H)} in{pr} ({it['name'].split(' carton')[0].split(' (')[0]})"
    short = {20: "3PLY E-FLUTE MAILER DIE CUT 4clr", 21: "PARTITION 12 CELL (SET)", 22: "PARTITION 6 CELL (SET)",
             23: "DIE CUT JAR TRAY", 24: "E-FLUTE INSERT (INDUCTION)", 25: "LAYER PAD 47x39 in", 26: "LAYER PAD 31.5x23.6 in",
             27: "CORNER PAD 6x6 in 5PLY", 28: "SF ROLL 39 in x 50 m", 29: "SF ROLL 47 in x 50 m"}
    return short[it["id"]]

def unit(it):
    t = TRUTH["D"][it["id"]]["raw_unit"]
    return {"INR / sq.ft": "per sq.ft", "INR / kg": "per kg"}.get(t, "per set" if it["uom"] == "set" else "per box")

PW, PH = 1700, 2350
paper = Image.new("RGB", (PW, PH), (246, 243, 232))
dr = ImageDraw.Draw(paper)
dr.text((PW // 2, 70), "SRI MURUGAN CORRUGATED BOXES", font=F("DejaVuSerif-Bold.ttf", 58), fill=(30, 30, 90), anchor="mm")
dr.text((PW // 2, 130), "Kaveripattinam, Krishnagiri Dt. - 635112   Cell: 98427 61530   GST: 33BXHPM2290L1ZK", font=F("DejaVuSans.ttf", 26), fill=(40, 40, 40), anchor="mm")
dr.line((60, 165, PW - 60, 165), fill=(30, 30, 90), width=4)
dr.text((PW // 2, 215), "RATE LIST / QUOTATION", font=F("DejaVuSans-Bold.ttf", 40), fill=(0, 0, 0), anchor="mm")
dr.text((70, 265), f"To: Kaveri Home Appliances, Hosur      Ref: Your RFQ {BUYER['rfq_no'][-13:]}      Dt: 01-10-2026", font=F("DejaVuSans.ttf", 26), fill=(0, 0, 0))

x = [70, 165, 1180, 1400, PW - 70]
y0 = 320; rh = 62
dr.rectangle((x[0], y0, x[-1], y0 + rh), fill=(220, 220, 220))
for i, h in enumerate(["S.No", "DESCRIPTION", "RATE Rs.", "UNIT"]):
    dr.text((x[i] + 12, y0 + 16), h, font=F("DejaVuSans-Bold.ttf", 28), fill=(0, 0, 0))
y = y0 + rh
rows = [it for it in ITEMS if it["id"] not in D_MISSING]
hand_marks = []
for n, it in enumerate(rows, 1):
    t = TRUTH["D"][it["id"]]
    dr.text((x[0] + 14, y + 16), str(n), font=F("DejaVuSans.ttf", 27), fill=(0, 0, 0))
    dr.text((x[1] + 12, y + 16), d_desc(it), font=F("DejaVuSans.ttf", 27), fill=(0, 0, 0))
    printed = t.get("printed_struck", t["raw"])
    dr.text((x[2] + 20, y + 16), f"{printed:,.2f}", font=F("DejaVuSansMono.ttf", 29), fill=(0, 0, 0))
    dr.text((x[3] + 12, y + 16), unit(it), font=F("DejaVuSans.ttf", 26), fill=(0, 0, 0))
    if "printed_struck" in t:
        hand_marks.append((y, t["raw"]))
    y += rh
    dr.line((x[0], y, x[-1], y), fill=(120, 120, 120), width=1)
for xx in x:
    dr.line((xx, y0, xx, y), fill=(80, 80, 80), width=2)
dr.rectangle((x[0], y0, x[-1], y), outline=(0, 0, 0), width=3)
y += 25
for line in ["* GST 18% extra.  Transport extra at actuals.  Payment 60 days.",
             "* Plates / dies: customer to supply or charged at cost.",
             "* Air cooler box & base tray (7 ply) - not in our range."]:
    dr.text((70, y), line, font=F("DejaVuSans.ttf", 26), fill=(0, 0, 0)); y += 40
dr.text((PW - 480, PH - 120), "for SRI MURUGAN CORRUGATED", font=F("DejaVuSans-Bold.ttf", 24), fill=(0, 0, 0))

# handwritten corrections in blue pen
pen = (25, 45, 160)
for (ry, val) in hand_marks:
    dr.line((x[2] + 14, ry + 34, x[2] + 120, ry + 31), fill=pen, width=5)
    dr.text((x[2] + 118, ry - 4), f"{val:.2f}", font=HAND, fill=pen)
# signature scribble + stamp
dr.text((PW - 440, PH - 205), "M. Senthil", font=HAND, fill=pen)
dr.ellipse((PW - 760, PH - 260, PW - 540, PH - 90), outline=(150, 40, 120), width=6)
dr.text((PW - 650, PH - 175), "SMCB\nKRISHNAGIRI", font=F("DejaVuSans-Bold.ttf", 22), fill=(150, 40, 120), anchor="mm", align="center")

# --- photograph it: perspective, desk, shadow, blur, noise -----------------------
src = np.array(paper)
CW, CH = 2200, 2700
desk = np.zeros((CH, CW, 3), np.uint8)
grad = np.linspace(0, 1, CW)[None, :, None]
desk[:] = (np.array([60, 82, 118]) * (0.75 + 0.35 * grad)).astype(np.uint8)  # brown wood-ish (BGR later)
noise = np.random.default_rng(3).normal(0, 9, desk.shape)
desk = np.clip(desk + noise, 0, 255).astype(np.uint8)
srcpts = np.float32([[0, 0], [PW, 0], [PW, PH], [0, PH]])
dst = np.float32([[300, 230], [1930, 290], [2020, 2510], [150, 2430]])  # angled shot
M = cv2.getPerspectiveTransform(srcpts, dst)
warped = cv2.warpPerspective(src[:, :, ::-1], M, (CW, CH), borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
mask = cv2.warpPerspective(np.ones((PH, PW), np.uint8) * 255, M, (CW, CH))
desk_bgr = desk[:, :, ::-1].copy()
out = np.where(mask[..., None] > 0, warped, desk_bgr).astype(np.float32)
# uneven lighting: shadow from phone / hand in lower-left, light falloff top-right
yy, xx = np.mgrid[0:CH, 0:CW]
light = 1.0 - 0.38 * np.exp(-(((xx - 350) / 700) ** 2 + ((yy - 2350) / 600) ** 2)) - 0.12 * (xx / CW)
out = np.clip(out * light[..., None], 0, 255).astype(np.uint8)
out = cv2.GaussianBlur(out, (3, 3), 0.9)
img = Image.fromarray(out[:, :, ::-1]).rotate(0.4, resample=Image.BICUBIC, fillcolor=(40, 55, 80))
img = img.resize((1650, 2025), Image.LANCZOS)
img.save(f"{OUT}/IMG_20261002_113412.jpg", quality=72)

email = f"""From: Senthil M <srimurugancorrugated@yahoo.co.in>
To: {BUYER['buyer_email']}
Date: Fri, 02 Oct 2026 11:40:19 +0530
Subject: Fwd: RFQ rates
Attachments: IMG_20261002_113412.jpg, ISO_certificate.pdf

Madam, sorry for delay, typing person on leave. Rate list photo attached. 2 rates corrected by hand pls take corrected one.

Your questions:
1. ISO yes - certificate attached
2. Test report yes every lot
3. 450 ton per month, running 80%
4. 10 days delivery
6. printing upto 3 colour
8. 60 days ok
9. GST 33BXHPM2290L1ZK
10. yes replace

Senthil
Sri Murugan Corrugated Boxes
"""
open(f"{OUT}/email.eml", "w").write(email)
print("D done")
