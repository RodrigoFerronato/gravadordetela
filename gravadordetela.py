import tkinter as tk
from tkinter import ttk
import cv2
import numpy as np
import pyautogui
import threading
import sounddevice as sd
import wave
import os
import time
from moviepy.editor import VideoFileClip

class ScreenRecorder:
    def __init__(self, root):
        self.root = root
        self.root.title("Screen Recorder")
        self.is_recording = False
        self.is_paused = False
        self.record_audio = tk.BooleanVar()
        self.start_time = None
        self.pause_start_time = None
        self.total_pause_duration = 0
        self.selection = None

        self.setup_ui()
        self.video_writer = None
        self.audio_writer = None
        self.frames = []
        self.audio_frames = []

    def setup_ui(self):
        self.record_button = ttk.Button(self.root, text="Record", command=self.select_area)
        self.record_button.grid(row=0, column=0, padx=10, pady=10)
        
        self.stop_button = ttk.Button(self.root, text="Stop", command=self.stop_recording, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=10, pady=10)
        
        self.pause_button = ttk.Button(self.root, text="Pause", command=self.pause_recording, state=tk.DISABLED)
        self.pause_button.grid(row=0, column=2, padx=10, pady=10)
        
        self.resume_button = ttk.Button(self.root, text="Resume", command=self.resume_recording, state=tk.DISABLED)
        self.resume_button.grid(row=0, column=3, padx=10, pady=10)
        
        self.audio_check = ttk.Checkbutton(self.root, text="Record Audio", variable=self.record_audio)
        self.audio_check.grid(row=1, column=0, columnspan=4, pady=10)

        self.time_label = ttk.Label(self.root, text="00:00:00")
        self.time_label.grid(row=2, column=0, columnspan=4, pady=10)

    def select_area(self):
        self.selection_window = tk.Toplevel(self.root)
        self.selection_window.attributes("-fullscreen", True)
        self.selection_window.attributes("-alpha", 0.3)
        self.selection_window.config(bg='gray')

        self.canvas = tk.Canvas(self.selection_window, bg='gray')
        self.canvas.pack(fill=tk.BOTH, expand=tk.YES)

        self.canvas.bind("<ButtonPress-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)
        
        self.selection_rectangle = None
        self.start_x = self.start_y = 0

    def on_mouse_press(self, event):
        self.start_x, self.start_y = event.x, event.y
        if self.selection_rectangle:
            self.canvas.delete(self.selection_rectangle)
        self.selection_rectangle = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=2
        )

    def on_mouse_drag(self, event):
        self.canvas.coords(self.selection_rectangle, self.start_x, self.start_y, event.x, event.y)

    def on_mouse_release(self, event):
        end_x, end_y = event.x, event.y
        self.selection = (self.start_x, self.start_y, end_x, end_y)
        self.selection_window.destroy()
        self.start_recording()

    def start_recording(self):
        self.is_recording = True
        self.is_paused = False
        self.start_time = time.time()
        self.total_pause_duration = 0
        self.update_time_label()
        self.record_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.NORMAL)

        x1, y1, x2, y2 = self.selection
        self.region = (x1, y1, x2 - x1, y2 - y1)
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        self.video_writer = cv2.VideoWriter('output_temp.avi', fourcc, 20.0, (x2 - x1, y2 - y1))
        self.frames = []
        self.audio_frames = []

        if self.record_audio.get():
            self.audio_thread = threading.Thread(target=self.record_audio_data)
            self.audio_thread.start()

        self.video_thread = threading.Thread(target=self.record_video_data)
        self.video_thread.start()

    def update_time_label(self):
        if self.is_recording:
            if not self.is_paused:
                elapsed_time = int(time.time() - self.start_time - self.total_pause_duration)
                hrs, secs = divmod(elapsed_time, 3600)
                mins, secs = divmod(secs, 60)
                self.time_label.config(text=f"{hrs:02}:{mins:02}:{secs:02}")
            self.root.after(1000, self.update_time_label)

    def record_audio_data(self):
        def callback(indata, frames, time, status):
            self.audio_frames.append(indata.copy())

        with sd.InputStream(samplerate=44100, channels=2, callback=callback):
            while self.is_recording:
                sd.sleep(1000)
    
    def record_video_data(self):
        while self.is_recording:
            if not self.is_paused:
                img = pyautogui.screenshot(region=self.region)
                frame = np.array(img)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.frames.append(frame)
                self.video_writer.write(frame)
                cv2.imshow('Recording', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        self.video_writer.release()
        cv2.destroyAllWindows()

    def pause_recording(self):
        self.is_paused = True
        self.pause_start_time = time.time()
        self.pause_button.config(state=tk.DISABLED)
        self.resume_button.config(state=tk.NORMAL)

    def resume_recording(self):
        self.is_paused = False
        self.total_pause_duration += time.time() - self.pause_start_time
        self.pause_button.config(state=tk.NORMAL)
        self.resume_button.config(state=tk.DISABLED)

    def stop_recording(self):
        self.is_recording = False
        self.record_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.pause_button.config(state=tk.DISABLED)
        self.resume_button.config(state=tk.DISABLED)

        if self.record_audio.get():
            self.audio_thread.join()
            self.save_audio()

        self.video_thread.join()
        self.convert_to_mp4()
        self.move_to_videos()

    def save_audio(self):
        wf = wave.open('output_temp.wav', 'wb')
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(b''.join(self.audio_frames))
        wf.close()

    def convert_to_mp4(self):
        video = VideoFileClip("output_temp.avi")
        if self.record_audio.get():
            audio = VideoFileClip("output_temp.wav").audio
            video = video.set_audio(audio)
        video.write_videofile("output.mp4", codec="libx264")
        os.remove("output_temp.avi")
        if self.record_audio.get():
            os.remove("output_temp.wav")

    def move_to_videos(self):
        videos_dir = os.path.join(os.path.expanduser("~"), "Videos")
        if not os.path.exists(videos_dir):
            os.makedirs(videos_dir)
        os.rename("output.mp4", os.path.join(videos_dir, "output.mp4"))

if __name__ == "__main__":
    root = tk.Tk()
    app = ScreenRecorder(root)
    root.mainloop()
