# ====================== FULL PYTHON GUI PROGRAM ======================
# Save as: lcd1602_video_streamer.py
# Run with: pip install customtkinter pyserial numpy pillow
# Then: python lcd1602_video_streamer.py

import customtkinter as ctk
from tkinter import filedialog, messagebox
import serial
import serial.tools.list_ports
import subprocess
import os
import time
import threading
import numpy as np

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class LCDVideoStreamer(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("24×18 → LCD1602 Video Streamer (FFmpeg + Custom Chars)")
        self.geometry("780x620")
        self.resizable(False, False)
        
        self.video_path = None
        self.ser = None
        self.running = False
        self.thread = None
        self.temp_raw = "lcd_temp.raw"

        self.create_widgets()

    def create_widgets(self):
        ctk.CTkLabel(self, text="LCD1602 Video Streamer", 
                     font=ctk.CTkFont(size=28, weight="bold")).pack(pady=20)

        # === VIDEO SECTION ===
        ctk.CTkLabel(self, text="1. Select Video File (any format)", 
                     font=ctk.CTkFont(size=14)).pack(anchor="w", padx=40)
        self.btn_video = ctk.CTkButton(self, text="Browse Video File", width=300,
                                       command=self.select_video)
        self.btn_video.pack(pady=8)
        self.lbl_video = ctk.CTkLabel(self, text="No file selected", text_color="gray")
        self.lbl_video.pack(pady=5)

        # === SERIAL PORT ===
        ctk.CTkLabel(self, text="2. Serial Port (Arduino)", 
                     font=ctk.CTkFont(size=14)).pack(anchor="w", padx=40, pady=(20,0))
        self.port_var = ctk.StringVar()
        self.combo_port = ctk.CTkComboBox(self, variable=self.port_var, width=300)
        self.combo_port.pack(pady=8)
        ctk.CTkButton(self, text="Refresh Ports", width=140,
                      command=self.refresh_ports).pack()

        # === FPS ===
        ctk.CTkLabel(self, text="3. Target FPS (3–12 recommended for smooth playback)", 
                     font=ctk.CTkFont(size=14)).pack(anchor="w", padx=40, pady=(20,0))
        self.fps_var = ctk.IntVar(value=8)
        self.slider_fps = ctk.CTkSlider(self, from_=3, to=20, number_of_steps=9,
                                        variable=self.fps_var)
        self.slider_fps.pack(pady=8)
        self.lbl_fps = ctk.CTkLabel(self, text="8 FPS")
        self.lbl_fps.pack()
        self.slider_fps.configure(command=lambda v: self.lbl_fps.configure(text=f"{int(v)} FPS"))

        # === START / STOP ===
        self.btn_start = ctk.CTkButton(self, text="Convert with FFmpeg & START Streaming",
                                       width=340, height=60, fg_color="green", font=ctk.CTkFont(size=16, weight="bold"),
                                       command=self.toggle_stream)
        self.btn_start.pack(pady=30)

        self.status = ctk.CTkLabel(self, text="Ready – Select video + COM port", text_color="lightblue", 
                                   font=ctk.CTkFont(size=14))
        self.status.pack(pady=10)

        self.refresh_ports()

    def select_video(self):
        path = filedialog.askopenfilename(
            title="Select video",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.webm *.flv")]
        )
        if path:
            self.video_path = path
            name = os.path.basename(path)
            self.lbl_video.configure(text=(name if len(name) < 50 else name[:47]+"..."))

    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.combo_port.configure(values=ports if ports else ["No ports found"])
        if ports:
            self.combo_port.set(ports[0])

    def toggle_stream(self):
        if not self.running:
            self.start_streaming()
        else:
            self.stop_streaming()

    def start_streaming(self):
        if not self.video_path:
            messagebox.showerror("Error", "Please select a video file first!")
            return
        port = self.port_var.get()
        if not port or "No ports" in port:
            messagebox.showerror("Error", "Please select a valid COM port!")
            return

        try:
            self.ser = serial.Serial(port, 1000000, timeout=0.1)
            time.sleep(2.5)  # Arduino reset time
        except Exception as e:
            messagebox.showerror("Serial Error", str(e))
            return

        self.running = True
        self.btn_start.configure(text="STOP Streaming", fg_color="red")
        self.status.configure(text="FFmpeg is converting video...", text_color="orange")

        self.thread = threading.Thread(target=self.ffmpeg_and_stream, daemon=True)
        self.thread.start()

    def stop_streaming(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.btn_start.configure(text="Convert with FFmpeg & START Streaming", fg_color="green")
        self.status.configure(text="Stopped", text_color="red")

    def ffmpeg_and_stream(self):
        fps = self.fps_var.get()

        # ================== AUTOMATIC FFmpeg CONVERSION ==================
        cmd = [
            'ffmpeg', '-y', '-i', self.video_path,
            '-vf', 'scale=20:16:flags=neighbor',   # perfect for LCD1602 (5px/char × 8 chars)
            '-r', str(fps),
            '-pix_fmt', 'gray',
            '-f', 'rawvideo',
            self.temp_raw
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                raise Exception(result.stderr)
        except Exception as e:
            self.status.configure(text=f"FFmpeg Error: {str(e)[:80]}", text_color="red")
            self.running = False
            return

        self.status.configure(text=f"Streaming @ {fps} FPS (20×16 pixels)...", text_color="lime")

        # ================== STREAMING LOOP ==================
        frame_size = 20 * 16
        delay = 1.0 / fps

        with open(self.temp_raw, "rb") as f:
            while self.running:
                frame_bytes = f.read(frame_size)
                if len(frame_bytes) < frame_size:
                    f.seek(0)
                    continue

                # Convert raw grayscale → binary → 128 bytes (64 top + 64 bottom)
                img = np.frombuffer(frame_bytes, dtype=np.uint8).reshape(16, 20)
                binary = 1-(img > 128).astype(np.uint8)

                packet = bytearray()

                # Top half (LCD row 0)
                for cx in range(4):                 
                    for row in range(8):
                        byte = 0
                        for bit in range(5):          
                            if binary[row][cx * 5 + bit]:
                                byte |= (1 << (4 - bit))
                        packet.append(byte)

                # Bottom half (LCD row 1)
                for cx in range(4):
                    for row in range(8):
                        byte = 0
                        for bit in range(5):
                            if binary[8 + row][cx * 5 + bit]:
                                byte |= (1 << (4 - bit))
                        packet.append(byte)

                # Send to Arduino
                try:
                    if self.ser and self.ser.is_open:
                        self.ser.write(packet)
                except:
                    break

                time.sleep(delay)

        # Cleanup
        if os.path.exists(self.temp_raw):
            os.remove(self.temp_raw)

if __name__ == "__main__":
    app = LCDVideoStreamer()
    app.mainloop()