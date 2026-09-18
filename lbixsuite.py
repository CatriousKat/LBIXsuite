import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from PIL import Image, ImageTk, ImageOps
import zipfile
import os
import re
import time
from io import BytesIO

# --- LBIMG5 encoder/decoder --- #

def encode_lbimg(png_path):
    """Encodes PNG at 100% quality and physically rotates pixels if vertical."""
    with Image.open(png_path) as img:
        # PHYSICALLY rotate pixels based on phone's orientation flag 
        # before we strip the metadata.
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGBA")
        
        output = BytesIO()
        # Save at 100% quality, optimize=True, and strip EXIF/ICC profiles
        img.save(output, format="PNG", quality=100, optimize=True, icc_profile=None)
        return output.getvalue()

def decode_lbimg(data):
    """Decodes the image and ensures it stays upright."""
    img = Image.open(BytesIO(data))
    # Safety check for decoding
    img = ImageOps.exif_transpose(img)
    return img

# --- LBScript interpreter --- #

class LBScriptRunner:
    def __init__(self, master, main_img, lbix_name):
        self.master = master
        self.main_img = main_img
        self.lbix_name = lbix_name
        self.image_window = None
        self.img_tk = None
        self.transparency = 255
        self.txtboxinput = ""
        self.filepicked = ""
        
    def strip_quotes(self, text):
        if not text: return text
        if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
            return text[1:-1]
        return text
        
    def show_image(self):
        if self.image_window is None or not self.image_window.winfo_exists():
            self.image_window = tk.Toplevel(self.master)
            self.image_window.title(self.lbix_name)
            self.image_window.protocol("WM_DELETE_WINDOW", self.cmd_close)

        # --- SMART SCALING ---
        # Get 80% of screen size so the image isn't too huge
        screen_w = self.master.winfo_screenwidth() * 0.8
        screen_h = self.master.winfo_screenheight() * 0.8
        
        display_img = self.main_img.copy()
        w, h = display_img.size
        
        if w > screen_w or h > screen_h:
            ratio = min(screen_w / w, screen_h / h)
            new_size = (int(w * ratio), int(h * ratio))
            display_img = display_img.resize(new_size, Image.Resampling.LANCZOS)

        if self.transparency < 255:
            display_img.putalpha(self.transparency)
        
        self.img_tk = ImageTk.PhotoImage(display_img)
        
        if hasattr(self, 'canvas'):
            self.canvas.destroy()
            
        self.canvas = tk.Canvas(self.image_window, width=display_img.width, height=display_img.height)
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor="nw", image=self.img_tk)

    def substitute_vars(self, text):
        text = text.replace("%txtboxinput%", str(self.txtboxinput))
        text = text.replace("%lbixname%", str(self.lbix_name))
        text = text.replace("%filepicked%", str(self.filepicked))
        return text

    def run_script(self, script):
        lines = script.strip().splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"): continue
            try:
                self.execute_line(line)
            except Exception as e:
                messagebox.showerror("LBScript Error", f"Line: {line}\n{e}")
                break

    def execute_line(self, line):
        if line.startswith("setwintitle "):
            arg = self.strip_quotes(self.substitute_vars(line[12:].strip()))
            if self.image_window and self.image_window.winfo_exists():
                self.image_window.title(arg)

        elif line.startswith("showmsgbox"):
            m = re.match(r'showmsgbox\s+"([^"]+)"\s*,\s*"([^"]+)"', line)
            if m:
                title = self.strip_quotes(self.substitute_vars(m.group(1)))
                text = self.strip_quotes(self.substitute_vars(m.group(2)))
                messagebox.showinfo(title, text)

        elif line.startswith("wait "):
            try:
                ms = int(line[5:].strip())
                self.master.update()
                time.sleep(ms / 1000.0)
            except: pass

        elif line.startswith("transparency "):
            parts = line.split()
            op, val = parts[1].lower(), int(parts[2])
            if op == "add": self.transparency = min(255, self.transparency + val)
            elif op == "sub": self.transparency = max(0, self.transparency - val)
            self.show_image()

        elif line.startswith("showtxtbox "):
            prompt = self.strip_quotes(self.substitute_vars(line[11:].strip()))
            self.txtboxinput = simpledialog.askstring("Input", prompt)

        elif line.startswith("showfilepicker "):
            title = self.strip_quotes(self.substitute_vars(line[15:].strip()))
            fname = filedialog.askopenfilename(title=title)
            if fname: self.filepicked = fname

        elif line == "close":
            self.cmd_close()

    def cmd_close(self):
        if self.image_window and self.image_window.winfo_exists():
            self.image_window.destroy()
            self.image_window = None

# --- LBIX file handling --- #

def save_lbix(path, main_img_path, script_text):
    main_data = encode_lbimg(main_img_path)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("image.lbimg", main_data)
        z.writestr("main.lbscript", script_text)

def load_lbix(path):
    with zipfile.ZipFile(path, "r") as z:
        main_data = z.read("image.lbimg")
        script_text = z.read("main.lbscript").decode("utf-8")
    return decode_lbimg(main_data), script_text

# --- GUI --- #

class LBIXApp:
    def __init__(self, master):
        self.master = master
        self.master.title("LBIX Builder & Viewer")
        self.master.geometry("700x550")
        
        self.notebook = ttk.Notebook(master)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)

        self.builder_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.builder_frame, text="Builder")
        
        self.main_img_path_var = tk.StringVar()
        
        row = 0
        ttk.Label(self.builder_frame, text="Source PNG:").grid(row=row, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(self.builder_frame, textvariable=self.main_img_path_var, width=40).grid(row=row, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(self.builder_frame, text="Browse", command=self.browse_main_img).grid(row=row, column=2, padx=5, pady=5)
        row += 1

        ttk.Label(self.builder_frame, text="Script:").grid(row=row, column=0, sticky="nw", padx=5, pady=5)
        self.script_textbox = ScrolledText(self.builder_frame, width=60, height=15)
        self.script_textbox.grid(row=row, column=1, columnspan=2, sticky="nsew", padx=5, pady=5)
        row += 1

        self.builder_frame.grid_rowconfigure(row-1, weight=1)
        self.builder_frame.grid_columnconfigure(1, weight=1)
        ttk.Button(self.builder_frame, text="Save .LBIX", command=self.save_lbix_file).grid(row=row, column=1, sticky="e", padx=5, pady=10)

        self.viewer_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.viewer_frame, text="Viewer")
        self.lbix_open_path_var = tk.StringVar()
        ttk.Label(self.viewer_frame, text="Open LBIX:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(self.viewer_frame, textvariable=self.lbix_open_path_var, width=50).grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(self.viewer_frame, text="Browse", command=self.browse_lbix_file).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(self.viewer_frame, text="Run LBIX", command=self.run_script_from_lbix).grid(row=1, column=1, sticky="e", padx=5, pady=5)
        self.viewer_frame.grid_columnconfigure(1, weight=1)

    def browse_main_img(self):
        path = filedialog.askopenfilename(filetypes=[("PNG", "*.png")])
        if path: self.main_img_path_var.set(path)

    def save_lbix_file(self):
        img_p = self.main_img_path_var.get()
        script = self.script_textbox.get("1.0", "end").strip()
        if img_p and script:
            save_path = filedialog.asksaveasfilename(defaultextension=".lbix", filetypes=[("LBIX", "*.lbix")])
            if save_path:
                save_lbix(save_path, img_p, script)
                messagebox.showinfo("Success", "LBIX saved.")

    def browse_lbix_file(self):
        path = filedialog.askopenfilename(filetypes=[("LBIX", "*.lbix")])
        if path: self.lbix_open_path_var.set(path)

    def run_script_from_lbix(self):
        path = self.lbix_open_path_var.get()
        if os.path.exists(path):
            img, script = load_lbix(path)
            self.script_runner = LBScriptRunner(self.master, img, os.path.basename(path))
            self.script_runner.show_image()
            self.script_runner.run_script(script)

if __name__ == "__main__":
    root = tk.Tk()
    app = LBIXApp(root)
    root.mainloop()
