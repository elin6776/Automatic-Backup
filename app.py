import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import datetime
import os
import sys
import subprocess

from backup_utils import upload_to_google_drive, sync_backup, save_config, load_config, run_backup, load_scheduled_config

class BackupApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Backup Sync Tool")
        self.root.geometry("600x500")

        self.source_folders = []
        self.backup_base = tk.StringVar()
        self.google_parent_id = tk.StringVar()
        self.upload_enabled = tk.BooleanVar()

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True)
    
        self.tab1 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab1, text="Sync Backup")

        self.tab3 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab3, text="Scheduler")

        self.create_backup_tab(self.tab1)
        self.create_scheduler_tab(self.tab3)
        self.notebook.pack(expand=1, fill='both')

    # Back up Tab
    def create_backup_tab(self, parent):
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
        load_config(self.folder_listbox, self.source_folders, self.backup_base, self.google_parent_id, self.upload_enabled)

    def add_source_folder(self):
        folder = filedialog.askdirectory()
        if folder and folder not in self.source_folders:
            self.source_folders.append(folder)
            self.folder_listbox.insert(tk.END, folder)
        save_config(self.folder_listbox, self.backup_base, self.google_parent_id, self.upload_enabled)

    def remove_selected_folder(self):
        selected_indices = self.folder_listbox.curselection()
        for i in reversed(selected_indices):
            folder = self.folder_listbox.get(i)
            self.source_folders.remove(folder)
            self.folder_listbox.delete(i)
        save_config(self.folder_listbox, self.backup_base, self.google_parent_id, self.upload_enabled)

    def browse_backup(self):
        folder = filedialog.askdirectory()
        if folder:
            self.backup_base.set(folder)
            save_config(self.folder_listbox, self.backup_base, self.google_parent_id, self.upload_enabled)

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
            backup_paths = sync_backup(self.source_folders, dst)
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

    # Schedule Tab
    def create_scheduler_tab(self, parent):
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        tk.Label(parent, text="Schedule Auto Backup").pack(pady=10)

        self.log_text = tk.Text(parent, height=6, width=60)
        self.log_text.pack(pady=10)

        tk.Label(parent, text="Select Time (24-hour):").pack()

        time_frame = tk.Frame(parent)
        time_frame.pack(pady=5)

        # Hour dropdown (00 to 23)
        self.hour_var = tk.StringVar()
        hour_choices = [f"{h:02d}" for h in range(24)]
        self.hour_combo = ttk.Combobox(time_frame, values=hour_choices, width=3, textvariable=self.hour_var, state="readonly")
        self.hour_combo.current(0)
        self.hour_combo.pack(side=tk.LEFT)

        tk.Label(time_frame, text=":").pack(side=tk.LEFT, padx=2)

        # Minute dropdown (00 to 59)
        self.minute_var = tk.StringVar()
        minute_choices = [f"{m:02d}" for m in range(60)]
        self.minute_combo = ttk.Combobox(time_frame, values=minute_choices, width=3, textvariable=self.minute_var, state="readonly")
        self.minute_combo.current(0)
        self.minute_combo.pack(side=tk.LEFT)
        
        tk.Label(parent, text="Frequency:").pack()
        self.freq_var = tk.StringVar()
        freq_dropdown = ttk.Combobox(parent, textvariable=self.freq_var)
        freq_dropdown['values'] = ("Daily", "Weekly")
        freq_dropdown.current(0)
        freq_dropdown.pack()

        tk.Button(parent, text="Create Scheduled Task", command=lambda: self.schedule_task(self.hour_var.get(), self.minute_var.get())).pack(pady=10)

        self.update_schedule_log()

    def schedule_task(self, hour, minute):
        try:
            python_path = sys.executable
            script_path = os.path.abspath(__file__)
            task_name = "AutomaticBackup"

            time_str = f"{hour}:{minute}"

            command = (
                f'schtasks /Create /SC DAILY /TN "{task_name}" '
                f'/TR "\\"{python_path}\\" \\"{script_path}\\" --auto" '
                f'/ST {time_str} /F'
            )

            subprocess.run(command, shell=True, check=True)
            messagebox.showinfo("Success", f"Scheduled task '{task_name}' created for {time_str}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create scheduled task:\n{e}")

    def update_schedule_log(self):
        self.log_text.delete("1.0", tk.END)  
        try:
            config = load_scheduled_config() 
            source_folders = config.get("source_folders", [])
        except Exception:
            source_folders = []
        
        if not source_folders:
            self.log_text.insert(tk.END, "No source folders selected for backup.\n")
        else:
            for folder in source_folders:
                self.log_text.insert(tk.END, f" - {folder}\n")

    def on_tab_changed(self, event):
        selected_tab = event.widget.select() 
        tab_text = event.widget.tab(selected_tab, "text")
        if tab_text == "Scheduler":
            self.update_schedule_log()

if __name__ == "__main__":
    if '--auto' in sys.argv:
        run_backup()
    else:
        root = tk.Tk()
        app = BackupApp(root)
        root.mainloop()
