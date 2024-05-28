import tkinter as tk
from tkinter import ttk, simpledialog
import cv2
import numpy as np
import pyautogui
import threading
import pyaudio
import wave
import os
import time
from moviepy.editor import VideoFileClip, AudioFileClip

class ScreenRecorder:
    def __init__(self, root):
        self.root = root
        self.root.title("Screen Recorder")
        self.is_recording = False
        self.is_paused = False
        self.record_mic_audio = tk.BooleanVar()
        self.record_sys_audio = tk.BooleanVar()
        self.start_time = None
        self.pause_start_time = None
        self.total_pause_duration = 0
        self.selection = None

        self.setup_ui()
        self.video_writer = None
        self.frames = []
        self.audio_frames = []
        self.audio_streams = []

    def setup_ui(self):
        self.record_button = ttk.Button(self.root, text="Record", command=self.select_area)
        self.record_button.grid(row=0, column=0, padx=10, pady=10)
        
        self.stop_button = ttk.Button(self.root, text="Stop", command=self.stop_recording, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=10, pady=10)
        
        self.pause_button = ttk.Button(self.root, text="Pause", command=self.pause_recording, state=tk.DISABLED)
        self.pause_button.grid(row=0, column=2, padx=10, pady=10)
        
        self.resume_button = ttk.Button(self.root, text="Resume", command=self.resume_recording, state=tk.DISABLED)
        self.resume_button.grid(row=0, column=3, padx=10, pady=10)
        
        self.mic_audio_check = ttk.Checkbutton(self.root, text="Record Microphone Audio", variable=self.record_mic_audio)
        self.mic_audio_check.grid(row=1, column=0, columnspan=4, pady=10)

        self.sys_audio_check = ttk.Checkbutton(self.root, text="Record System Audio", variable=self.record_sys_audio)
        self.sys_audio_check.grid(row=2, column=0, columnspan=4, pady=10)

        self.time_label = ttk.Label(self.root, text="00:00:00")
        self.time_label.grid(row=3, column=0, columnspan=4, pady=10)

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

        if self.record_mic_audio.get() or self.record_sys_audio.get():
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
        p = pyaudio.PyAudio()

        def callback(in_data, frame_count, time_info, status):
            self.audio_frames.append(in_data)
            return (in_data, pyaudio.paContinue)

        try:
            if self.record_mic_audio.get():
                mic_stream = p.open(format=pyaudio.paInt16,
                                    channels=1,  # Ajustar para 1 canal
                                    rate=44100,
                                    input=True,
                                    frames_per_buffer=1024,
                                    stream_callback=callback)
                self.audio_streams.append(mic_stream)

            if self.record_sys_audio.get():
                sys_device_index = self.get_loopback_device_index(p)
                if sys_device_index is not None:
                    sys_stream = p.open(format=pyaudio.paInt16,
                                        channels=2,  # Ajustar para 2 canais
                                        rate=44100,
                                        input=True,
                                        input_device_index=sys_device_index,
                                        frames_per_buffer=1024,
                                        stream_callback=callback)
                    self.audio_streams.append(sys_stream)

            for stream in self.audio_streams:
                stream.start_stream()

            while self.is_recording:
                time.sleep(0.1)

            for stream in self.audio_streams:
                stream.stop_stream()
                stream.close()

        except Exception as e:
            print(f"Erro ao gravar áudio: {e}")
        finally:
            p.terminate()

    def get_loopback_device_index(self, p):
        for i in range(p.get_device_count()):
            dev_info = p.get_device_info_by_index(i)
            if 'loopback' in dev_info['name'].lower() or 'stereo mix' in dev_info['name'].lower():
                return i
        return None

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

        if self.record_mic_audio.get() or self.record_sys_audio.get():
            self.audio_thread.join()
            self.save_audio()

        self.video_thread.join()
        self.convert_to_mp4()
        self.move_to_videos()

    def save_audio(self):
        wf = wave.open('output_temp.wav', 'wb')
        wf.setnchannels(1 if self.record_mic_audio.get() and not self.record_sys_audio.get() else 2)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(b''.join(self.audio_frames))
        wf.close()

    def convert_to_mp4(self):
        video = VideoFileClip("output_temp.avi")
        if self.record_mic_audio.get() or self.record_sys_audio.get():
            audio = AudioFileClip("output_temp.wav")
            video = video.set_audio(audio)
        video.write_videofile("output.mp4", codec="libx264")
        os.remove("output_temp.avi")
        if self.record_mic_audio.get() or self.record_sys_audio.get():
            os.remove("output_temp.wav")

    def move_to_videos(self):
        video_name = simpledialog.askstring("Save As", "Enter the name of the video file:", parent=self.root)
        if not video_name:
            video_name = "output"
        videos_dir = os.path.join(os.path.expanduser("~"), "Videos")
        if not os.path.exists(videos_dir):
            os.makedirs(videos_dir)
        os.rename("output.mp4", os.path.join(videos_dir, f"{video_name}.mp4"))

if __name__ == "__main__":
    root = tk.Tk()
    app = ScreenRecorder(root)
    root.mainloop()
