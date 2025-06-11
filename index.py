import os
import shutil
import datetime
import filecmp

source_folder = r""
backup_base = r""

backup_folders = [
    f for f in os.listdir(backup_base)
    if f.startswith("backup_") and os.path.isdir(os.path.join(backup_base, f))
]
backup_folders.sort(reverse=True)

last_backup_path = None

if backup_folders:
    last_backup_path = os.path.join(backup_base, backup_folders[0])

def folders_different(src, dst):
    comparison = filecmp.dircmp(src, dst)
    if comparison.left_only or comparison.right_only or comparison.diff_files:
        return True
    for subdir in comparison.common_dirs:
        if folders_different(
            os.path.join(src, subdir), os.path.join(dst, subdir)
        ):
            return True
    return False

timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
new_backup_path = os.path.join(backup_base, f"backup_{timestamp}")

if last_backup_path and not folders_different(source_folder, last_backup_path):
    print("No changes detected — backup skipped.")
else:
    if last_backup_path:
        print("Changes detected — replacing previous backup.")
        shutil.rmtree(last_backup_path)

    try:
        shutil.copytree(source_folder, new_backup_path)
        print(f"Backup successful: {new_backup_path}")
    except Exception as e:
        print(f"Backup failed: {e}")
