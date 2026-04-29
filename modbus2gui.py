import os
import csv
import time
import datetime
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pymodbus.client import ModbusTcpClient
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

LOG_DIR = "modbus_logs"
os.makedirs(LOG_DIR, exist_ok=True)

# ----------------------------
# Helper: Create timestamped CSV
# ----------------------------
def create_new_csv(num_coils, num_regs):
    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = os.path.join(LOG_DIR, f"modbus_data_{timestamp_str}.csv")

    fieldnames = ["timestamp"]
    fieldnames += [f"coil_{i+1}" for i in range(num_coils)]
    fieldnames += [f"reg_{i+1}" for i in range(num_regs)]

    with open(filename, "w", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

    print(f"[*] Created new log file: {filename}")
    return filename, fieldnames

# ----------------------------
# Modbus polling thread
# ----------------------------
class ModbusLogger(threading.Thread):
    def __init__(self, ip, port, start_addr, num_coils, num_regs, poll_interval, update_callback):
        super().__init__(daemon=True)
        self.ip = ip
        self.port = port
        self.start_addr = start_addr
        self.num_coils = num_coils
        self.num_regs = num_regs
        self.poll_interval = poll_interval
        self.update_callback = update_callback
        self.stop_flag = threading.Event()
        self.client = None

    def run(self):
        try:
            self.client = ModbusTcpClient(self.ip, port=self.port)
            if not self.client.connect():
                messagebox.showerror("Connection Error", f"Could not connect to {self.ip}:{self.port}")
                return

            print(f"[+] Connected to {self.ip}:{self.port}")
            csv_file, fieldnames = create_new_csv(self.num_coils, self.num_regs)
            log_start_time = time.time()

            while not self.stop_flag.is_set():
                # Rotate file hourly
                if time.time() - log_start_time >= 3600:
                    csv_file, fieldnames = create_new_csv(self.num_coils, self.num_regs)
                    log_start_time = time.time()

                row = {"timestamp": datetime.datetime.now().isoformat()}

                # Read coils
                coils = self.client.read_coils(self.start_addr, self.num_coils)
                coil_values = []
                if hasattr(coils, "bits"):
                    coil_values = [int(bit) for bit in coils.bits[:self.num_coils]]
                    for i, bit in enumerate(coil_values):
                        row[f"coil_{i+1}"] = bit

                # Read registers
                regs = self.client.read_holding_registers(self.start_addr, self.num_regs)
                reg_values = []
                if hasattr(regs, "registers"):
                    reg_values = regs.registers[:self.num_regs]
                    for i, val in enumerate(reg_values):
                        row[f"reg_{i+1}"] = val

                # Write to CSV safely
                success = False
                while not success and not self.stop_flag.is_set():
                    try:
                        with open(csv_file, "a", newline='') as f:
                            writer = csv.DictWriter(f, fieldnames=fieldnames)
                            writer.writerow(row)
                        success = True
                    except PermissionError:
                        print("[!] CSV file open in Excel. Retrying in 2s...")
                        time.sleep(2)

                # Update GUI with new values
                self.update_callback(coil_values, reg_values)

                time.sleep(self.poll_interval)

        except Exception as e:
            messagebox.showerror("Error", f"Error during Modbus polling: {e}")
        finally:
            if self.client:
                self.client.close()
            print("[*] Modbus logger stopped.")

    def stop(self):
        self.stop_flag.set()

# ----------------------------
# GUI Application
# ----------------------------
class ModbusGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Modbus Logger & Dynamic Grapher")
        self.geometry("1000x700")

        self.logger_thread = None
        self.poll_interval = 1
        self.num_coils = 10
        self.num_regs = 10
        self.coil_data = {}
        self.reg_data = {}

        self.create_widgets()
        self.create_plot_area()

    # ----------------------------
    # UI Layout
    # ----------------------------
    def create_widgets(self):
        frame = ttk.LabelFrame(self, text="Connection Settings")
        frame.pack(padx=10, pady=10, fill="x")

        ttk.Label(frame, text="PLC IP:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.ip_entry = ttk.Entry(frame)
        self.ip_entry.insert(0, "127.0.0.1")
        self.ip_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(frame, text="Port:").grid(row=0, column=2, sticky="e")
        self.port_entry = ttk.Entry(frame)
        self.port_entry.insert(0, "502")
        self.port_entry.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(frame, text="Polling (s):").grid(row=0, column=4, sticky="e")
        self.poll_entry = ttk.Entry(frame)
        self.poll_entry.insert(0, "1")
        self.poll_entry.grid(row=0, column=5, padx=5, pady=5)

        ttk.Label(frame, text="Coils:").grid(row=1, column=0, sticky="e")
        self.coil_entry = ttk.Entry(frame)
        self.coil_entry.insert(0, "10")
        self.coil_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(frame, text="Registers:").grid(row=1, column=2, sticky="e")
        self.reg_entry = ttk.Entry(frame)
        self.reg_entry.insert(0, "10")
        self.reg_entry.grid(row=1, column=3, padx=5, pady=5)

        ttk.Button(frame, text="Start Logging", command=self.start_logging).grid(row=2, column=1, pady=10)
        ttk.Button(frame, text="Stop", command=self.stop_logging).grid(row=2, column=2, pady=10)

    # ----------------------------
    # Matplotlib area
    # ----------------------------
    def create_plot_area(self):
        self.fig, self.axes = plt.subplots(1, 1, figsize=(9, 5))
        self.fig.subplots_adjust(hspace=0.4)
        self.fig.suptitle("Dynamic Coils and Registers Charts")
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(padx=10, pady=10, fill="both", expand=True)

    # ----------------------------
    # Start/Stop Logic
    # ----------------------------
    def start_logging(self):
        if self.logger_thread and self.logger_thread.is_alive():
            messagebox.showinfo("Info", "Logger is already running.")
            return

        try:
            ip = self.ip_entry.get()
            port = int(self.port_entry.get())
            self.poll_interval = float(self.poll_entry.get())
            self.num_coils = int(self.coil_entry.get())
            self.num_regs = int(self.reg_entry.get())
        except ValueError:
            messagebox.showerror("Input Error", "Please enter valid numeric values.")
            return

        self.coil_data.clear()
        self.reg_data.clear()
        self.axes.clear()
        self.fig.clf()

        self.logger_thread = ModbusLogger(
            ip, port, 0, self.num_coils, self.num_regs, self.poll_interval, self.update_graphs
        )
        self.logger_thread.start()
        print("[*] Logging started.")

    def stop_logging(self):
        if self.logger_thread:
            self.logger_thread.stop()
            self.logger_thread.join(timeout=2)
            messagebox.showinfo("Stopped", "Modbus logging stopped.")
        else:
            messagebox.showinfo("Info", "No logger is currently running.")

    # ----------------------------
    # Dynamic Graph Management
    # ----------------------------
    def update_graphs(self, coil_values, reg_values):
        # Collect data
        for i, val in enumerate(coil_values):
            key = f"coil_{i+1}"
            if key not in self.coil_data:
                self.coil_data[key] = []
            self.coil_data[key].append(val)

        for i, val in enumerate(reg_values):
            key = f"reg_{i+1}"
            if key not in self.reg_data:
                self.reg_data[key] = []
            self.reg_data[key].append(val)

        # Determine active signals (non-zero ever)
        active_coils = [k for k, v in self.coil_data.items() if any(val != 0 for val in v)]
        active_regs = [k for k, v in self.reg_data.items() if any(val != 0 for val in v)]

        total_plots = len(active_coils) + len(active_regs)
        if total_plots == 0:
            return

        # Rebuild subplots dynamically
        self.fig.clf()
        self.fig.suptitle("Dynamic Coils and Registers Charts")

        axes = self.fig.subplots(total_plots, 1, sharex=True)
        if total_plots == 1:
            axes = [axes]

        idx = 0
        for key in active_coils:
            ax = axes[idx]
            ax.plot(self.coil_data[key], 'r.-')
            ax.set_ylabel(key)
            ax.grid(True)
            idx += 1

        for key in active_regs:
            ax = axes[idx]
            ax.plot(self.reg_data[key], 'b.-')
            ax.set_ylabel(key)
            ax.grid(True)
            idx += 1

        self.fig.tight_layout()
        self.canvas.draw_idle()

if __name__ == "__main__":
    app = ModbusGUI()
    app.mainloop()
