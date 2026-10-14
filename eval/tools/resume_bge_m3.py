import hashlib
import shutil
import time
import urllib.request
from pathlib import Path

URL = "https://huggingface.co/BAAI/bge-m3/resolve/main/pytorch_model.bin"
TOTAL_SIZE = 2271145830
EXPECTED_SHA256 = "b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38"

CACHE_DIR = Path(
    r"C:\Users\Ahmed Abdelghani\.cache\huggingface\hub\models--BAAI--bge-m3"
)
BLOBS_DIR = CACHE_DIR / "blobs"
SNAPSHOT_DIR = CACHE_DIR / "snapshots" / "5617a9f61b028005a4858fdac845db406aefb181"

FINAL_BLOB = BLOBS_DIR / EXPECTED_SHA256
PARTIAL_FILE = BLOBS_DIR / f"{EXPECTED_SHA256}.cb56c977.incomplete"

if FINAL_BLOB.exists() and FINAL_BLOB.stat().st_size == TOTAL_SIZE:
    print(f"[INFO] Final blob already exists ({TOTAL_SIZE} bytes).")
else:
    current_size = PARTIAL_FILE.stat().st_size if PARTIAL_FILE.exists() else 0
    print(
        f"[INFO] Resuming download from byte {current_size} / {TOTAL_SIZE} ({current_size / TOTAL_SIZE * 100:.1f}%)..."
    )

    req = urllib.request.Request(URL)
    req.add_header("Range", f"bytes={current_size}-")
    req.add_header("User-Agent", "Rafiq-Agent/1.0")

    start_time = time.time()
    last_print = time.time()
    downloaded_this_session = 0

    with urllib.request.urlopen(req, timeout=30) as resp, open(PARTIAL_FILE, "ab") as f:
        while True:
            chunk = resp.read(1024 * 1024 * 4)  # 4MB chunks
            if not chunk:
                break
            f.write(chunk)
            downloaded_this_session += len(chunk)
            current_size += len(chunk)
            now = time.time()
            if now - last_print >= 5.0:
                speed_mb = (downloaded_this_session / (1024 * 1024)) / (
                    now - start_time
                )
                pct = current_size / TOTAL_SIZE * 100
                print(
                    f"[{pct:.1f}%] {current_size}/{TOTAL_SIZE} bytes ({speed_mb:.2f} MB/s)..."
                )
                last_print = now

    print("[INFO] Download finished. Verifying SHA256...")
    h = hashlib.sha256()
    with open(PARTIAL_FILE, "rb") as f:
        while chunk := f.read(1024 * 1024 * 8):
            h.update(chunk)
    digest = h.hexdigest()
    print(f"Calculated SHA256: {digest}")
    if digest != EXPECTED_SHA256:
        raise ValueError(f"SHA256 mismatch! Expected {EXPECTED_SHA256}, got {digest}")

    PARTIAL_FILE.rename(FINAL_BLOB)
    print(f"[SUCCESS] Blob saved to {FINAL_BLOB}")

# Link or copy into snapshot
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
dest = SNAPSHOT_DIR / "pytorch_model.bin"
if not dest.exists():
    print(f"[INFO] Copying blob to snapshot destination {dest}...")
    shutil.copyfile(FINAL_BLOB, dest)
    print(f"[SUCCESS] Copied to {dest}")
else:
    print(f"[INFO] Snapshot file already exists at {dest}")

print("[ALL DONE] BAAI/bge-m3 weights fully ready!")
