
import subprocess
import json
import os
import re
from pathlib import Path
from tkinter import Tk, filedialog

def selecionar_video():
    root = Tk()
    root.withdraw()
    caminho = filedialog.askopenfilename(
        title="Selecione o vídeo",
        filetypes=[("Vídeos MP4", "*.mp4"), ("Todos os arquivos", "*.*")]
    )
    root.destroy()
    return caminho

def obter_duracao(arquivo):
    comando = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json", arquivo
    ]
    resultado = subprocess.run(
        comando, capture_output=True, text=True, check=True
    )
    return float(json.loads(resultado.stdout)["format"]["duration"])

def comprimir_video(entrada, resolucao="1080p", crf=26):
    alturas = {"1080p": 1080, "1440p": 1440}
    altura = alturas[resolucao]

    origem = Path(entrada)
    saida = origem.with_name(
        f"{origem.stem}_{resolucao}_h265.mp4"
    )

    duracao = obter_duracao(entrada)
    tamanho_original = os.path.getsize(entrada)

    comando = [
        "ffmpeg", "-y",
        "-i", str(origem),
        "-map", "0:v:0",
        "-map", "0:a?",
        "-vf", f"scale=-2:min(ih\\,{altura})",
        "-c:v", "libx265",
        "-preset", "medium",
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "160k",
        "-movflags", "+faststart",
        "-progress", "pipe:1",
        "-nostats",
        str(saida)
    ]

    print(f"\nConvertendo para {resolucao}...")
    print(f"Qualidade CRF: {crf}")
    print(f"Destino: {saida}\n")

    processo = subprocess.Popen(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    for linha in processo.stdout:
        if linha.startswith("out_time_us="):
            try:
                tempo = int(linha.split("=")[1]) / 1_000_000
                progresso = min(100, tempo / duracao * 100)
                print(f"\rProgresso: {progresso:.1f}%", end="", flush=True)
            except (ValueError, ZeroDivisionError):
                pass

    codigo = processo.wait()

    if codigo != 0:
        print("\nErro na conversão.")
        return

    tamanho_final = os.path.getsize(saida)
    reducao = (1 - tamanho_final / tamanho_original) * 100

    print("\n\nConversão concluída!")
    print(f"Original: {tamanho_original / 1024**3:.2f} GB")
    print(f"Final: {tamanho_final / 1024**3:.2f} GB")
    print(f"Redução: {reducao:.1f}%")
    print(f"Arquivo: {saida}")

if __name__ == "__main__":
    video = selecionar_video()

    if video:
        print("1 - 1080p (Full HD)")
        print("2 - 1440p (Quad HD)")

        opcao = input("Escolha a resolução [1]: ").strip() or "1"
        resolucao = "1440p" if opcao == "2" else "1080p"

        print("\nCRF: 22 = melhor qualidade; 26 = equilibrado; 30 = menor arquivo")
        valor = input("Escolha o CRF [26]: ").strip() or "26"

        comprimir_video(video, resolucao, int(valor))
