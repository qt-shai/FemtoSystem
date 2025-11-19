#!/usr/bin/env python3

# ==========================
#   CONFIGURATION CONSTANTS
# ==========================
ROWS = ["A", "B", "C", "D", "E"]
COLS = [1, 2, 3, 4, 5, 6]

OUTPUT_FILE = r"macro\\mdm_main_loop.txt"

# ==========================
#   GENERATION LOGIC
# ==========================
def generate():
    lines = []

    for row in ROWS:
        for col in COLS:
            name = f"{row}{col}"
            lines.append(f"spc note {name};")
            lines.append("coup mdm_sub_loop;")

            # shiftx normally, except last column
            if col < COLS[-1]:
                lines.append("coup shiftx;")
            else:
                lines.append("coup shiftx -5;")

            lines.append("")  # blank line between entries

        # After finishing each row:
        lines.append("coup shifty;")
        lines.append("movez 0.4;")
        lines.append("")  # space

    return "\n".join(lines)


def main():
    text = generate()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Generated: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
