import glob, os, shutil

seqA = sorted(glob.glob(r"C:\WC\SLM_bmp\seq_A\*.bmp"))
seqB = sorted(glob.glob(r"C:\WC\SLM_bmp\seq_B\*.bmp"))

out_dir = r"C:\WC\SLM_bmp\interlaced"
os.makedirs(out_dir, exist_ok=True)

n = 1
for a, b in zip(seqA, seqB):
    shutil.copy(a, os.path.join(out_dir, f"{n}.bmp")); n += 1
    shutil.copy(b, os.path.join(out_dir, f"{n}.bmp")); n += 1

print("Done, wrote", n-1, "frames")
