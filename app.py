import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import datetime
import os

from backup_utils import sync_local_backup, upload_to_google_drive

class BackupApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Backup Sync Tool")
        self.root.geometry("600x500")

        self.source_folders = []
        self.backup_base = tk.StringVar()
        self.google_parent_id = tk.StringVar()
        self.upload_enabled = tk.BooleanVar()

        # Create Notebook (Tabs container)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True)

        # Tab 1: Backup Tool UI
        self.tab1 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab1, text="Backup")

        # Tab 2: Placeholder for another tab
        self.tab2 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab2, text="Another Tab")

        self.create_backup_tab(self.tab1)
        self.create_another_tab(self.tab2)

    def create_backup_tab(self, parent):
        # Source Folder Selection
        tk.Label(parent, text="Source Folders").pack(pady=5)
        
        self.folder_listbox = tk.Listbox(parent, height=6, width=60)
        self.folder_listbox.pack()

        btn_frame = tk.Frame(parent)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Add Folder", command=self.add_source_folder).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Remove Selected", command=self.remove_selected_folder).pack(side=tk.LEFT, padx=5)

        tk.Label(parent, text="Backup Folder").pack(pady=5)
        tk.Entry(parent, textvariable=self.backup_base, width=60).pack()
        tk.Button(parent, text="Browse", command=self.browse_backup).pack(pady=5)

        tk.Checkbutton(parent, text="Upload to Google Drive", variable=self.upload_enabled).pack(pady=10)
        tk.Label(parent, text="(Required) Google Drive Parent Folder ID").pack()
        tk.Entry(parent, textvariable=self.google_parent_id, width=60).pack()

        tk.Button(parent, text="Start Backup", command=self.run_backup_thread).pack(pady=20)

        self.status_label = tk.Label(parent, text="Status: Ready")
        self.status_label.pack()

        self.last_backup_time = tk.Label(parent, text="Last Backup: Not yet")
        self.last_backup_time.pack()

    def create_another_tab(self, parent):
        # Example content for second tab
        tk.Label(parent, text="This is another tab!").pack(pady=20)
        tk.Button(parent, text="Click me", command=lambda: messagebox.showinfo("Hello", "You clicked the button in the second tab!")).pack()

    # (rest of your methods unchanged)
    def add_source_folder(self):
        folder = filedialog.askdirectory()
        if folder and folder not in self.source_folders:
            self.source_folders.append(folder)
            self.folder_listbox.insert(tk.END, folder)

    def remove_selected_folder(self):
        selected_indices = self.folder_listbox.curselection()
        for i in reversed(selected_indices):
            folder = self.folder_listbox.get(i)
            self.source_folders.remove(folder)
            self.folder_listbox.delete(i)

    def browse_backup(self):
        folder = filedialog.askdirectory()
        if folder:
            self.backup_base.set(folder)

    def run_backup_thread(self):
        threading.Thread(target=self.run_backup, daemon=True).start()

    def run_backup(self):
        if not self.source_folders:
            messagebox.showerror("Missing Info", "Add at least one source folder.")
            return

        dst = self.backup_base.get()
        if not dst:
            messagebox.showerror("Missing Info", "Select backup folder.")
            return

        self.status_label.config(text="Status: Backing up...")

        try:
            backup_paths = sync_local_backup(self.source_folders, dst)
            self.status_label.config(text="Status: Local backup complete")

            if self.upload_enabled.get():
                for backup_path in backup_paths:
                    folder_name = os.path.basename(backup_path)
                    upload_to_google_drive(backup_path, folder_name, self.google_parent_id.get())
                self.status_label.config(text="Status: Uploaded to Google Drive ✔")

            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.last_backup_time.config(text=f"Last Backup: {now}")

        except Exception as e:
            self.status_label.config(text="Status: Failed ❌")
            messagebox.showerror("Backup Error", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = BackupApp(root)
    root.mainloop()
