import tkinter as tk
from tkinter import ttk, messagebox, font
import requests
from PIL import Image, ImageTk
import ctypes
import threading
import time
import os
import io
import random
import sys
import webbrowser
import shutil
import psutil
from winotify import Notification, audio
from pystray import MenuItem as item, Icon

# --- Constants ---
APP_NAME = "Infinity_Wallpaper"
VERSION = "2.6" # Final Polish
SAVED_WALLPAPERS_DIR = os.path.join(os.path.expanduser('~'), 'Pictures', APP_NAME)
ASPECT_RATIO_16_9 = 16 / 9
ASPECT_RATIO_TOLERANCE = 0.1
DONATION_URL = "coff.ee/XiaoInt"
RATING_INFO_URL = "https://danbooru.donmai.us/wiki_pages/howto:rate"
ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif']
STARTUP_FOLDER = os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
SCRIPT_PATH = os.path.abspath(sys.argv[0])
STARTUP_SCRIPT_PATH = os.path.join(STARTUP_FOLDER, f"{APP_NAME}.bat")
ICON_PATH = "app_icon.ico"


# --- Windows API for setting wallpaper ---
SPI_SETDESKWALLPAPER = 20
SPIF_UPDATEINIFILE = 1
SPIF_SENDCHANGE = 2

def set_wallpaper(path):
    """Sets the desktop wallpaper for Windows."""
    abs_path = os.path.abspath(path)
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, abs_path, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE)
        except Exception as e:
            print(f"Error setting wallpaper: {e}")
            return False
    else:
        print("Wallpaper setting is only supported on Windows.")
        return False
    return True

class DanbooruWallpaperApp:
    """The main class for the Tkinter GUI application."""
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} v{VERSION}")
        self.root.geometry("550x490") 
        self.root.minsize(500, 460)

        if os.path.exists(ICON_PATH):
            self.root.iconbitmap(ICON_PATH)

        # --- State & System Tray Variables ---
        self.slideshow_thread = None
        self.is_running = threading.Event()
        self.is_paused = threading.Event()
        self.current_image_path = None
        self.last_image_path = None
        self.current_image_url = ""
        self.current_post_url = ""
        self.preview_window = None
        self.tray_icon = None

        # --- Style Configuration ---
        self.style = ttk.Style(self.root)
        self.style.theme_use('clam')
        self.style.configure("TLabel", padding=5, font=('Segoe UI', 10))
        self.style.configure("TButton", padding=6, font=('Segoe UI', 10, 'bold'))
        self.style.configure("TEntry", padding=5, font=('Segoe UI', 10))
        self.style.configure("TFrame", padding=10)
        self.style.configure("Header.TLabel", font=('Segoe UI', 14, 'bold'))
        self.style.configure("Info.TButton", font=('Segoe UI', 8, 'bold'), padding=(2,0))
        self.style.configure("Donate.TButton", font=('Segoe UI', 9, 'bold'), foreground='red')

        self.create_widgets()
        
        if not os.path.exists(SAVED_WALLPAPERS_DIR):
            os.makedirs(SAVED_WALLPAPERS_DIR)
            
        self.is_paused.set()
        
        # --- FIX: Check for a wallpaper from the last session on startup ---
        self.check_for_existing_wallpaper()

    def check_for_existing_wallpaper(self):
        """Checks for a temp wallpaper from a previous session and enables buttons if found."""
        if os.path.exists(SAVED_WALLPAPERS_DIR):
            for filename in os.listdir(SAVED_WALLPAPERS_DIR):
                if filename.startswith("temp_wallpaper_") and filename.endswith(".jpg"):
                    self.current_image_path = os.path.join(SAVED_WALLPAPERS_DIR, filename)
                    self.save_button.config(state=tk.NORMAL)
                    self.preview_button.config(state=tk.NORMAL)
                    self.update_status("Found wallpaper from last session. Ready to preview.")
                    break # Found one, no need to check further

    def show_info(self):
        """Displays an informational message box about tags, usage, and license."""
        info_text = (
            "--- How to Find and Use Tags ---\n\n"
            "1. Finding Tags:\n"
            "   - Go to the Danbooru website (danbooru.donmai.us).\n\n"
            "2. Tag Formatting:\n"
            "   - Separate multiple tags with spaces (e.g., 'genshin_impact 1girl').\n"
            "   - For tags with multiple words, use underscores (_) (e.g., 'long_hair').\n\n"
            "--- About & License ---\n\n"
            "Disclaimer:\n"
            "This application is a tool to access content from the Danbooru API for personal use. The images are the property of their respective copyright holders.\n\n"
            "License (GNU GPLv3):\n"
            "This is free software. You are free to use, study, share, and improve it. If you distribute modified versions, they must also be licensed under the GPLv3."
        )
        messagebox.showinfo("Info & About", info_text)
        
    def toggle_startup(self):
        """Creates or deletes the startup script."""
        if self.startup_var.get():
            executable_path = sys.executable if SCRIPT_PATH.endswith('.py') else SCRIPT_PATH
            script_to_run = f'"{SCRIPT_PATH}"' if SCRIPT_PATH.endswith('.py') else ''
            command = f'start "" "{executable_path}" {script_to_run} --startup'
            
            with open(STARTUP_SCRIPT_PATH, "w") as f:
                f.write(command)
        else:
            if os.path.exists(STARTUP_SCRIPT_PATH):
                os.remove(STARTUP_SCRIPT_PATH)

    def create_widgets(self):
        """Creates and arranges all the GUI widgets."""
        main_frame = ttk.Frame(self.root, padding=(20, 10))
        main_frame.pack(fill=tk.BOTH, expand=True)

        header_label = ttk.Label(main_frame, text=APP_NAME, style="Header.TLabel")
        header_label.pack(pady=(0, 15))

        settings_frame = ttk.Frame(main_frame)
        settings_frame.pack(fill=tk.X, expand=True)
        settings_frame.columnconfigure(1, weight=1)

        # Tags
        tags_frame = ttk.Frame(settings_frame)
        tags_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        tags_frame.columnconfigure(1, weight=1)
        ttk.Label(tags_frame, text="Tags:").grid(row=0, column=0, sticky="w")
        self.info_button = ttk.Button(tags_frame, text="?", style="Info.TButton", width=2, command=self.show_info)
        self.info_button.grid(row=0, column=2, sticky='e', padx=(5,0))
        self.tags_var = tk.StringVar(value="1girl solo")
        self.tags_entry = ttk.Entry(tags_frame, textvariable=self.tags_var)
        self.tags_entry.grid(row=0, column=1, sticky="ew", padx=(5, 2))

        # Rating
        rating_frame = ttk.Frame(settings_frame)
        rating_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        rating_frame.columnconfigure(1, weight=1)
        ttk.Label(rating_frame, text="Rating:").grid(row=0, column=0, sticky="w")
        self.rating_info_button = ttk.Button(rating_frame, text="?", style="Info.TButton", width=2, command=lambda: webbrowser.open_new(RATING_INFO_URL))
        self.rating_info_button.grid(row=0, column=2, sticky='e', padx=(5,0))
        self.rating_var = tk.StringVar(value="general")
        ratings = ["general", "sensitive", "questionable", "explicit"]
        self.rating_menu = ttk.OptionMenu(rating_frame, self.rating_var, ratings[0], *ratings)
        self.rating_menu.grid(row=0, column=1, sticky="ew", padx=(5, 2))

        # Interval
        interval_frame = ttk.Frame(settings_frame)
        interval_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        interval_frame.columnconfigure(1, weight=1)
        ttk.Label(interval_frame, text="Interval (s):").grid(row=0, column=0, sticky="w")
        self.interval_var = tk.StringVar(value="300")
        self.interval_entry = ttk.Entry(interval_frame, textvariable=self.interval_var)
        self.interval_entry.grid(row=0, column=1, sticky="ew")

        # --- Start with Windows Checkbox ---
        self.startup_var = tk.BooleanVar()
        self.startup_check = ttk.Checkbutton(main_frame, text="Start with Windows", variable=self.startup_var, command=self.toggle_startup)
        self.startup_check.pack(pady=10)
        if os.path.exists(STARTUP_SCRIPT_PATH):
            self.startup_var.set(True)

        # Controls
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(5, 10))
        controls_frame.columnconfigure((0, 1), weight=1)
        self.start_button = ttk.Button(controls_frame, text="Start Slideshow", command=self.start_slideshow)
        self.start_button.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5)
        self.pause_button = ttk.Button(controls_frame, text="Pause", command=self.toggle_pause, state=tk.DISABLED)
        self.pause_button.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        self.stop_button = ttk.Button(controls_frame, text="Stop", command=self.stop_slideshow, state=tk.DISABLED)
        self.stop_button.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

        # Actions
        actions_frame = ttk.Frame(main_frame)
        actions_frame.pack(fill=tk.X, pady=(5, 10))
        actions_frame.columnconfigure((0, 1), weight=1)
        self.save_button = ttk.Button(actions_frame, text="Save Current", command=self.save_wallpaper, state=tk.DISABLED)
        self.save_button.grid(row=0, column=0, sticky="ew", padx=5)
        self.preview_button = ttk.Button(actions_frame, text="Preview", command=self.toggle_preview, state=tk.DISABLED)
        self.preview_button.grid(row=0, column=1, sticky="ew", padx=5)

        # --- Background info text ---
        bg_info_label = ttk.Label(main_frame, text="You can close this window; the app will run in the background.", font=('Segoe UI', 8, 'italic'), justify=tk.CENTER)
        bg_info_label.pack(pady=(5,0))

        # Status Label
        self.status_var = tk.StringVar(value="Ready. Click 'Start Slideshow' to begin.")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, wraplength=500, justify=tk.CENTER)
        status_label.pack(fill=tk.X, pady=(5, 0))

        # Footer
        footer_frame = ttk.Frame(main_frame)
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X, anchor='s', pady=(5,0))
        credit_font = font.Font(family='Segoe UI', size=8, underline=True)
        credit_label = tk.Label(footer_frame, text="Created by xiaoint", fg="blue", cursor="hand2", font=credit_font)
        credit_label.pack(side=tk.LEFT, padx=5)
        credit_label.bind("<Button-1>", lambda e: webbrowser.open_new("https://github.com/xiaoint"))
        donate_button = ttk.Button(footer_frame, text="❤ Donate", style="Donate.TButton", command=lambda: webbrowser.open_new(DONATION_URL))
        donate_button.pack(side=tk.RIGHT, padx=5)

    def lock_settings(self):
        """Disables settings widgets while the slideshow is running."""
        self.tags_entry.config(state=tk.DISABLED)
        self.rating_menu.config(state=tk.DISABLED)
        self.interval_entry.config(state=tk.DISABLED)
        self.startup_check.config(state=tk.DISABLED)

    def unlock_settings(self):
        """Enables settings widgets when the slideshow is stopped."""
        self.tags_entry.config(state=tk.NORMAL)
        self.rating_menu.config(state=tk.NORMAL)
        self.interval_entry.config(state=tk.NORMAL)
        self.startup_check.config(state=tk.NORMAL)

    def start_slideshow(self):
        if self.slideshow_thread and self.slideshow_thread.is_alive():
            return
        self.lock_settings() 
        self.is_running.set()
        self.slideshow_thread = threading.Thread(target=self.wallpaper_loop, daemon=True)
        self.slideshow_thread.start()
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.NORMAL, text="Pause")
        self.update_status("Slideshow started...")

    def stop_slideshow(self):
        self.unlock_settings() 
        self.is_running.clear()
        self.is_paused.set()
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.pause_button.config(state=tk.DISABLED, text="Pause")
        self.update_status("Slideshow stopped.")

    def toggle_pause(self):
        if self.is_paused.is_set():
            self.is_paused.clear()
            self.pause_button.config(text="Resume")
            self.update_status("Paused. Waiting for resume...")
        else:
            self.is_paused.set()
            self.pause_button.config(text="Pause")
            self.update_status("Resumed. Fetching next wallpaper...")

    def save_wallpaper(self):
        if not self.current_image_path or not os.path.exists(self.current_image_path):
            messagebox.showerror("Error", "No valid wallpaper to save.")
            return
        try:
            filename = os.path.basename(self.current_image_url).split('?')[0]
            save_path = os.path.join(SAVED_WALLPAPERS_DIR, filename)
            shutil.copy(self.current_image_path, save_path)
            messagebox.showinfo("Success", f"Wallpaper saved to:\n{os.path.abspath(save_path)}")
        except Exception as e:
            messagebox.showerror("Save Failed", f"Could not save the wallpaper: {e}")

    def update_status(self, message):
        self.root.after(0, self.status_var.set, message)

    def wallpaper_loop(self):
        while self.is_running.is_set():
            self.is_paused.wait() 
            if not self.is_running.is_set(): break
            try:
                self.update_status("Fetching new image list...")
                tags = self.tags_var.get().strip()
                rating = self.rating_var.get()
                random_page = random.randint(1, 200)
                headers = {'User-Agent': f'{APP_NAME}/{VERSION}'}
                api_url = f"https://danbooru.donmai.us/posts.json"
                params = {'tags': f"{tags} rating:{rating}", 'limit': 100, 'page': random_page}
                response = requests.get(api_url, params=params, headers=headers, timeout=15)
                response.raise_for_status()
                posts = response.json()

                suitable_posts = []
                for post in posts:
                    if 'file_ext' not in post or post['file_ext'] not in ALLOWED_EXTENSIONS:
                        continue
                    if 'file_url' in post and 'image_width' in post and 'image_height' in post:
                        w, h = post['image_width'], post['image_height']
                        if h > 0 and abs((w / h) - ASPECT_RATIO_16_9) < ASPECT_RATIO_TOLERANCE:
                            suitable_posts.append(post)

                if not suitable_posts:
                    self.update_status("No suitable images found on this page. Retrying...")
                    time.sleep(5)
                    continue

                post = random.choice(suitable_posts)
                image_url = post['file_url']
                self.current_post_url = f"https://danbooru.donmai.us/posts/{post['id']}"
                self.current_image_url = image_url
                
                self.update_status(f"Downloading: {os.path.basename(image_url)}")
                img_response = requests.get(image_url, headers=headers, timeout=20)
                img_response.raise_for_status()

                temp_filename = f"temp_wallpaper_{post['id']}.jpg"
                self.current_image_path = os.path.join(SAVED_WALLPAPERS_DIR, temp_filename)

                with open(self.current_image_path, 'wb') as f:
                    f.write(img_response.content)

                if set_wallpaper(self.current_image_path):
                    self.update_status(f"Wallpaper set! Source: {self.current_post_url}")
                    # --- FIX: Enable both save and preview buttons ---
                    self.root.after(0, lambda: self.save_button.config(state=tk.NORMAL))
                    self.root.after(0, lambda: self.preview_button.config(state=tk.NORMAL))
                    if self.last_image_path and os.path.exists(self.last_image_path):
                        try:
                            os.remove(self.last_image_path)
                        except OSError as e:
                            print(f"Error removing old wallpaper file: {e}")
                    self.last_image_path = self.current_image_path
                else:
                    self.update_status("Error: Failed to set wallpaper via Windows API.")
                    if os.path.exists(self.current_image_path):
                        os.remove(self.current_image_path)

                interval = int(self.interval_var.get())
                for _ in range(interval):
                    if not self.is_running.is_set(): break
                    time.sleep(1)
            except requests.exceptions.HTTPError as e:
                self.update_status(f"HTTP Error: {e.response.status_code}. Retrying...")
                time.sleep(30)
            except requests.exceptions.RequestException as e:
                self.update_status(f"Network Error. Check connection. Retrying...")
                time.sleep(30)
            except Exception as e:
                self.update_status(f"An unexpected error occurred: {e}. Retrying...")
                time.sleep(30)

    def show_notification(self, title, message):
        """Shows a Windows notification using winotify."""
        def _show():
            toast = Notification(app_id=APP_NAME,
                                 title=title,
                                 msg=message,
                                 duration='short')
            toast.set_audio(audio.Default, loop=False)
            if os.path.exists(ICON_PATH):
                toast.set_icon(os.path.abspath(ICON_PATH))
            toast.show()
        threading.Thread(target=_show, daemon=True).start()

    def hide_window(self):
        """Hides the main window and creates a system tray icon."""
        self.root.withdraw()
        if os.path.exists(ICON_PATH):
            image = Image.open(ICON_PATH)
        else:
            image = Image.new('RGB', (64, 64), 'black') # Placeholder icon
            
        menu = (item('Show', self.show_window), item('Quit', self.quit_app))
        self.tray_icon = Icon("name", image, f"{APP_NAME}", menu)
        
        self.show_notification(f"{APP_NAME}", "Running in the background.")
        
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_window(self, icon, item):
        """Shows the main window and stops the tray icon."""
        self.tray_icon.stop()
        self.root.after(0, self.root.deiconify)

    def quit_app(self, icon=None, item=None):
        """Properly quits the application from the system tray."""
        if self.tray_icon:
            self.tray_icon.stop()
        self.is_running.clear()
        self.is_paused.set()
        if self.slideshow_thread and self.slideshow_thread.is_alive():
            self.slideshow_thread.join(timeout=2)
        # --- FIX: Do not delete any temp files on quit, so they can be previewed next time ---
        self.root.destroy()

    def toggle_preview(self):
        """Toggles a fullscreen preview of the current wallpaper."""
        if self.preview_window and self.preview_window.winfo_exists():
            self.preview_window.destroy()
            self.preview_window = None
            return

        if not self.current_image_path or not os.path.exists(self.current_image_path):
            messagebox.showinfo("No Preview", "No wallpaper has been set in this session yet.")
            return

        self.preview_window = tk.Toplevel(self.root)
        self.preview_window.title("Wallpaper Preview - Press ESC to close")
        self.preview_window.configure(bg='black')
        self.preview_window.attributes('-fullscreen', True)
        
        img = Image.open(self.current_image_path)
        
        screen_width = self.preview_window.winfo_screenwidth()
        screen_height = self.preview_window.winfo_screenheight()
        img.thumbnail((screen_width, screen_height), Image.Resampling.LANCZOS)
        
        photo = ImageTk.PhotoImage(img)
        
        label = tk.Label(self.preview_window, image=photo, bg='black')
        label.image = photo # Keep a reference!
        label.pack(expand=True)
        
        self.preview_window.bind("<Escape>", lambda e: self.preview_window.destroy())


if __name__ == "__main__":
    lock_file_path = os.path.join(os.path.expanduser('~'), f'.{APP_NAME.lower()}.lock')
    
    if "--startup" not in sys.argv:
        if os.path.exists(lock_file_path):
            try:
                with open(lock_file_path, 'r') as f:
                    pid = int(f.read())
                if psutil.pid_exists(pid):
                    messagebox.showerror("Already Running", f"{APP_NAME} is already running.")
                    sys.exit()
                else:
                    os.remove(lock_file_path)
            except (IOError, ValueError):
                os.remove(lock_file_path)

        with open(lock_file_path, "w") as f:
            f.write(str(os.getpid()))

    try:
        root = tk.Tk()
        app = DanbooruWallpaperApp(root)

        if "--startup" in sys.argv:
            boot_time = psutil.boot_time()
            boot_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(boot_time))
            app.show_notification(f"{APP_NAME} Started", f"Successfully launched on startup.\nSystem last booted: {boot_time_str}")
            app.start_slideshow()
            app.hide_window()
        
        root.protocol("WM_DELETE_WINDOW", app.hide_window)
        root.mainloop()

    finally:
        if os.path.exists(lock_file_path):
            os.remove(lock_file_path)
