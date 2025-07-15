import re
import pytesseract
from PIL import ImageGrab, ImageOps, Image

# If Tesseract isn’t on your PATH, uncomment & adjust:
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Use PSM 6 and whitelist only the characters we care about
TESSERACT_CONFIG = r"--psm 6 -c tessedit_char_whitelist=Ch0123456789:\.-"

def preprocess_image(img: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(img)
    return ImageOps.autocontrast(gray, cutoff=2)

def normalize_text(text: str) -> str:
    t = text.upper()
    t = re.sub(r"\s*([\.:-])\s*", r"\1", t)
    for i in ("0", "1", "2"):
        t = re.sub(rf"C[\s\.:-]*H[\s\.:-]*{i}", f"CH{i}", t)
    return t

def extract_positions(text: str):
    norm = normalize_text(text)

    # for each channel: expected integer-part digit lengths
    digit_ranges = {
        "0": (3, 5),   # e.g. 2707 → 4 digits, allow 3–5
        "1": (2, 4),   # e.g. 997 → 3 digits
        "2": (2, 4),   # e.g. 649 → 3 digits
    }

    results = {}
    for n, (min_d, max_d) in digit_ranges.items():
        # find every position of "CHn" in the text
        matches = [m.end() for m in re.finditer(rf"CH{n}", norm)]
        candidates = []
        for pos in matches:
            # take a snippet right after "CHn"
            snippet = norm[pos:pos+50]
            # grab all floats in that snippet
            for s in re.findall(r"-?\d+\.\d+", snippet):
                # measure integer-part length
                int_part = s.split(".",1)[0].lstrip("-")
                if min_d <= len(int_part) <= max_d:
                    candidates.append(float(s))
        # if we got valid candidates, pick the first
        if candidates:
            results[f"Ch{n}"] = round(candidates[0], 2)
        else:
            # fallback: pick the float anywhere whose integer‐length is closest to the midrange
            all_floats = [float(s) for s in re.findall(r"-?\d+\.\d+", norm)]
            if all_floats:
                target = (min_d + max_d) / 2
                best = min(all_floats, key=lambda f: abs(len(str(int(abs(f)))) - target))
                results[f"Ch{n}"] = round(best, 2)
            else:
                results[f"Ch{n}"] = None

    return norm, results

def main():
    img = ImageGrab.grabclipboard()
    if not isinstance(img, Image.Image):
        print("No image found in clipboard.")
        return

    proc = preprocess_image(img)
    ocr = pytesseract.image_to_string(proc, config=TESSERACT_CONFIG)

    norm, positions = extract_positions(ocr)

    print("── Normalized OCR text ──")
    print(norm.strip())
    print("─────────────────────────\n")

    for ch in ("Ch0", "Ch1", "Ch2"):
        val = positions[ch]
        print(f"{ch}: {val if val is not None else 'not found'}")

if __name__ == "__main__":
    main()
