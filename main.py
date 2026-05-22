import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import subprocess
import json
import threading
import os
import queue
import re
import shutil
from pathlib import Path

# =========================================================
# CONFIG
# =========================================================

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"

VIDEO_SAFE_CODECS = ["h264", "hevc", "av1"]
AUDIO_SAFE_CODECS = ["aac", "mp3", "ac3"]

# =========================================================
# LOGGER
# =========================================================

log_queue = queue.Queue()


def log(msg):
    log_queue.put(msg)


def update_logs():
    while not log_queue.empty():
        msg = log_queue.get_nowait()

        output.insert(tk.END, msg + "\n")
        output.see(tk.END)

    root.after(100, update_logs)


# =========================================================
# FFMPEG CHECK
# =========================================================

def check_ffmpeg():
    try:
        subprocess.run(
            [FFMPEG, "-version"],
            capture_output=True,
            check=True
        )

        subprocess.run(
            [FFPROBE, "-version"],
            capture_output=True,
            check=True
        )

        return True

    except Exception:
        return False


# =========================================================
# FILE ANALYSIS
# =========================================================

def analyze_file(path):

    cmd = [
        FFPROBE,
        "-v", "error",
        "-show_streams",
        "-show_format",
        "-print_format", "json",
        path
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    data = json.loads(result.stdout)

    info = {
        "video": None,
        "audios": [],
        "subtitles": [],
        "duration": 0
    }

    if "format" in data:
        info["duration"] = float(
            data["format"].get("duration", 0)
        )

    for stream in data["streams"]:

        codec = stream.get("codec_name")
        stream_type = stream.get("codec_type")

        language = stream.get(
            "tags",
            {}
        ).get("language", "und")

        if stream_type == "video":

            info["video"] = codec

        elif stream_type == "audio":

            info["audios"].append({
                "codec": codec,
                "language": language,
                "channels": stream.get("channels", 2)
            })

        elif stream_type == "subtitle":

            info["subtitles"].append({
                "codec": codec,
                "language": language
            })

    return info


# =========================================================
# AUDIO PRIORITY
# =========================================================

def choose_best_audio(audios):

    priority = {
        "aac": 1,
        "ac3": 2,
        "eac3": 3,
        "mp3": 4
    }

    sorted_audio = sorted(
        audios,
        key=lambda x: priority.get(
            x["codec"],
            99
        )
    )

    return sorted_audio[0] if sorted_audio else None


# =========================================================
# COMPATIBILITY
# =========================================================

def needs_video_reencode(video_codec):
    return video_codec not in VIDEO_SAFE_CODECS


def needs_audio_reencode(audio_codec):
    return audio_codec not in AUDIO_SAFE_CODECS


# =========================================================
# PROGRESS
# =========================================================

time_pattern = re.compile(
    r"time=(\d+):(\d+):(\d+).(\d+)"
)


def time_to_seconds(h, m, s):
    return (
        int(h) * 3600 +
        int(m) * 60 +
        int(s)
    )


# =========================================================
# CONVERTER
# =========================================================

def convert_video(input_file):

    try:

        # =================================================
        # ANALYSIS
        # =================================================

        info = analyze_file(input_file)

        video_codec = info["video"]

        best_audio = choose_best_audio(
            info["audios"]
        )

        audio_codec = (
            best_audio["codec"]
            if best_audio
            else "aac"
        )

        duration = info["duration"]

        output_file = str(
            Path(input_file).with_suffix(".mp4")
        )

        log("")
        log("=" * 60)
        log(f"📁 Arquivo: {os.path.basename(input_file)}")
        log(f"🎥 Vídeo: {video_codec}")
        log(f"🔊 Áudio: {audio_codec}")
        log(f"⏱ Duração: {round(duration / 60, 1)} min")

        # =================================================
        # VIDEO
        # =================================================

        video_reencode = needs_video_reencode(
            video_codec
        )

        if video_reencode:

            log("⚠ Vídeo incompatível")
            log("🎥 Reencodando para H264")

            video_args = [
                "-c:v", "libx264",
                "-preset", "slow",
                "-crf", "18"
            ]

            video_mode = "VIDEO REENCODE"

        else:

            log("✅ Vídeo compatível")
            log("⚡ Copiando vídeo")

            video_args = [
                "-c:v", "copy"
            ]

            video_mode = "VIDEO COPY"

        # =================================================
        # AUDIO
        # =================================================

        audio_reencode = needs_audio_reencode(
            audio_codec
        )

        if audio_reencode:

            log("⚠ Áudio incompatível")
            log("🔊 Convertendo áudio para AAC")

            audio_args = [
                "-c:a", "aac",
                "-profile:a", "aac_low",
                "-b:a", "192k",
                "-ac", "2",
                "-ar", "48000"
            ]

        else:

            log("✅ Áudio compatível")
            log("⚡ Copiando áudio")

            audio_args = [
                "-c:a", "copy"
            ]

        # =================================================
        # COMMAND
        # =================================================

        cmd = [
            FFMPEG,
            "-y",

            "-i", input_file,

            # VIDEO
            *video_args,

            # AUDIO
            *audio_args,

            # REMOVE SUBS
            "-sn",

            # FASTSTART
            "-movflags", "+faststart",

            # METADATA
            "-map_metadata", "0",
            "-map_chapters", "0",

            # STREAMS
            "-map", "0:v:0",
            "-map", "0:a:0?",

            output_file
        ]

        log("")
        log("🚀 Iniciando conversão...")
        log("")

        # =================================================
        # PROCESS
        # =================================================

        process = subprocess.Popen(
            cmd,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            universal_newlines=True
        )

        for line in process.stderr:

            match = time_pattern.search(line)

            if match and duration > 0:

                h, m, s, _ = match.groups()

                current = time_to_seconds(
                    h,
                    m,
                    s
                )

                progress = (
                    current / duration
                ) * 100

                progress_bar["value"] = progress

                status_var.set(
                    f"{video_mode} • {progress:.1f}%"
                )

                root.update_idletasks()

        process.wait()

        # =================================================
        # RESULT
        # =================================================

        if process.returncode == 0:

            progress_bar["value"] = 100

            log("")
            log("✅ Conversão finalizada!")
            log(f"💾 Salvo em:")
            log(output_file)

            status_var.set("Finalizado")

        else:

            log("")
            log("❌ FFmpeg retornou erro")

            status_var.set("Erro")

    except Exception as e:

        log("")
        log(f"❌ Erro: {str(e)}")

        status_var.set("Erro")


# =========================================================
# THREADS
# =========================================================

def start_conversion():

    files = filedialog.askopenfilenames(
        filetypes=[
            (
                "Vídeos",
                "*.mkv *.mp4 *.avi *.mov"
            )
        ]
    )

    if not files:
        return

    threading.Thread(
        target=process_queue,
        args=(files,),
        daemon=True
    ).start()


def process_queue(files):

    total = len(files)

    for index, file in enumerate(files):

        status_var.set(
            f"Processando {index + 1}/{total}"
        )

        convert_video(file)

    log("")
    log("🎉 TODOS OS ARQUIVOS FORAM PROCESSADOS")

    status_var.set("Fila concluída")


# =========================================================
# UI
# =========================================================

root = tk.Tk()

root.title("MP4 Converter PRO")
root.geometry("900x650")
root.configure(bg="#111111")

style = ttk.Style()
style.theme_use("clam")

# =========================================================
# TITLE
# =========================================================

title = tk.Label(
    root,
    text="MP4 Converter PRO",
    font=("Segoe UI", 24, "bold"),
    bg="#111111",
    fg="white"
)

title.pack(pady=20)

# =========================================================
# BUTTONS
# =========================================================

button_frame = tk.Frame(
    root,
    bg="#111111"
)

button_frame.pack()

convert_btn = tk.Button(
    button_frame,
    text="Selecionar Vídeos",
    font=("Segoe UI", 12, "bold"),
    bg="#1f6feb",
    fg="white",
    padx=20,
    pady=10,
    bd=0,
    cursor="hand2",
    command=start_conversion
)

convert_btn.pack(pady=10)

# =========================================================
# STATUS
# =========================================================

status_var = tk.StringVar()
status_var.set("Aguardando")

status_label = tk.Label(
    root,
    textvariable=status_var,
    font=("Segoe UI", 10),
    bg="#111111",
    fg="#aaaaaa"
)

status_label.pack()

# =========================================================
# PROGRESS
# =========================================================

progress_bar = ttk.Progressbar(
    root,
    orient="horizontal",
    length=700,
    mode="determinate"
)

progress_bar.pack(pady=15)

# =========================================================
# OUTPUT
# =========================================================

output = tk.Text(
    root,
    bg="#0d1117",
    fg="#e6edf3",
    insertbackground="white",
    font=("Consolas", 10),
    relief="flat"
)

output.pack(
    fill="both",
    expand=True,
    padx=20,
    pady=20
)

# =========================================================
# INIT
# =========================================================

if not check_ffmpeg():

    messagebox.showerror(
        "Erro",
        "FFmpeg não encontrado no sistema."
    )

    root.destroy()

else:

    log("✅ FFmpeg detectado")
    log("🚀 Sistema pronto")

update_logs()

root.mainloop()