# MP4 Converter PRO

Conversor profissional de vídeos MKV para MP4 com:

- Interface gráfica moderna
- Detecção automática de codecs
- Conversão inteligente
- Preservação máxima de qualidade
- Compatibilidade com Windows, TVs, navegadores e streaming
- Preservação de metadados
- FastStart para streaming web
- Processamento em fila
- Barra de progresso em tempo real

---

# ✨ Recursos

## 🎥 Conversão Inteligente

O sistema analisa automaticamente:

- codec de vídeo
- codec de áudio
- canais de áudio
- legendas
- duração

E decide automaticamente:

| Situação | Ação |
|---|---|
| Vídeo compatível | Copia sem perda |
| Áudio incompatível | Converte para AAC |
| Vídeo incompatível | Reencoda para H264 |

---

# 🚀 Compatibilidade

O MP4 final funciona em:

- Windows Media Player
- VLC
- TVs Samsung/LG
- Android
- iPhone
- Chrome
- Firefox
- Streaming web
- Plex
- Jellyfin
- Emby

---

# 🧠 Codecs suportados

## Vídeo

- H264
- HEVC / H265
- AV1
- MPEG4
- VP9
- outros

## Áudio

- AAC
- EAC3
- AC3
- DTS
- MP3
- Opus
- outros

---

# ⚡ Estratégia de conversão

## Vídeo compatível

O sistema faz:

```bash
-copy
```

Sem perda de qualidade.

---

## Vídeo incompatível

O sistema usa:

```bash
libx264
crf 18
preset slow
```

Qualidade visual extremamente alta.

---

## Áudio incompatível

Converte automaticamente para:

```bash
AAC LC
192 kbps
48 kHz
Stereo
```

Máxima compatibilidade.

---

# 📦 Requisitos

## Python

Python 3.10+

Download:

https://www.python.org/downloads/

---

## FFmpeg

Instale via Winget:

```powershell
winget install "FFmpeg (Essentials Build)"
```

Depois reinicie o terminal.

---

# ▶️ Como executar

## 1. Clone ou baixe o projeto

```bash
git clone https://github.com/seuusuario/mp4-converter-pro.git
```

---

## 2. Entre na pasta

```bash
cd mp4-converter-pro
```

---

## 3. Execute

```bash
python main.py
```

---

# 🖥 Interface

A aplicação possui:

- seleção múltipla de arquivos
- logs em tempo real
- barra de progresso
- processamento em fila
- status automático

---

# 📁 Estrutura

```bash
mp4-converter-pro/
│
├── main.py
├── README.md
└── assets/
```

---

# 🔥 Pipeline profissional

## Entrada

```text
MKV
├── H264
├── EAC3
└── SRT
```

## Saída

```text
MP4
├── H264 (copy)
├── AAC
└── FastStart
```

---

# 📈 Performance

## Stream Copy

Extremamente rápido:

- sem perda
- baixa CPU
- arquivos menores

---

## Reencode

Qualidade visual profissional:

- CRF 18
- preset slow
- alta fidelidade

---

# ⚠️ Observações

## Legendas

Atualmente o sistema remove legendas internas para evitar:

- incompatibilidade
- corrupção do MP4
- problemas no Windows

Suporte avançado pode ser adicionado depois.

---

# 🛠 Tecnologias

- Python
- Tkinter
- FFmpeg
- FFprobe

---

# 📄 Licença

MIT License

---

# 👨‍💻 Autor

Desenvolvido com foco em:

- qualidade
- compatibilidade
- performance
- streaming profissional