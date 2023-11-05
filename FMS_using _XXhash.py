import xxhash
import os
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox, colorchooser
import concurrent.futures
import threading
from collections import defaultdict
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from functools import partial
from PIL import Image, ImageTk
import json

backup_mapping_path = r"C:\deletion_backup\backup_mapping.json"

def delete_and_backup(file_path):
    try:
        backup_root = r"C:\deletion_backup"
        current_date = datetime.now().strftime("%Y-%m-%d")
        backup_folder = os.path.join(backup_root, current_date)
        os.makedirs(backup_folder, exist_ok=True)
        backup_file_path = os.path.join(backup_folder, os.path.basename(file_path))
        
        backup_mapping_path = os.path.join(backup_root, "backup_mapping.json")  # Define backup_mapping_path
        
        # Update the backup mapping
        if os.path.exists(backup_mapping_path):
            with open(backup_mapping_path, 'r') as f:
                backup_mapping = json.load(f)
        else:
            backup_mapping = {}
        
        # Ensure file paths are stored with double backslashes
        formatted_file_path = file_path.replace("/", "\\")
        backup_mapping[backup_file_path] = formatted_file_path
        
        with open(backup_mapping_path, 'w') as f:
            json.dump(backup_mapping, f)
        
        os.rename(file_path, backup_file_path)
        messagebox.showinfo("File Deleted", f"File deleted and backed up to {backup_file_path}")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {str(e)}")
    
def restore_file():
    file_path = filedialog.askopenfilename(initialdir=r"C:\deletion_backup")
    if not file_path:
        return

    # Normalize the file path
    normalized_file_path = file_path.replace("/", "\\")

    try:
        with open(backup_mapping_path, 'r') as f:
            backup_mapping = json.load(f)
        
        original_path = backup_mapping.get(normalized_file_path)
        if not original_path:
            messagebox.showerror("Error", "Unable to find the original path for this file.")
            return
        
        os.rename(normalized_file_path, original_path)
        del backup_mapping[normalized_file_path]
        with open(backup_mapping_path, 'w') as f:
            json.dump(backup_mapping, f)
        
        messagebox.showinfo("File Restored", f"File restored to {original_path}")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {str(e)}")




# Define a dictionary to map file type categories to their respective extensions
file_type_categories = {
    "All": [],
    "PDF": [".pdf"],
    "Text": [".txt", ".doc", ".docx"],
    "Image": [".jpg", ".jpeg", ".png", ".gif", ".bmp"],
    "Audio": [".mp3", ".wav", ".ogg"],
    "Video": [".mp4", ".avi", ".mkv", ".mov"],
    "Executable": [".exe", ".zip"],
}

selected_file_types = []
selected_size = None
excluded_extensions = ['.gitignore', '.git', '.classpath', '.settings', '.json', '.prefs', '.description', '.TAG', '.o', '.bin', '.log',
                       '.history', '.pdb', '.class', '.lock', '.c', '.h', '.o', '.so', '.a', '.pyc', '.pyo', '.dll', '.lib', '.obj',
                       '.cfg', '.ini', '.dat']
directory_entry = None
result_text = None
total_files_scanned = 0
total_duplicate_files = 0
duplicate_files_info = {}
root = None
stop_scan = False
scanned_file_types = defaultdict(int)
duplicate_file_types = defaultdict(int)
pie_chart_canvas = None
# ... (previous code) ...

def open_image_preview(image1_path, image2_path):
    img1 = Image.open(image1_path)
    img2 = Image.open(image2_path)

    preview_window = tk.Toplevel()
    preview_window.title("Image Preview")

    img1_photo = ImageTk.PhotoImage(img1)
    img2_photo = ImageTk.PhotoImage(img2)

    pane = tk.PanedWindow(preview_window, orient=tk.HORIZONTAL, sashrelief=tk.FLAT)
    pane.pack(fill=tk.BOTH, expand=1)

    label1 = tk.Label(pane, image=img1_photo)
    label1.image = img1_photo  # Keep a reference to the image object to prevent garbage collection

    label2 = tk.Label(pane, image=img2_photo)
    label2.image = img2_photo  # Keep a reference to the image object to prevent garbage collection

    pane.add(label1)
    pane.add(label2)


def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def calculate_file_hash(file_path, block_size=65536):
    xxh3 = xxhash.xxh3_64()
    with open(file_path, 'rb') as file:
        while True:
            data = file.read(block_size)
            if not data:
                break
            xxh3.update(data)
    return xxh3.hexdigest()

def scan_directory(directory, scan_progressbar, scan_percentage_label):

    selected_size = size_var.get()
    file_hashes = defaultdict(list)
    total_files = 0
    global stop_scan 

    def file_generator(directory):
        nonlocal total_files
        for root, _, files in os.walk(directory):
            for filename in files:
                full_path = os.path.join(root, filename)
                total_files += 1
                yield full_path

    def process_file(file_path):
        global total_files_scanned, total_duplicate_files
        global stop_scan
        if stop_scan:
            return
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension in excluded_extensions:
            return
        if selected_file_types and file_extension not in selected_file_types:
            return
        file_size = os.path.getsize(file_path)
        if selected_size == "Large" and file_size < 10 * 1024 * 1024:
            return
        if selected_size == "Medium" and not (5 * 1024 * 1024 <= file_size < 10 * 1024 * 1024):
            return
        if selected_size == "Small" and file_size >= 5 * 1024 * 1024:
            return
        file_hash = calculate_file_hash(file_path)
        file_hashes[file_hash].append(file_path)
        total_files_scanned += 1
        

        # Update the progress bar
        current_progress = (total_files_scanned / total_files) * 100
        scan_progressbar["value"] = current_progress
        scan_percentage_label["text"] = f"{int(current_progress)}%"

        scanned_file_types[file_extension] += 1

    generator = file_generator(directory)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        for file_path in generator:
            executor.submit(process_file, file_path)

    return file_hashes

def identify_duplicates(file_hashes):
    duplicates = {hash_value: file_paths for hash_value, file_paths in file_hashes.items() if len(file_paths) > 1}
    # Update the duplicate file types dictionary
    for _, file_paths in duplicates.items():
        for file_path in file_paths:
            file_extension = os.path.splitext(file_path)[1].lower()
            duplicate_file_types[file_extension] += 1
    
    return duplicates



def select_directory():
    selected_directory = filedialog.askdirectory()
    if selected_directory:
        directory_entry.delete(0, tk.END)
        directory_entry.insert(0, selected_directory)

def open_folder_for_file(file_path):
    folder_path = os.path.dirname(file_path)
    os.startfile(folder_path)
    os.startfile(file_path)



def update_selected_file_types():
    global selected_file_types
    selected_file_types = []
    for category, extensions in file_type_categories.items():
        if category != "All" and category in file_type_var and file_type_var[category].get() == 1:
            selected_file_types.extend(extensions)

def find_duplicates():
    global total_files_scanned, total_duplicate_files, duplicate_files_info
    directory = directory_entry.get()
    if not directory:
        result_text.delete("1.0", tk.END)
        result_text.insert(tk.END, "Please select a directory to scan.")
        return

    result_text.delete("1.0", tk.END)
    result_text.insert(tk.END, "Scanning...\n")

    start_time = datetime.now()

    

    def scan_and_display():
        global total_files_scanned, total_duplicate_files, duplicate_files_info
        try:
            update_selected_file_types()
            file_hashes = scan_directory(directory, scan_progressbar, scan_percentage_label)
            duplicate_files = identify_duplicates(file_hashes)

            total_files_scanned = sum(len(file_paths) for file_paths in file_hashes.values())
            total_duplicate_files = sum(len(file_paths) for file_paths in duplicate_files.values())

            end_time = datetime.now()
            timestamp = get_timestamp()

            # Update the progress bar with 100% after scanning is complete
            if stop_scan == False:
                scan_progressbar["value"] = 100
                scan_percentage_label["text"] = "100%"

            root.after(0, update_gui_with_results, duplicate_files, start_time, end_time, timestamp)
        except Exception as e:
            root.after(0, handle_error, str(e))

    scan_thread = threading.Thread(target=scan_and_display)
    scan_thread.start()

def clear_results():
    global total_files_scanned, total_duplicate_files, duplicate_files_info, stop_scan, pie_chart_canvas
    total_files_scanned = 0
    total_duplicate_files = 0
    duplicate_files_info = {}
    stop_scan = False
    result_text.delete("1.0", tk.END)
    directory_entry.delete(0, tk.END)
    scan_progressbar["value"] = 0
    scan_percentage_label["text"] = "0%"

    # Reset the scanned file types counts to 0
    for file_type in scanned_file_types:
        scanned_file_types[file_type] = 0

    # Reset the duplicate file types counts to 0
    for file_type in duplicate_file_types:
        duplicate_file_types[file_type] = 0
    
    # Update the StringVar variables to reset the displayed statistics
    total_scanned_var.set("0")
    total_duplicate_var.set("0")
    scanned_file_types_display.delete("1.0", tk.END)
    duplicate_file_types_display.delete("1.0", tk.END)

    if pie_chart_canvas:
        pie_chart_canvas.get_tk_widget().destroy()
        pie_chart_canvas = None

def stop_scan_process():
    global stop_scan
    stop_scan = True
    result_text.insert(tk.END, "Scanning stopped.\n")
    
def open_group_preview(file_paths):
    preview_window = tk.Toplevel()
    preview_window.title("Image Group Preview")

    pane = tk.PanedWindow(preview_window, orient=tk.HORIZONTAL, sashrelief=tk.FLAT)
    pane.pack(fill=tk.BOTH, expand=1)

    for file_path in file_paths:
        img = Image.open(file_path)
        photo = ImageTk.PhotoImage(img)

        label = tk.Label(pane, image=photo)
        label.image = photo  # Keep a reference to the image object to prevent garbage collection
        pane.add(label)


def update_gui_with_results(duplicate_files, start_time, end_time, timestamp):
    def update_gui():
        result_text.delete("1.0", tk.END)

        if timestamp:
            result_text.insert(tk.END, f"Time of scan: {timestamp}\n")
            result_text.insert(tk.END, f"Time taken: {end_time - start_time}\n")
            result_text.insert(tk.END, f"Total files scanned: {total_files_scanned}\n")
            result_text.insert(tk.END, f"Total duplicate files: {total_duplicate_files}\n\n")

        if not duplicate_files:
            result_text.insert(tk.END, "No duplicates found.")
            return

        for hash_value, file_paths in duplicate_files.items():
            result_text.insert(tk.END, f"{'-' * 95}\n")  # Separator line
            result_text.insert(tk.END, f"Duplicate group (Hash: {hash_value}):\n")
            for file_path in file_paths:
                file_extension = os.path.splitext(file_path)[1].lower()
                result_text.insert(tk.END, f"  {file_path}\n")
                if file_extension in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                    
                   preview_button = tk.Button(result_text, text="Preview Group",command=partial(open_group_preview, file_paths))
                   result_text.window_create(tk.END, window=preview_button)
                   delete_button = tk.Button(result_text, text="Delete", command=lambda path=file_path: delete_and_backup(path))
                   result_text.window_create(tk.END, window=delete_button) 
                   
                 
                
            
                else:
                    
                    open_button = tk.Button(result_text, text="Open", command=lambda path=file_path: open_folder_for_file(path))
                    delete_button = tk.Button(result_text, text="Delete", command=lambda path=file_path: delete_and_backup(path))
                    result_text.window_create(tk.END, window=open_button)
                    result_text.window_create(tk.END, window=delete_button)
                    result_text.insert(tk.END, "\n")
                    
                result_text.insert(tk.END, "\n")

        def create_pie_chart():
            global pie_chart_canvas 
            file_types = list(duplicate_file_types.keys())
            counts = list(duplicate_file_types.values())

            fig, ax = plt.subplots(figsize=(3,3))
            ax.pie(counts, labels=file_types, autopct='%1.1f%%', startangle=140)
            ax.set_title('Duplicate File Types')

            pie_chart_canvas = FigureCanvasTkAgg(fig, master=root)
            pie_chart_canvas.get_tk_widget().grid(row=4, column=4, columnspan=1, padx=10, pady=10)

        create_pie_chart()

    total_scanned_var.set(str(total_files_scanned))
    total_duplicate_var.set(str(total_duplicate_files))

    for file_type, count in scanned_file_types.items():
        scanned_file_types_display.insert(tk.END, f"{file_type}: {count}\n")

    for file_type, count in duplicate_file_types.items():
        duplicate_file_types_display.insert(tk.END, f"{file_type}: {count}\n")
    
    root.after(0, update_gui)


def handle_error(error_message):
    result_text.delete("1.0", tk.END)
    result_text.insert(tk.END, f"Error occurred:\n{error_message}\n")


if __name__ == "__main__":
    root = tk.Tk()
    root.title("File Management System")

    total_scanned_var = tk.StringVar()
    total_duplicate_var = tk.StringVar()

    def change_theme(theme_name):
        style.theme_use(theme_name)
        style.configure("TButton", background="blue", foreground="white")
        # style.configure("TLabel", background="lightblue")


    def change_theme_color():
        # Open a color dialog and get the selected color
        color = colorchooser.askcolor()[1]

        # Configure the style with the selected color for the root theme
        style.configure(".", background=color)


    def change_root_color():
        # Open a color dialog and get the selected color
        color = colorchooser.askcolor()[1]

        # Configure the background color of the root window
        root.configure(bg=color)


    def change_background_color():
        # Open a color dialog and get the selected background color
        background_color = colorchooser.askcolor()[1]

        # Configure the style with the selected background color
        style.configure("TButton", background=background_color)
        # style.configure("TLabel", background=background_color)


    def change_foreground_color():
        # Open a color dialog and get the selected foreground color
        foreground_color = colorchooser.askcolor()[1]

        # Configure the style with the selected foreground color
        style.configure("TButton", foreground=foreground_color)
        # style.configure("TLabel", foreground=foreground_color)

    directory_label = ttk.Label(root, text="Directory to Scan:")
    directory_label.grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)

    directory_entry = ttk.Entry(root, width=60)
    directory_entry.grid(row=0, column=1, padx=10, pady=5)

    select_directory_button = ttk.Button(root, text="Select Directory", command=select_directory)
    select_directory_button.grid(row=0, column=2, padx=10, pady=5)

    file_type_frame = ttk.LabelFrame(root, text="File Types to Scan", padding="10 5")
    file_type_frame.grid(row=1, column=0, columnspan=3, padx=10, pady=5, sticky=tk.W + tk.E)

    file_type_var = {}
    for idx, (category, _) in enumerate(file_type_categories.items()):
        file_type_var[category] = tk.IntVar(value=1 if category == "All" else 0)
        chk = ttk.Checkbutton(file_type_frame, text=category, variable=file_type_var[category])
        chk.grid(row=0, column=idx, sticky=tk.W, padx=5)

    size_var = tk.StringVar(value="All")
    size_frame = ttk.LabelFrame(root, text="File Size", padding="10 5")
    size_frame.grid(row=2, column=0, columnspan=3, padx=10, pady=5, sticky=tk.W + tk.E)

    for idx, size_category in enumerate(["All", "Small", "Medium", "Large"]):
        rad = ttk.Radiobutton(size_frame, text=size_category, value=size_category, variable=size_var)
        rad.grid(row=0, column=idx, sticky=tk.W, padx=5)

    style = ttk.Style()
    # List of available themes
    themes = ["alt", "alt", "default", "classic", "vista", "xpnative", "clam"]

    # Create a Menubutton for color and theme options
    color_theme_menu = ttk.Menubutton(root, text="GUI Settings")

    # Create a menu for color and theme options
    color_theme_submenu = tk.Menu(color_theme_menu, tearoff=0)

    # Add commands to the menu for changing background and foreground colors
    color_theme_submenu.add_command(label="Change Button Color", command=change_background_color)
    color_theme_submenu.add_command(label="Change Font Color", command=change_foreground_color)
    color_theme_submenu.add_command(label="Change Frame Color", command=change_theme_color)
    color_theme_submenu.add_command(label="Change Theme Color", command=change_root_color)

    # Add a separator line in the menu
    color_theme_submenu.add_separator()

    # Add commands to the menu for changing themes
    for theme in themes:
        color_theme_submenu.add_command(label=f"Change to {theme} Theme", command=lambda t=theme: change_theme(t))

    # Set the menu to the Menubutton
    color_theme_menu["menu"] = color_theme_submenu

    # Place the Menubutton in the desired location
    color_theme_menu.grid(row=5, column=4, padx=10, pady=10)

    start_button = ttk.Button(root, text="Find Duplicates", command=find_duplicates)
    start_button.grid(row=3, column=0, columnspan=3, padx=10, pady=10)
    
    restore_button = ttk.Button(root, text="Restore File", command=restore_file)
    restore_button.grid(row=5, column=2, columnspan=1, padx=10, pady=10)
    
    result_text = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=100, height=20)
    result_text.grid(row=4, column=0, columnspan=3, padx=10, pady=10)

    clear_button = ttk.Button(root, text="Clear Results", command=clear_results)
    clear_button.grid(row=5, column=1, columnspan=1, padx=10, pady=10)

    stop_button = ttk.Button(root, text="Stop", command=stop_scan_process)
    stop_button.grid(row=5, column=0, columnspan=1, padx=10, pady=10)

    # Create a progress bar and label for scanning
    scan_progressbar = ttk.Progressbar(root, length=200, mode="determinate")
    scan_progressbar.grid(row=6, column=0, columnspan=3, padx=10, pady=5)
    scan_percentage_label = ttk.Label(root, text="0%")
    scan_percentage_label.grid(row=6, column=1, columnspan=3)

    scanned_file_types_label = ttk.Label(root, text="Types of Files Scanned:")
    scanned_file_types_label.grid(row=0, column=4, sticky=tk.W, padx=10, pady=5)
    scanned_file_types_display = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=20, height=3)
    scanned_file_types_display.grid(row=1, column=4, columnspan=1, padx=10, pady=10)

    duplicate_file_types_label = ttk.Label(root, text="Types of Duplicate Files:")
    duplicate_file_types_label.grid(row=2, column=4, sticky=tk.W, padx=10, pady=5)
    duplicate_file_types_display = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=20, height=3)
    duplicate_file_types_display.grid(row=3, column=4, columnspan=1, padx=10, pady=10)

    root.mainloop()
