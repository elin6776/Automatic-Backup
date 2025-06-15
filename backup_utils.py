import os
import shutil
import datetime
import re
import filecmp
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import tkinter as tk
from tkinter import messagebox, simpledialog
import json

CONFIG_FILE = "backup_config.json"
def save_config(folder_listbox, backup_base, google_parent_id, upload_enabled):
    config = {
        "source_folders": folder_listbox.get(0, 'end'),
        "backup_base": backup_base.get(),
        "google_parent_id": google_parent_id.get(),
        "upload_enabled": upload_enabled.get()
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

def load_config(folder_listbox, source_folders, backup_base, google_parent_id, upload_enabled):
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            for folder in config.get("source_folders", []):
                if folder not in source_folders:
                    source_folders.append(folder)
                    folder_listbox.insert('end', folder)
            backup_base.set(config.get("backup_base", ""))
            google_parent_id.set(config.get("google_parent_id", ""))
            upload_enabled.set(config.get("upload_enabled", False))

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

def sync_backup(source_folders, backup_base):
    backed_up_paths = []

    for folder in source_folders:
        if not os.path.isdir(folder):
            print(f"Skipping invalid folder: {folder}")
            continue

        folder_name_safe = sanitize_folder_name(folder)

        backup_folders = [
            f for f in os.listdir(backup_base)
            if f.startswith(f"backup_{folder_name_safe}_") and os.path.isdir(os.path.join(backup_base, f))
        ]
        backup_folders.sort(reverse=True) 

        if backup_folders:
            last_backup_name = backup_folders[0]
            last_backup_path = os.path.join(backup_base, last_backup_name)
            
            if folders_different(folder, last_backup_path):
                print(f"\n Changes detected in '{folder}', syncing into existing backup: {last_backup_name}")
                
                try:
                    shutil.copytree(folder, last_backup_path, dirs_exist_ok=True)
                    print(f"Synced backup: {last_backup_path}")
                    backed_up_paths.append(last_backup_path)
                except Exception as e:
                    print(f"Sync failed for {folder}: {e}")
            else:
                print(f"\n✔ No changes detected in '{folder}' — skipping sync.")
        else:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            new_backup_name = f"backup_{folder_name_safe}_{timestamp}"
            new_backup_path = os.path.join(backup_base, new_backup_name)

            print(f"\n⚠ No backup found for '{folder}', creating initial backup: {new_backup_name}")

            try:
                shutil.copytree(folder, new_backup_path)
                print(f"Initial backup successful: {new_backup_path}")
                backed_up_paths.append(new_backup_path)
            except Exception as e:
                print(f"Initial backup failed for {folder}: {e}")

    return backed_up_paths

######################

def load_scheduled_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)
    
def run_backup():
    config = load_scheduled_config()
    source_folders = config.get("source_folders", [])
    backup_base = config.get("backup_base", "")
    upload_enabled = config.get("upload_enabled", False)
    google_parent_id = config.get("google_parent_id", "")

    sync_backup(source_folders, backup_base)

    if upload_enabled:
        upload_to_google_drive(backup_base, google_parent_id)