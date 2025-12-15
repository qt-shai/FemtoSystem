# Utils\plot_csv_spectrum.py
import os
import sys
import glob
import traceback

import numpy as np
import matplotlib.pyplot as plt

import pythoncom
import win32com.client


CSV_DIR = r"Q:\QT-Quantum_Optic_Lab\expData\Spectrometer"


def newest_csvs_in_folder(folder: str, n: int):
    pattern = os.path.join(folder, "*.csv")
    candidates = glob.glob(pattern)
    if not candidates:
        raise FileNotFoundError(f"No CSV files found in: {folder}")

    # sort by mtime descending, take top n
    candidates.sort(key=os.path.getmtime, reverse=True)
    return candidates[:max(1, int(n))]


def load_spectrum_csv(file_path: str):
    data = np.genfromtxt(file_path, delimiter=",")
    if data.ndim != 2 or data.shape[1] < 2:
        raise ValueError(f"CSV does not have at least two columns: {file_path}")

    data = data[data[:, 0].argsort()]  # sort by wavelength
    x_vals = data[:, 0]
    y_vals = data[:, 1]
    return x_vals, y_vals


def save_plot_png(csv_paths, out_dir: str) -> str:
    # Title uses newest file (first in list)
    newest = csv_paths[0]
    newest_base = os.path.splitext(os.path.basename(newest))[0]

    out_png = os.path.join(out_dir, "~csv_spectrum_plot.png")

    fig, ax = plt.subplots(figsize=(8.5, 4.8), dpi=200)

    # Plot newest last so it's on top? (optional)
    # We'll plot in reverse order so the newest appears last (on top)
    for fp in reversed(csv_paths):
        x, y = load_spectrum_csv(fp)
        label = os.path.splitext(os.path.basename(fp))[0]
        ax.plot(x, y, label=label)

    ax.set_title(newest_base if len(csv_paths) == 1 else f"Last {len(csv_paths)} spectra (newest: {newest_base})")
    ax.set_xlabel("Wavelength [nm]")
    ax.set_ylabel("Intensity")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.5)

    # if len(csv_paths) > 1:
    #     ax.legend(fontsize=8)
    # if len(csv_paths) > 1:
    #     # Put legend outside on the right
    #     ax.legend(
    #         loc="center left",
    #         bbox_to_anchor=(1.02, 0.5),
    #         fontsize=8,
    #         frameon=True
    #     )

    fig.tight_layout()
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)

    return out_png, newest_base

def build_alt_text(csv_paths):
    """
    Build MATLAB-friendly text containing ALL numeric data (no trimming).
    Precision: 2 decimals.
    """
    lines = []
    lines.append("% CSV Spectrum Export")
    lines.append("% Columns: wavelength_nm, intensity")
    lines.append("% Precision: 2 decimals")
    lines.append("")

    for fp in csv_paths:
        base = os.path.basename(fp)
        lines.append(f"% File: {base}")

        x, y = load_spectrum_csv(fp)
        for xv, yv in zip(x, y):
            lines.append(f"{xv:.2f}, {yv:.2f}")

        lines.append("")  # blank line between files

    return "\n".join(lines)


def insert_slide_with_image(png_path: str, title_text: str, notes_text: str):

    pythoncom.CoInitialize()
    ppt = win32com.client.Dispatch("PowerPoint.Application")

    if ppt.Presentations.Count == 0:
        raise RuntimeError("No PowerPoint presentation open!")

    pres = ppt.ActivePresentation
    slide = pres.Slides.Add(pres.Slides.Count + 1, 12)  # ppLayoutBlank

    slide_w = pres.PageSetup.SlideWidth
    slide_h = pres.PageSetup.SlideHeight

    # Title
    title = slide.Shapes.AddTextbox(1, 20, 10, slide_w - 40, 40)
    tr = title.TextFrame.TextRange
    tr.Text = title_text
    tr.Font.Size = 22
    tr.ParagraphFormat.Alignment = 1  # center

    # --- Bigger picture on slide: smaller margins ---
    margin = 25          # was 40
    top = 65             # was 70
    max_w = slide_w - 2 * margin
    max_h = slide_h - top - margin

    pic = slide.Shapes.AddPicture(
        FileName=png_path,
        LinkToFile=False,
        SaveWithDocument=True,
        Left=margin,
        Top=top
    )

    # -------------------------------
    # Speaker Notes: FULL DATA (copy/paste to MATLAB)
    # -------------------------------
    try:
        # Placeholder(2) is typically the body text of the Notes page
        notes_range = slide.NotesPage.Shapes.Placeholders(2).TextFrame.TextRange
        notes_range.Text = notes_text
    except Exception as e:
        print(f"[PPT] Failed to write speaker notes: {e}")

    try:
        pic.AlternativeText = "Spectrum plot (numeric data in Speaker Notes)."
        pic.Title = "I vs Wavelength"
    except Exception:
        pass

    pic.LockAspectRatio = True

    # Scale UP or DOWN to fill as much of the bounding box as possible
    scale = min(max_w / pic.Width, max_h / pic.Height)

    # # Make it a bit bigger (optional), but still safe
    # scale *= 1.05  # 5% boost; change to 1.10 if you want more

    # Don’t exceed the box after boost
    scale = min(scale, max_w / pic.Width*0.9, max_h / pic.Height*0.9)

    pic.Width = pic.Width * scale
    pic.Height = pic.Height * scale

    # Center horizontally
    pic.Left = (slide_w - pic.Width) / 2
    pic.Top = top


def main():
    try:
        # Usage:
        #   python plot_csv_spectrum.py            -> last 1 in CSV_DIR
        #   python plot_csv_spectrum.py 3          -> last 3 in CSV_DIR
        #   python plot_csv_spectrum.py 3 <folder> -> last 3 in folder
        #   python plot_csv_spectrum.py <file.csv> -> plot that file only
        args = sys.argv[1:]

        n = 1
        folder = CSV_DIR
        explicit_file = None

        if len(args) >= 1:
            # if first arg is a csv file
            if os.path.isfile(args[0]) and args[0].lower().endswith(".csv"):
                explicit_file = args[0]
            else:
                # else treat it as N
                try:
                    n = int(args[0])
                except Exception:
                    n = 1

        if len(args) >= 2 and os.path.isdir(args[1]):
            folder = args[1]

        if explicit_file:
            csv_paths = [explicit_file]
        else:
            csv_paths = newest_csvs_in_folder(folder, n)

        print(f"runcsv: using {len(csv_paths)} newest CSV(s):")
        for fp in csv_paths:
            print(f"  - {fp}")

        out_dir = os.path.dirname(csv_paths[0]) or folder
        png_path, newest_base = save_plot_png(csv_paths, out_dir=out_dir)
        print(f"Saved plot PNG: {png_path}")

        # Slide title: newest file base (no folder, no extension)
        notes_text = build_alt_text(csv_paths)
        insert_slide_with_image(png_path, newest_base if len(csv_paths) == 1 else f"{newest_base} (+{len(csv_paths)-1})", notes_text)
        print("Slide added to the open PowerPoint.")
        return 0

    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
