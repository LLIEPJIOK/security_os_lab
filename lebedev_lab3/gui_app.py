import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
from archive_manager import ArchiveManager

class ArchiveGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Permission Archive")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        self.bg_color = "#f5f5f5"
        self.accent_color = "#2196F3"
        self.success_color = "#4CAF50"
        self.error_color = "#f44336"
        
        self.root.configure(bg=self.bg_color)
        
        self.create_widgets()
        
    def create_widgets(self):
        title_frame = tk.Frame(self.root, bg="#2196F3", height=80)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(title_frame, text="Permission Archive",
                              font=("Arial", 24, "bold"), bg="#2196F3", fg="white")
        title_label.pack(pady=20)
        
        subtitle_label = tk.Label(title_frame, 
                                 text="Pack and unpack files with permissions preservation",
                                 font=("Arial", 10), bg="#2196F3", fg="white")
        subtitle_label.pack()
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook', background=self.bg_color, borderwidth=0)
        style.configure('TNotebook.Tab', padding=[20, 10], font=("Arial", 11))
        style.map('TNotebook.Tab', background=[('selected', self.accent_color)],
                 foreground=[('selected', 'white')])
        
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        self.create_serialization_tab()
        self.create_deserialization_tab()
        
    def create_serialization_tab(self):
        frame = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(frame, text="Pack")
        
        content_frame = tk.Frame(frame, bg="white", relief=tk.RAISED, bd=1)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        title = tk.Label(content_frame, text="Pack Files or Directories",
                        font=("Arial", 18, "bold"), bg="white", fg="#333")
        title.pack(pady=(10, 5))
        
        description = tk.Label(content_frame, 
                              text="Select a file or directory to pack into an archive with permissions",
                              font=("Arial", 10), bg="white", fg="#666")
        description.pack(pady=(0, 20))
        
        source_frame = tk.Frame(content_frame, bg="white")
        source_frame.pack(pady=10, padx=40, fill=tk.X)
        
        tk.Label(source_frame, text="Source Path:", font=("Arial", 11, "bold"),
                bg="white", fg="#333").pack(anchor=tk.W, pady=(0, 5))
        
        source_input_frame = tk.Frame(source_frame, bg="white")
        source_input_frame.pack(fill=tk.X)
        
        self.source_entry = tk.Entry(source_input_frame, font=("Arial", 10), 
                                     relief=tk.SOLID, bd=1)
        self.source_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)
        
        btn_browse_source = tk.Button(source_input_frame, text="Browse...",
                                      command=self.browse_source,
                                      bg=self.accent_color, fg="white",
                                      font=("Arial", 10, "bold"),
                                      relief=tk.FLAT, padx=15, pady=8,
                                      cursor="hand2")
        btn_browse_source.pack(side=tk.LEFT, padx=(10, 0))
        
        dest_frame = tk.Frame(content_frame, bg="white")
        dest_frame.pack(pady=10, padx=40, fill=tk.X)
        
        tk.Label(dest_frame, text="Archive Path:", font=("Arial", 11, "bold"),
                bg="white", fg="#333").pack(anchor=tk.W, pady=(0, 5))
        
        dest_input_frame = tk.Frame(dest_frame, bg="white")
        dest_input_frame.pack(fill=tk.X)
        
        self.archive_entry = tk.Entry(dest_input_frame, font=("Arial", 10),
                                      relief=tk.SOLID, bd=1)
        self.archive_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)
        
        btn_browse_archive = tk.Button(dest_input_frame, text="Browse...",
                                       command=self.browse_archive_save,
                                       bg=self.accent_color, fg="white",
                                       font=("Arial", 10, "bold"),
                                       relief=tk.FLAT, padx=15, pady=8,
                                       cursor="hand2")
        btn_browse_archive.pack(side=tk.LEFT, padx=(10, 0))
        
        progress_frame = tk.Frame(content_frame, bg="white")
        progress_frame.pack(pady=20, padx=40, fill=tk.X)
        
        self.pack_progress = ttk.Progressbar(progress_frame, mode='determinate')
        self.pack_progress.pack(fill=tk.X, pady=(0, 5))
        
        self.pack_status_label = tk.Label(progress_frame, text="Ready to pack",
                                          font=("Arial", 9), bg="white", fg="#666")
        self.pack_status_label.pack()
        
        btn_frame = tk.Frame(content_frame, bg="white")
        btn_frame.pack(pady=20)
        
        btn = tk.Button(
            btn_frame,
            text="Pack Archive",
            command=self.pack_archive,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 11, "bold"),
            relief=tk.FLAT,
            width=20,
            height=2
        )
        btn.pack()
        
    def create_deserialization_tab(self):
        frame = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(frame, text="Unpack")
        
        content_frame = tk.Frame(frame, bg="white", relief=tk.RAISED, bd=1)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        title = tk.Label(content_frame, text="Unpack Archive",
                        font=("Arial", 18, "bold"), bg="white", fg="#333")
        title.pack(pady=(10, 5))
        
        description = tk.Label(content_frame,
                              text="Select an archive to unpack and restore files with permissions",
                              font=("Arial", 10), bg="white", fg="#666")
        description.pack(pady=(0, 20))
        
        archive_frame = tk.Frame(content_frame, bg="white")
        archive_frame.pack(pady=10, padx=40, fill=tk.X)
        
        tk.Label(archive_frame, text="Archive Path:", font=("Arial", 11, "bold"),
                bg="white", fg="#333").pack(anchor=tk.W, pady=(0, 5))
        
        archive_input_frame = tk.Frame(archive_frame, bg="white")
        archive_input_frame.pack(fill=tk.X)
        
        self.unpack_archive_entry = tk.Entry(archive_input_frame, font=("Arial", 10),
                                            relief=tk.SOLID, bd=1)
        self.unpack_archive_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)
        
        btn_browse_unpack = tk.Button(archive_input_frame, text="Browse...",
                                      command=self.browse_archive_open,
                                      bg=self.accent_color, fg="white",
                                      font=("Arial", 10, "bold"),
                                      relief=tk.FLAT, padx=15, pady=8,
                                      cursor="hand2")
        btn_browse_unpack.pack(side=tk.LEFT, padx=(10, 0))
        
        dest_frame = tk.Frame(content_frame, bg="white")
        dest_frame.pack(pady=10, padx=40, fill=tk.X)
        
        tk.Label(dest_frame, text="Destination Path:", font=("Arial", 11, "bold"),
                bg="white", fg="#333").pack(anchor=tk.W, pady=(0, 5))
        
        dest_input_frame = tk.Frame(dest_frame, bg="white")
        dest_input_frame.pack(fill=tk.X)
        
        self.unpack_dest_entry = tk.Entry(dest_input_frame, font=("Arial", 10),
                                          relief=tk.SOLID, bd=1)
        self.unpack_dest_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)
        
        btn_browse_dest = tk.Button(dest_input_frame, text="Browse...",
                                    command=self.browse_destination,
                                    bg=self.accent_color, fg="white",
                                    font=("Arial", 10, "bold"),
                                    relief=tk.FLAT, padx=15, pady=8,
                                    cursor="hand2")
        btn_browse_dest.pack(side=tk.LEFT, padx=(10, 0))
        
        progress_frame = tk.Frame(content_frame, bg="white")
        progress_frame.pack(pady=20, padx=40, fill=tk.X)
        
        self.unpack_progress = ttk.Progressbar(progress_frame, mode='determinate')
        self.unpack_progress.pack(fill=tk.X, pady=(0, 5))
        
        self.unpack_status_label = tk.Label(progress_frame, text="Ready to unpack",
                                           font=("Arial", 9), bg="white", fg="#666")
        self.unpack_status_label.pack()
        
        btn_frame = tk.Frame(content_frame, bg="white")
        btn_frame.pack(pady=20)
        
        btn = tk.Button(
            btn_frame,
            text="Unpack Archive",
            command=self.unpack_archive,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 11, "bold"),
            relief=tk.FLAT,
            width=20,
            height=2
        )
        btn.pack()
    
    def browse_source(self):
        choice = messagebox.askquestion("Select Source Type",
                                       "Do you want to select a directory?\n\n"
                                       "Click 'Yes' for directory, 'No' for file")
        
        if choice == 'yes':
            path = filedialog.askdirectory(title="Select Directory to Pack")
        else:
            path = filedialog.askopenfilename(title="Select File to Pack")
        
        if path:
            self.source_entry.delete(0, tk.END)
            self.source_entry.insert(0, path)

            suggested_name = f"{path}.perm"
            self.archive_entry.delete(0, tk.END)
            self.archive_entry.insert(0, suggested_name)
    
    def browse_archive_save(self):
        path = filedialog.asksaveasfilename(
            title="Save Archive As",
            defaultextension=".perm",
            filetypes=[("Permission Archive", "*.perm"), ("All Files", "*.*")]
        )
        
        if path:
            self.archive_entry.delete(0, tk.END)
            self.archive_entry.insert(0, path)
    
    def browse_archive_open(self):
        path = filedialog.askopenfilename(
            title="Select Archive to Unpack",
            filetypes=[("Permission Archive", "*.perm"), ("All Files", "*.*")]
        )
        
        if path:
            self.unpack_archive_entry.delete(0, tk.END)
            self.unpack_archive_entry.insert(0, path)

            suggested_destination = os.path.dirname(path)
            self.unpack_dest_entry.delete(0, tk.END)
            self.unpack_dest_entry.insert(0, suggested_destination)
    
    def browse_destination(self):
        path = filedialog.askdirectory(title="Select Destination Directory")
        
        if path:
            self.unpack_dest_entry.delete(0, tk.END)
            self.unpack_dest_entry.insert(0, path)
    
    def pack_archive(self):
        source = self.source_entry.get().strip()
        archive = self.archive_entry.get().strip()
        
        if not source:
            messagebox.showerror("Error", "Please select a source file or directory")
            return
        
        if not archive:
            messagebox.showerror("Error", "Please specify archive path")
            return
        
        if not os.path.exists(source):
            messagebox.showerror("Error", "Source path does not exist")
            return
        
        if not os.path.exists(os.path.dirname(archive)):
            choice = messagebox.askquestion("Create Directory",
                                    "Directory does not exist. Create it?")
            
            if choice == 'yes':
                os.makedirs(os.path.dirname(archive), exist_ok=True)
            else:
                return
        
        self.pack_progress['value'] = 0
        self.pack_status_label.config(text="Starting packing...")
        
        def progress_callback(current, total, message):
            progress = (current / total * 100) if total > 0 else 0
            self.root.after(0, lambda: self.pack_progress.config(value=progress))
            self.root.after(0, lambda: self.pack_status_label.config(text=message))
        
        def pack_thread():
            try:
                ArchiveManager.pack(source, archive, progress_callback)
            except Exception as e:
                self.root.after(0, lambda exc=e: messagebox.showerror("Error", f"Failed to create archive: {exc}"))
        
        threading.Thread(target=pack_thread, daemon=True).start()
    
    def unpack_archive(self):
        archive = self.unpack_archive_entry.get().strip()
        destination = self.unpack_dest_entry.get().strip()
        
        if not archive:
            messagebox.showerror("Error", "Please select an archive to unpack")
            return
        
        if not destination:
            messagebox.showerror("Error", "Please specify destination path")
            return
        
        if not os.path.exists(archive):
            messagebox.showerror("Error", "Archive does not exist")
            return
        
        if not os.path.exists(destination):
            choice = messagebox.askquestion("Create Directory",
                                    "Destination directory does not exist. Create it?")
            
            if choice == 'yes':
                os.makedirs(destination, exist_ok=True)
            else:
                return
        
        self.unpack_progress['value'] = 0
        self.unpack_status_label.config(text="Starting unpacking...")
        
        def progress_callback(current, total, message):
            progress = (current / total * 100) if total > 0 else 0
            self.root.after(0, lambda: self.unpack_progress.config(value=progress))
            self.root.after(0, lambda: self.unpack_status_label.config(text=message))
        
        def unpack_thread():
            try:
                ArchiveManager.unpack(archive, destination, progress_callback)
            except Exception as e:
                self.root.after(0, lambda exc=e: messagebox.showerror("Error", f"Failed to unpack archive: {exc}"))

        threading.Thread(target=unpack_thread, daemon=True).start()


def main():
    root = tk.Tk()
    app = ArchiveGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
