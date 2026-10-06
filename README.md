# FreesIA (alpha)

A personal AI desktop assistant for Windows that runs **locally**: chat with a character ("A2"), open apps and files, generate images, and read old chat exports, all without sending your data to a cloud service.

> **Alpha.** Things work on the author's PC but are not widely tested. Expect rough edges (see below).

## Features
- **Local chat** through [Ollama](https://ollama.com), with a modern dark/light UI: avatars, code blocks with copy, typing indicator, dated and pinned history, search, and a `Ctrl+K` command palette.
- **Persona**: write your own personality text (or drag a `.txt` in), or pick a preset from Soft to Cold.
- **Check-ins** (optional, off by default): A2 occasionally messages first, with quiet hours and a fullscreen-app guard.
- **Voice**: Windows voice, or an offline neural "A2 voice" ([Piper](https://github.com/rhasspy/piper)) downloaded from inside the app.
- **Image generation** through [FastSD CPU](https://github.com/rupeshs/fastsdcpu), with a gallery, starred images and speed options (TAESD / token merging).
- **Chat Reader**: import a Character.AI export and read it like a chat, with resume, search, timeline and bookmarks.
- **System helpers**: open apps and folders, file search, shortcuts/macros, PIN lock, permissions and a diagnostics page.

## Requirements
- Windows 10/11, Python 3.10+
- [Ollama](https://ollama.com) with the models you want. Defaults: `phi4-mini` (complex questions) and `llama3.2:3b` (fast replies). Models are changeable in **Settings -> Models**.
- Optional: [FastSD CPU](https://github.com/rupeshs/fastsdcpu) in a folder named `fastsdcpu` **next to** the FreesIA folder, for image generation.

## Setup
```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
ollama pull phi4-mini
ollama pull llama3.2:3b
python FreesIA_GUI.py
```
Or double-click `Launch FreesIA.vbs` (no console window).

Your chats, persona text and settings stay on your PC (`ChatHistory/`, `Personality.txt` and `%USERPROFILE%\.freesia`). Copy `Personality.example.txt` to `Personality.txt` to start with a sample character.

## Known rough edges
- Windows only.
- Fullscreen detection (for check-ins) and the offline A2 voice have had limited testing.
- Image-speed options depend on the image model you use.
- Image generation needs an SDXL `.safetensors` checkpoint (ideally a Lightning/Turbo one). Pick it in Settings → General → Image model, or drop it into `fastsdcpu/models/custom`; otherwise it falls back to `stabilityai/sdxl-turbo`.
- No installer yet; setup is manual.

## Third-party software
FreesIA uses Ollama, FastSD CPU, PyQt6 (GPL/commercial), Piper voices and several Python libraries. Each has its own license; check them before redistributing.

## License
MIT, see [LICENSE](LICENSE).
