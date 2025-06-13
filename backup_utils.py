import os
import shutil
import datetime
import re
import filecmp
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

def folders_different(src, dst):
    comparison = filecmp.dircmp(src, dst)
    if comparison.left_only or comparison.right_only or comparison.diff_files:
        return True
    for subdir in comparison.common_dirs:
        if folders_different(os.path.join(src, subdir), os.path.join(dst, subdir)):
            return True
    return False

def sanitize_folder_name(folder_path):
    folder_name = os.path.basename(folder_path.rstrip("/\\"))
    safe_name = re.sub(r'[^A-Za-z0-9_-]', '_', folder_name)
    return safe_name

def upload_to_google_drive(local_folder_path, drive_folder_name, parent_folder_id=None):
    gauth = GoogleAuth()
    gauth.LoadCredentialsFile("credentials.txt")

    if gauth.credentials is None:
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
        gauth.Refresh()
    else:
        gauth.Authorize()

    gauth.SaveCredentialsFile("credentials.txt")
    drive = GoogleDrive(gauth)

    # Check if folder exists
    existing_folders = drive.ListFile({
        'q': f"'{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    }).GetList()

    folder = next((f for f in existing_folders if f['title'] == drive_folder_name), None)

    if not folder:
        folder_metadata = {
            'title': drive_folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [{'id': parent_folder_id}] if parent_folder_id else []
        }
        folder = drive.CreateFile(folder_metadata)
        folder.Upload()

    folder_id = folder['id']

    for root, dirs, files in os.walk(local_folder_path):
        for filename in files:
            file_path = os.path.join(root, filename)
            drive_filename = os.path.relpath(file_path, local_folder_path).replace(os.sep, "_")

            file_drive = drive.CreateFile({
                'title': drive_filename,
                'parents': [{'id': folder_id}]
            })
            file_drive.SetContentFile(file_path)
            file_drive.Upload()

def get_most_recent_source_folder(source_folders):
    most_recent_folder = None
    most_recent_mtime = 0
    for folder in source_folders:
        try:
            mtime = os.path.getmtime(folder)
            if mtime > most_recent_mtime:
                most_recent_mtime = mtime
                most_recent_folder = folder
        except Exception as e:
            print(f"Error getting modification time for {folder}: {e}")
    return most_recent_folder

def sync_local_backup(source_folders, backup_base):
    backed_up_paths = []
    most_recent_folder = get_most_recent_source_folder(source_folders)
    if not most_recent_folder:
        print("No valid source folders found.")
        return backed_up_paths

    folder_name_safe = sanitize_folder_name(most_recent_folder)

    backup_folders = [
        f for f in os.listdir(backup_base)
        if f.startswith(f"backup_{folder_name_safe}_") and os.path.isdir(os.path.join(backup_base, f))
    ]
    backup_folders.sort(reverse=True)

    last_backup_name = backup_folders[0] if backup_folders else None
    last_backup_path = os.path.join(backup_base, last_backup_name) if last_backup_name else None

    changes_detected = not last_backup_path or folders_different(most_recent_folder, last_backup_path)

    if changes_detected:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        new_backup_name = f"backup_{folder_name_safe}_{timestamp}"
        new_backup_path = os.path.join(backup_base, new_backup_name)

        print(f"Changes detected in '{most_recent_folder}' — syncing to new backup: {new_backup_name}")

        if last_backup_path and os.path.exists(last_backup_path):
            try:
                shutil.rmtree(last_backup_path)
                print(f"Deleted previous backup: {last_backup_name}")
            except Exception as e:
                print(f"Failed to delete old backup: {e}")

        try:
            shutil.copytree(most_recent_folder, new_backup_path)
            print(f"Local backup successful: {new_backup_path}")
            backed_up_paths.append(new_backup_path)
        except Exception as e:
            print(f"Local backup failed: {e}")
            exit(1)

    else:
        print(f"No changes detected for '{most_recent_folder}' — Synced.")

    return backed_up_paths

def version_local_backup(source_folders, backup_base):
    backed_up_paths = []
    
    for source_folder in source_folders:
        folder_name_safe = sanitize_folder_name(source_folder)

        # Find the latest existing backup (if any)
        backup_folders = [
            f for f in os.listdir(backup_base)
            if f.startswith(f"backup_{folder_name_safe}_") and os.path.isdir(os.path.join(backup_base, f))
        ]
        backup_folders.sort(reverse=True)

        last_backup_name = backup_folders[0] if backup_folders else None
        last_backup_path = os.path.join(backup_base, last_backup_name) if last_backup_name else None

        changes_detected = not last_backup_path or folders_different(source_folder, last_backup_path)

        if changes_detected:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            new_backup_name = f"backup_{folder_name_safe}_{timestamp}"
            new_backup_path = os.path.join(backup_base, new_backup_name)

            print(f"Changes detected in '{source_folder}' — syncing to new backup: {new_backup_name}")

            # Delete previous backup
            if last_backup_path and os.path.exists(last_backup_path):
                try:
                    shutil.rmtree(last_backup_path)
                    print(f"Deleted previous backup: {last_backup_name}")
                except Exception as e:
                    print(f"Failed to delete old backup: {e}")
                    continue

            # Create the new backup folder
            try:
                shutil.copytree(source_folder, new_backup_path)
                print(f"Local backup successful: {new_backup_path}")
                backed_up_paths.append(new_backup_path)
            except Exception as e:
                print(f"Local backup failed: {e}")
                exit(1)

        else:
            print(f"No changes detected for '{source_folder}' — backup skipped.")
            
    return backed_up_paths