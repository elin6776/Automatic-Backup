import os
import shutil
import datetime
import filecmp
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from dotenv import load_dotenv

def folders_different(src, dst):
    comparison = filecmp.dircmp(src, dst)
    if comparison.left_only or comparison.right_only or comparison.diff_files:
        return True
    for subdir in comparison.common_dirs:
        if folders_different(os.path.join(src, subdir), os.path.join(dst, subdir)):
            return True
    return False

def upload_folder_to_drive(local_folder_path, drive_folder_name, parent_drive_folder_id=None):
    from pydrive.auth import GoogleAuth
    from pydrive.drive import GoogleDrive
    import re

    gauth = GoogleAuth()
    gauth.LocalWebserverAuth()
    drive = GoogleDrive(gauth)

    # Create folder
    folder_metadata = {
        'title': drive_folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    if parent_drive_folder_id:
        folder_metadata['parents'] = [{'id': parent_drive_folder_id}]

    drive_folder = drive.CreateFile(folder_metadata)
    drive_folder.Upload()
    print(f"Created folder '{drive_folder_name}' on Google Drive with ID: {drive_folder['id']}")

    # Upload
    for root, dirs, files in os.walk(local_folder_path):
        for filename in files:
            file_path = os.path.join(root, filename)
            relative_path = os.path.relpath(file_path, local_folder_path)
            drive_filename = relative_path.replace(os.sep, "_")

            file_drive = drive.CreateFile({
                'title': drive_filename,
                'parents': [{'id': drive_folder['id']}]
            })
            file_drive.SetContentFile(file_path)
            file_drive.Upload()
            print(f"Uploaded '{drive_filename}' to Google Drive folder '{drive_folder_name}'")

    print("Upload complete.")

    # Delete if > 5
    if parent_drive_folder_id:
        folder_list = drive.ListFile({
            'q': f"'{parent_drive_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        }).GetList()

        backup_folders = [
            f for f in folder_list if re.match(r"backup_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}", f['title'])
        ]
        backup_folders.sort(key=lambda f: f['title'])

        if len(backup_folders) > 5:
            num_to_delete = len(backup_folders) - 5
            for i in range(num_to_delete):
                try:
                    backup_folders[i].Delete()
                    print(f"Deleted old Google Drive backup folder: {backup_folders[i]['title']}")
                except Exception as e:
                    print(f"Failed to delete folder '{backup_folders[i]['title']}': {e}")

load_dotenv()  
source_folder = os.getenv("SOURCE_FOLDER")
backup_base = os.getenv("BACKUP_BASE")
google_drive_parent_folder_id = os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID")

# Sorts backup folders 
backup_folders = [
    f for f in os.listdir(backup_base)
    if f.startswith("backup_") and os.path.isdir(os.path.join(backup_base, f))
]
backup_folders.sort(reverse=True)

# Find latest backup and see any changes
last_backup_path = os.path.join(backup_base, backup_folders[0]) if backup_folders else None
changes_detected = not last_backup_path or folders_different(source_folder, last_backup_path)

if changes_detected:
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    new_backup_path = os.path.join(backup_base, f"backup_{timestamp}")
    print("Changes detected — backing up and uploading to Google Drive.")

    try:
        shutil.copytree(source_folder, new_backup_path)
        print(f"Local backup successful: {new_backup_path}")
    except Exception as e:
        print(f"Local backup failed: {e}")
        exit(1)

    try:
        backups = [f for f in os.listdir(backup_base) if f.startswith("backup_")]
        backups.sort() 

        if len(backups) > 5:
            num_to_delete = len(backups) - 5
            for i in range(num_to_delete):
                oldest = os.path.join(backup_base, backups[i])
                shutil.rmtree(oldest)
                print(f"Deleted old backup: {oldest}")
    except Exception as e:
        print(f"Error managing backup rotation: {e}")

    try:
        upload_folder_to_drive(new_backup_path, os.path.basename(new_backup_path), google_drive_parent_folder_id)
    except Exception as e:
        print(f"Google Drive upload failed: {e}")

else:
    print("No changes detected — backup skipped.")