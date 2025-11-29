import argparse
import os
import shutil
import subprocess
from collections import deque

exclude_dirs = ["/proc", "/sys", "/dev", "/system"]
OUTPUT_DIR = "dump_enc"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def parse_args():
    parser = argparse.ArgumentParser(description="Работа с эмуляторами Android")
    parser.add_argument(
        "-s", "--emulator", 
        required=True, 
        help="Идентификатор эмулятора или устройства (например, emulator-5554)"
    )
    return parser.parse_args()

def main():
    args = parse_args()

    emulator_id = args.emulator

    print(f"[*] Removing virus apk from emulator {emulator_id}...")
    subprocess.run(
        ["adb", "-s", args.emulator, "shell", "pm uninstall org.simplelocker"],
        capture_output=True,
        text=True
    )

    print("[*] Searching for encrypted files...")

    queue = deque(["/"])
    files = []

    while queue:
        cur = queue.popleft()

        result = subprocess.run(
            ["adb", "-s", emulator_id, "shell", f"ls \"{cur}\""],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"[-] Failed to read directory {cur}")
            continue

        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.count("/") > 1:
                continue

            full_path = cur.rstrip("/") + "/" + line

            if line.endswith(".enc"):
                files.append(full_path)
                continue

            if "." not in line and full_path not in exclude_dirs:
                queue.append(full_path)

    if not files:
        shutil.rmtree(OUTPUT_DIR)
        print("[-] .enc files not found.")
        exit()

    print(f"[+] Found {len(files)} .enc files")

    local_map = {}

    for path in files:
        safe_name = path.replace("/", "_")
        local_path = os.path.join(OUTPUT_DIR, safe_name)

        subprocess.run(
            ["adb", "-s", emulator_id, "pull", path, local_path],
            capture_output=True,
            text=True
        )

        local_map[local_path] = path

    print("[*] Decrypting...")

    subprocess.run(
        ["make", "android_decrypt", f"input={OUTPUT_DIR}", f"output={OUTPUT_DIR}"],
        capture_output=True,
        text=True
    )
    subprocess.run(
        ["make", "android_clean"],
        capture_output=True,
        text=True
    )

    print("[*] Returning decrypted files to device…")

    for local_in, original_remote in local_map.items():
        decrypted = local_in.replace(".enc", "")
        if not os.path.exists(decrypted):
            print(f"[-] No decrypted file: {decrypted}")
            continue

        remote_dir = os.path.dirname(original_remote)
        subprocess.run(
            ["adb", "-s", emulator_id, "shell", f"mkdir -p \"{remote_dir}\""],
            capture_output=True,
            text=True
        )
        subprocess.run(
            ["adb", "-s", emulator_id, "push", decrypted, original_remote.replace(".enc", "")],
            capture_output=True,
            text=True
        )
        subprocess.run(
            ["adb", "-s", emulator_id, "shell", f"rm \"{original_remote}\""],
            capture_output=True,
            text=True
        )

    shutil.rmtree(OUTPUT_DIR)

    print("[+] Done! All files have been processed and returned.")

if __name__ == "__main__":
    main()
