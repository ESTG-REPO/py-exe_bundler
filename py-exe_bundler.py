import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import shutil
import sys
import subprocess
import threading
import queue
import tempfile
import urllib.request
import zipfile
import re
import platform
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app_converter.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Get the directory where the script/executable is located
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    SCRIPT_DIR = os.path.dirname(sys.executable)
    logger.debug(f"Running as executable from {SCRIPT_DIR}")
else:
    # Running as script
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    logger.debug(f"Running as script from {SCRIPT_DIR}")

# Dependencies info
DEPENDENCIES = {
    'pyinstaller': {
        'pip_name': 'pyinstaller',
        'version': '5.13.0',
        'url': 'https://files.pythonhosted.org/packages/99/6e/d7d76d4d15f6351f1f942256633b795eec3d6c691d985869df1bf319cd9d/pyinstaller-6.12.0-py3-none-win_amd64.whl'
    }
}

class AppConverterGUI:
    def __init__(self):
        logger.debug("Initializing AppConverterGUI")

        self.window = tk.Tk()
        self.window.title("Folder to EXE Converter")
        self.window.geometry("800x600")

        # Create deps directory
        self.deps_dir = os.path.join(SCRIPT_DIR, 'dependencies')
        os.makedirs(self.deps_dir, exist_ok=True)
        logger.debug(f"Dependencies directory: {self.deps_dir}")

        # Left side - Controls
        self.controls_frame = tk.Frame(self.window)
        self.controls_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        # Source folder selection
        self.source_label = tk.Label(self.controls_frame, text="Select Folder with EXE/Python Script and Assets:")
        self.source_label.pack(pady=10)
        
        self.source_path = tk.StringVar()
        self.source_entry = tk.Entry(self.controls_frame, textvariable=self.source_path, width=50)
        self.source_entry.pack()
        
        self.source_button = tk.Button(self.controls_frame, text="Browse", command=self.browse_source)
        self.source_button.pack(pady=5)

        # Output folder selection
        self.output_label = tk.Label(self.controls_frame, text="Select Output Folder:")
        self.output_label.pack(pady=10)
        
        self.output_path = tk.StringVar()
        self.output_entry = tk.Entry(self.controls_frame, textvariable=self.output_path, width=50)
        self.output_entry.pack()
        
        self.output_button = tk.Button(self.controls_frame, text="Browse", command=self.browse_output)
        self.output_button.pack(pady=5)

        # Options Frame
        self.options_frame = tk.LabelFrame(self.controls_frame, text="Options", padx=10, pady=5)
        self.options_frame.pack(pady=10, padx=10, fill="x")

        # Window Console Option  
        self.window_var = tk.BooleanVar(value=False)
        self.window_check = tk.Checkbutton(self.options_frame, text="Window Mode (no console)", variable=self.window_var)
        self.window_check.pack(side=tk.LEFT, padx=5)

        # Convert button
        self.convert_button = tk.Button(self.controls_frame, text="Convert to Single EXE", command=self.start_conversion)
        self.convert_button.pack(pady=20)

        # Right side - Console and Progress
        self.console_frame = tk.Frame(self.window)
        self.console_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Console output
        self.console_label = tk.Label(self.console_frame, text="Console Output:")
        self.console_label.pack()

        self.console = tk.Text(self.console_frame, height=20, width=50, bg='black', fg='white')
        self.console.pack(fill=tk.BOTH, expand=True)

        # Progress bar
        self.progress_frame = tk.Frame(self.console_frame)
        self.progress_frame.pack(fill=tk.X, pady=10)

        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(self.progress_frame, variable=self.progress_var, maximum=100, mode='determinate', style='Vista.Horizontal.TProgressbar')
        self.progress.pack(fill=tk.X)

        # Configure Windows 7 style
        style = ttk.Style()
        style.theme_use('vista')
        style.configure('Vista.Horizontal.TProgressbar', background='#06B025')

        # Queue for thread communication
        self.queue = queue.Queue()
        self.is_converting = False

        # Set default paths relative to script location
        default_source = os.path.join(SCRIPT_DIR, 'source')
        default_output = os.path.join(SCRIPT_DIR, 'output')
        
        # Create default directories if they don't exist
        os.makedirs(default_source, exist_ok=True)
        os.makedirs(default_output, exist_ok=True)
        
        # Set default paths
        self.source_path.set(default_source)
        self.output_path.set(default_output)
        logger.debug(f"Default source path: {default_source}")
        logger.debug(f"Default output path: {default_output}")

    def ensure_dependencies(self):
        """Download and install required dependencies if not present"""
        logger.info("Checking dependencies...")
        self.log("Checking dependencies...")
        
        dependencies_installed = False
        for dep_name, dep_info in DEPENDENCIES.items():
            dep_path = os.path.join(self.deps_dir, f"{dep_name}-{dep_info['version']}")
            logger.debug(f"Checking dependency: {dep_name} at {dep_path}")
            
            if not os.path.exists(dep_path):
                dependencies_installed = True
                logger.info(f"Downloading {dep_name}...")
                self.log(f"Downloading {dep_name}...")
                
                try:
                    # Download dependency
                    temp_file = os.path.join(tempfile.gettempdir(), f"{dep_name}.tar.gz")
                    urllib.request.urlretrieve(dep_info['url'], temp_file)
                    
                    # Extract to deps directory
                    with zipfile.ZipFile(temp_file, 'r') as zip_ref:
                        zip_ref.extractall(dep_path)
                    
                    os.remove(temp_file)
                    
                    logger.info(f"Installed {dep_name} successfully")
                    self.log(f"Installed {dep_name} successfully")
                except Exception as e:
                    logger.error(f"Failed to install {dep_name}: {str(e)}")
                    raise
            
            # Add to Python path
            if dep_path not in sys.path:
                sys.path.insert(0, dep_path)
                logger.debug(f"Added {dep_path} to Python path")
                
        if dependencies_installed:
            logger.info("Dependencies installed. Restarting application...")
            self.log("Dependencies installed. Restarting application...")
            self.window.after(2000, self.window.destroy)  # Close window after 2 seconds
            return True
        return False

    def log(self, message):
        logger.debug(f"GUI Log: {message}")
        self.console.insert(tk.END, f"{message}\n")
        self.console.see(tk.END)
        self.window.update()

    def update_progress(self, value):
        logger.debug(f"Progress update: {value}%")
        self.progress_var.set(value)
        self.window.update()

    def browse_source(self):
        try:
            folder = filedialog.askdirectory(initialdir=self.source_path.get())
            if folder:
                logger.debug(f"Source folder selected: {folder}")
                self.source_path.set(folder)
                self.log(f"Source folder selected: {folder}")
        except Exception as e:
            logger.error(f"Error selecting source folder: {str(e)}")
            messagebox.showerror("Error", f"Failed to select source folder: {str(e)}")

    def browse_output(self):
        try:
            folder = filedialog.askdirectory(initialdir=self.output_path.get())
            if folder:
                logger.debug(f"Output folder selected: {folder}")
                self.output_path.set(folder)
                self.log(f"Output folder selected: {folder}")
        except Exception as e:
            logger.error(f"Error selecting output folder: {str(e)}")
            messagebox.showerror("Error", f"Failed to select output folder: {str(e)}")

    def start_conversion(self):
        if self.is_converting:
            logger.debug("Conversion already in progress")
            return
            
        logger.info("Starting conversion process")
        self.is_converting = True
        self.convert_button.config(state='disabled')
        
        # Start conversion in separate thread
        conversion_thread = threading.Thread(target=self.convert_app)
        conversion_thread.daemon = True
        conversion_thread.start()
        
        # Start checking queue for messages
        self.window.after(100, self.check_queue)

    def check_queue(self):
        try:
            while True:
                msg_type, msg = self.queue.get_nowait()
                logger.debug(f"Queue message received: {msg_type} - {msg}")
                
                if msg_type == "log":
                    self.log(msg)
                elif msg_type == "progress":
                    self.update_progress(msg)
                elif msg_type == "error":
                    logger.error(msg)
                    messagebox.showerror("Error", msg)
                elif msg_type == "success":
                    logger.info(msg)
                    messagebox.showinfo("Success", msg)
                elif msg_type == "done":
                    self.is_converting = False
                    self.convert_button.config(state='normal')
                    return
                
                self.queue.task_done()
                
        except queue.Empty:
            if self.is_converting:
                self.window.after(100, self.check_queue)

    def convert_app(self):
        try:
            logger.info("Starting app conversion")
            # Ensure dependencies are available
            if self.ensure_dependencies():
                return  # Script will restart after dependencies are installed
            
            source_path = self.source_path.get().strip()
            output_path = self.output_path.get().strip()
            logger.debug(f"Source path: {source_path}")
            logger.debug(f"Output path: {output_path}")

            if not all([source_path, output_path]):
                logger.error("Source or output path not specified")
                self.queue.put(("error", "Please select source and output folders"))
                self.queue.put(("done", None))
                return

            if not os.path.exists(source_path):
                logger.error(f"Source folder does not exist: {source_path}")
                self.queue.put(("error", f"Source folder does not exist: {source_path}"))
                self.queue.put(("done", None))
                return

            self.queue.put(("progress", 0))
            self.queue.put(("log", "Starting conversion process..."))
            self.queue.put(("log", f"Scanning source directory: {source_path}"))

            # Find the exe or py file in source folder
            exe_files = [f for f in os.listdir(source_path) if f.endswith('.exe')]
            py_files = [f for f in os.listdir(source_path) if f.endswith('.py')]
            
            if not exe_files and not py_files:
                logger.error("No EXE or Python files found in source folder")
                self.queue.put(("error", "No EXE or Python files found in source folder"))
                self.queue.put(("done", None))
                return
            
            if exe_files:
                main_file = os.path.join(source_path, exe_files[0])
                is_python = False
                logger.info(f"Found EXE file: {main_file}")
                self.queue.put(("log", f"Found EXE file: {main_file}"))
            else:
                main_file = os.path.join(source_path, py_files[0])
                is_python = True
                logger.info(f"Found Python file: {main_file}")
                self.queue.put(("log", f"Found Python file: {main_file}"))
                
            self.queue.put(("progress", 20))

            if not os.path.exists(output_path):
                try:
                    os.makedirs(output_path)
                    logger.debug(f"Created output directory: {output_path}")
                    self.queue.put(("log", f"Created output directory: {output_path}"))
                except Exception as e:
                    logger.error(f"Could not create output directory: {str(e)}")
                    self.queue.put(("error", f"Could not create output directory: {str(e)}"))
                    self.queue.put(("done", None))
                    return

            self.queue.put(("log", "Creating launcher script..."))
            self.queue.put(("progress", 40))

            # Create a temporary Python script that launches the exe/py file
            temp_script = os.path.join(source_path, "launcher.py")
            try:
                with open(temp_script, "w") as f:
                    if is_python:
                        f.write(f'''
import os
import sys
import logging
import runpy

logging.basicConfig(level=logging.DEBUG, 
                  filename='launcher.log',
                  format='%(asctime)s - %(levelname)s - %(message)s')

if getattr(sys, 'frozen', False):
    # Running in a bundle
    base_dir = sys._MEIPASS
    logging.debug(f"Running from frozen bundle at {{base_dir}}")
else:
    # Running in normal Python environment
    base_dir = os.path.dirname(os.path.abspath(__file__))
    logging.debug(f"Running from Python environment at {{base_dir}}")

script_name = "{os.path.basename(main_file)}"
script_path = os.path.join(base_dir, script_name)
logging.debug(f"Launching Python script: {{script_path}}")

try:
    sys.path.insert(0, base_dir)
    runpy.run_path(script_path)
except Exception as e:
    logging.error(f"Failed to launch Python script: {{str(e)}}")
    raise
''')
                    else:
                        f.write(f'''
import os
import sys
import subprocess
import logging

logging.basicConfig(level=logging.DEBUG, 
                  filename='launcher.log',
                  format='%(asctime)s - %(levelname)s - %(message)s')

if getattr(sys, 'frozen', False):
    # Running in a bundle
    base_dir = sys._MEIPASS
    logging.debug(f"Running from frozen bundle at {{base_dir}}")
else:
    # Running in normal Python environment
    base_dir = os.path.dirname(os.path.abspath(__file__))
    logging.debug(f"Running from Python environment at {{base_dir}}")

exe_name = "{os.path.basename(main_file)}"
exe_path = os.path.join(base_dir, exe_name)
logging.debug(f"Launching executable: {{exe_path}}")

try:
    subprocess.run([exe_path], check=True)
except Exception as e:
    logging.error(f"Failed to launch executable: {{str(e)}}")
    raise
''')
                logger.debug("Created launcher script successfully")
            except Exception as e:
                logger.error(f"Failed to create launcher script: {str(e)}")
                raise

            self.queue.put(("log", "Configuring PyInstaller..."))
            self.queue.put(("progress", 60))

            try:
                # Import PyInstaller after ensuring dependencies
                import PyInstaller.__main__

                # Build PyInstaller command
                pyinstaller_args = [
                    temp_script,
                    '--distpath', output_path,
                    '--workpath', os.path.join(output_path, 'build'),
                    '--specpath', output_path,
                    '--onefile',
                    '--add-data', f"{source_path}/*;."
                ]
                
                if self.window_var.get():
                    pyinstaller_args.append('--windowed')
                    logger.debug("Window mode enabled")
                    self.queue.put(("log", "Window mode enabled - console will be hidden in final EXE"))

                logger.info("Running PyInstaller...")
                self.queue.put(("log", "Running PyInstaller..."))
                self.queue.put(("progress", 80))

                # Run PyInstaller
                PyInstaller.__main__.run(pyinstaller_args)
                logger.info("PyInstaller completed successfully")

            except Exception as e:
                logger.error(f"PyInstaller failed: {str(e)}")
                raise

            try:
                # Clean up temporary files
                os.remove(temp_script)
                build_dir = os.path.join(output_path, 'build')
                spec_file = os.path.join(output_path, 'launcher.spec')
                
                if os.path.exists(build_dir):
                    shutil.rmtree(build_dir)
                if os.path.exists(spec_file):
                    os.remove(spec_file)
                    
                logger.debug("Cleaned up temporary files and build artifacts")
                self.queue.put(("log", "Cleaned up temporary files and build artifacts"))
                self.queue.put(("progress", 100))
            except Exception as e:
                logger.warning(f"Failed to clean up temporary files: {str(e)}")

            logger.info("Conversion completed successfully")
            self.queue.put(("log", "Conversion completed successfully!"))
            self.queue.put(("success", f"Folder converted to single EXE successfully!\nOutput location: {output_path}"))

        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.queue.put(("log", f"ERROR: {error_msg}"))
            self.queue.put(("error", error_msg))
        
        finally:
            self.queue.put(("done", None))

    def run(self):
        logger.info("Starting application")
        self.window.mainloop()

if __name__ == "__main__":
    try:
        logger.info("Application starting")
        app = AppConverterGUI()
        app.run()
    except Exception as e:
        logger.critical("Application crashed", exc_info=True)
        messagebox.showerror("Critical Error", f"Application crashed: {str(e)}")
