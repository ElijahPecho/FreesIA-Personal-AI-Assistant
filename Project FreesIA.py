# FreesIA - Functional & Responsive Entity for Enhanced System Intelligence Administration
# A comprehensive voice and text-based assistant for Windows
# Features: File management, system control, productivity tools, and more

# ================= IMPORTS ====================
import os
import subprocess
import sys

# Force UTF-8 output so emoji/box-drawing characters (used throughout the UI)
# never crash print()/input() on consoles using a legacy codepage (e.g. cp1252)
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from typing import List, Dict
from pathlib import Path
import webbrowser
from difflib import get_close_matches
import winreg
import re
import psutil
import datetime
import time
import threading
import json
from PIL import ImageGrab
import tkinter as tk
from tkinter import messagebox

# Import Relationship Manager (stored separately to preserve data across updates)
sys.path.insert(0, str(Path(__file__).parent / "Relation"))
from relationship_manager import RelationshipManager

# ==================== PACKAGE INSTALLATION ====================
# Automatically install required packages if not present

def install_package(package):
    """Install a Python package using pip"""
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Try importing required packages, install if missing
try:
    import speech_recognition as sr
except ImportError:
    print("Installing speech_recognition...")
    install_package("SpeechRecognition")
    import speech_recognition as sr

try:
    import pyaudio
except ImportError:
    print("Installing PyAudio...")
    try:
        install_package("PyAudio")
        import pyaudio
    except:
        print("Note: PyAudio installation failed. Voice features may not work.")
        print("You can install it manually with: pip install PyAudio")

try:
    import vosk
except ImportError:
    print("Installing vosk for offline voice recognition...")
    install_package("vosk")
    import vosk

try:
    import psutil
except ImportError:
    print("Installing psutil...")
    install_package("psutil")
    import psutil

try:
    from PIL import ImageGrab
except ImportError:
    print("Installing Pillow...")
    install_package("Pillow")
    from PIL import ImageGrab

try:
    import requests
except ImportError:
    print("Installing requests...")
    install_package("requests")
    import requests

try:
    import pyttsx3
except ImportError:
    print("Installing pyttsx3...")
    install_package("pyttsx3")
    import pyttsx3

try:
    from PIL import Image
except ImportError:
    # Pillow already imported above, just need Image module
    from PIL import Image

try:
    import send2trash
except ImportError:
    print("Installing send2trash...")
    install_package("send2trash")
    import send2trash

try:
    import ollama
except ImportError:
    print("Installing ollama...")
    install_package("ollama")
    import ollama

try:
    import win32gui
    import win32process
    import win32com.client
except ImportError:
    print("Installing pywin32 for context awareness...")
    install_package("pywin32")
    import win32gui
    import win32process
    import win32com.client

try:
    from pynput import keyboard as pynput_keyboard
except ImportError:
    print("Installing pynput for push-to-talk...")
    install_package("pynput")
    from pynput import keyboard as pynput_keyboard

# Windows virtual-key codes for common push-to-talk bindings.
# Single letters/digits are matched by character instead (see set_ptt_key), since
# vk codes for those vary less predictably across keyboard layouts.
PTT_KEY_NAME_TO_VK = {
    "numpad 0": 96, "numpad 1": 97, "numpad 2": 98, "numpad 3": 99, "numpad 4": 100,
    "numpad 5": 101, "numpad 6": 102, "numpad 7": 103, "numpad 8": 104, "numpad 9": 105,
    "numpad multiply": 106, "numpad add": 107, "numpad subtract": 109,
    "numpad decimal": 110, "numpad divide": 111,
    "f13": 124, "f14": 125, "f15": 126, "f16": 127, "f17": 128, "f18": 129,
    "f19": 130, "f20": 131, "f21": 132, "f22": 133, "f23": 134, "f24": 135,
    "right ctrl": 163, "right control": 163, "right alt": 165, "right shift": 161,
    "scroll lock": 145, "pause": 19, "caps lock": 20, "capslock": 20,
    "insert": 45, "home": 36, "end": 35, "page up": 33, "page down": 34,
}

# ==================== MAIN ASSISTANT CLASS ====================

class LocalVoice:
    """
    Local voice: Piper neural text-to-speech, fully offline once the engine
    and a voice file are on disk. Falls back to the Windows voice (pyttsx3)
    whenever the engine, the voice file or playback isn't available.
    Settings live in ~/.freesia/voice.json; voice files in ~/.freesia/voices/.
    """
    HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
    VOICES = [
        {"key": "en_US-lessac-medium", "name": "Lessac", "desc": "US English, female, clear and steady", "mb": 63},
        {"key": "en_US-amy-medium", "name": "Amy", "desc": "US English, female, relaxed", "mb": 63},
        {"key": "en_US-kathleen-low", "name": "Kathleen", "desc": "US English, female, smaller and lower quality", "mb": 63},
        {"key": "en_GB-alba-medium", "name": "Alba", "desc": "British English, female", "mb": 63},
    ]
    DEFAULTS = {"read_aloud": False, "engine": "system", "voice": "en_US-lessac-medium", "speed": 1.0, "volume": 0.9}
    SAMPLE = "Hey. It's me. This is how I sound."

    # Speech is synthesized in a separate Python process, never inside the app: the neural engine
    # (onnxruntime) is native code, and if it ever crashed in-process it would take FreesIA down with it.
    _WORKER = (
        "import sys, json, wave, os\n"
        "a = json.loads(sys.argv[1])\n"
        "from piper import PiperVoice, SynthesisConfig\n"
        "v = PiperVoice.load(a['model'], config_path=a['config'])\n"
        "c = SynthesisConfig(length_scale=a['length_scale'], volume=a['volume'])\n"
        "for i, t in enumerate(a['chunks']):\n"
        "    p = os.path.join(a['outdir'], '%03d.wav' % i)\n"
        "    with wave.open(p, 'wb') as w:\n"
        "        v.synthesize_wav(t, w, syn_config=c)\n"
        "    sys.stdout.write(p + '\\n'); sys.stdout.flush()\n"
    )

    def __init__(self, config_dir, fallback=None):
        import threading
        self.config_dir = Path(config_dir)
        self.voice_dir = self.config_dir / "voices"
        self.cfg_path = self.config_dir / "voice.json"
        self.fallback = fallback          # callable(text) -> None, speaks with the Windows voice
        self.last_error = ""
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._proc = None
        self.cfg = self.load_cfg()

    # ---- settings
    def load_cfg(self) -> dict:
        cfg = dict(self.DEFAULTS)
        try:
            with open(self.cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                if isinstance(data.get("read_aloud"), bool):
                    cfg["read_aloud"] = data["read_aloud"]
                if data.get("engine") in ("system", "local"):
                    cfg["engine"] = data["engine"]
                if data.get("voice") in [v["key"] for v in self.VOICES]:
                    cfg["voice"] = data["voice"]
                for k, lo, hi in (("speed", 0.6, 1.5), ("volume", 0.0, 1.0)):
                    v = data.get(k)
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        cfg[k] = min(hi, max(lo, float(v)))
        except Exception:
            pass
        return cfg

    def set_cfg(self, **kw):
        self.cfg.update(kw)
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.cfg_path, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, indent=2)
        except Exception:
            pass

    # ---- files
    @staticmethod
    def _rel(key: str) -> str:
        locale, name, quality = key.split("-", 2)
        return f"{locale.split('_')[0]}/{locale}/{name}/{quality}/{key}"

    def engine_installed(self) -> bool:
        import importlib.util
        try:
            return importlib.util.find_spec("piper") is not None
        except Exception:
            return False

    def installed(self, key=None) -> bool:
        key = key or self.cfg["voice"]
        return (self.voice_dir / f"{key}.onnx").exists() and (self.voice_dir / f"{key}.onnx.json").exists()

    def disk_bytes(self) -> int:
        try:
            return sum(p.stat().st_size for p in self.voice_dir.glob("*") if p.is_file())
        except Exception:
            return 0

    def is_ready(self) -> bool:
        return self.engine_installed() and self.installed()

    def download(self, key, progress=None):
        """Download one voice (model + config). progress(done_bytes, total_bytes). Raises on failure."""
        import urllib.request
        self.voice_dir.mkdir(parents=True, exist_ok=True)
        for suffix in (".onnx.json", ".onnx"):
            dest = self.voice_dir / f"{key}{suffix}"
            if dest.exists():
                continue
            part = dest.with_name(dest.name + ".part")
            url = f"{self.HF_BASE}/{self._rel(key)}{suffix}"
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "FreesIA"}), timeout=30) as r, \
                        open(part, "wb") as out:
                    total = int(r.headers.get("Content-Length") or 0)
                    done = 0
                    while True:
                        chunk = r.read(256 * 1024)
                        if not chunk:
                            break
                        out.write(chunk)
                        done += len(chunk)
                        if progress and suffix == ".onnx":
                            progress(done, total)
                os.replace(part, dest)
            except Exception:
                try:
                    part.unlink()
                except Exception:
                    pass
                raise

    def remove_all(self):
        self.stop()
        try:
            for p in self.voice_dir.glob("*"):
                if p.is_file():
                    p.unlink()
        except Exception:
            pass

    # ---- speech
    @staticmethod
    def clean_for_speech(text: str, limit: int = 1800) -> str:
        t = re.sub(r"```.*?```", " ", text or "", flags=re.S)
        t = re.sub(r"`([^`]*)`", r"\1", t)
        t = re.sub(r"https?://\S+", "link", t)
        t = re.sub(r"[*_#>~|]+", " ", t)
        t = re.sub(r"[^\x00-\x7F‘’“”…]", " ", t)  # emoji and symbols
        t = re.sub(r"\s+", " ", t).strip()
        return t[:limit]

    @staticmethod
    def _chunks(text: str, size: int = 220):
        out, cur = [], ""
        for s in re.split(r"(?<=[.!?…])\s+", text):
            if cur and len(cur) + len(s) + 1 > size:
                out.append(cur)
                cur = s
            else:
                cur = (cur + " " + s).strip()
        if cur:
            out.append(cur)
        return out

    def _python(self) -> str:
        exe = sys.executable or "python"
        if exe.lower().endswith("pythonw.exe"):  # pythonw has no stdout to read from
            alt = exe[:-len("pythonw.exe")] + "python.exe"
            if os.path.exists(alt):
                return alt
        return exe

    def _start_worker(self, chunks, outdir):
        import subprocess
        key = self.cfg["voice"]
        args = {"model": str(self.voice_dir / f"{key}.onnx"), "config": str(self.voice_dir / f"{key}.onnx.json"),
                "length_scale": 1.0 / max(0.3, float(self.cfg["speed"])), "volume": float(self.cfg["volume"]),
                "chunks": chunks, "outdir": outdir}
        self._errfile = open(os.path.join(outdir, "err.txt"), "wb")
        return subprocess.Popen([self._python(), "-c", self._WORKER, json.dumps(args)], stdout=subprocess.PIPE,
                                stderr=self._errfile, stdin=subprocess.DEVNULL,
                                creationflags=0x08000000 if sys.platform == "win32" else 0)

    def synth_to_wav(self, text: str, path: str):
        """Synthesize `text` to a wav file (in the worker process). Raises if the engine fails."""
        import tempfile, shutil
        outdir = tempfile.mkdtemp(prefix="localvoice_")
        try:
            proc = self._start_worker([text], outdir)
            out, _ = proc.communicate(timeout=120)
            self._errfile.close()
            if proc.returncode != 0 or not out.strip():
                err = ""
                try:
                    err = open(os.path.join(outdir, "err.txt"), "r", errors="replace").read().strip().splitlines()[-1]
                except Exception:
                    pass
                raise RuntimeError(err or f"voice engine exited with code {proc.returncode}")
            shutil.copyfile(out.decode().strip().splitlines()[0], path)
        finally:
            shutil.rmtree(outdir, ignore_errors=True)

    def _play(self, path: str):
        if sys.platform != "win32":
            return
        import winsound
        winsound.PlaySound(str(path), winsound.SND_FILENAME)

    def stop(self):
        self._stop.set()
        p = self._proc
        if p is not None and p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass
        if sys.platform == "win32":
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass

    def speak(self, text: str) -> bool:
        """Speak with the local voice (blocking). Returns False if it couldn't, so the caller can fall back."""
        text = self.clean_for_speech(text)
        if not text:
            return True
        if not self.is_ready():
            return False
        import tempfile, shutil
        with self._lock:
            self._stop.clear()
            outdir = tempfile.mkdtemp(prefix="localvoice_")
            played = 0
            proc = None
            try:
                proc = self._proc = self._start_worker(self._chunks(text), outdir)
                for line in proc.stdout:
                    path = line.decode(errors="replace").strip()
                    if not path or self._stop.is_set():
                        continue
                    self._play(path)
                    played += 1
                    try:
                        os.remove(path)
                    except Exception:
                        pass
                proc.wait(timeout=30)
                if self._stop.is_set():
                    return True
                if proc.returncode != 0 and not played:
                    err = ""
                    try:
                        self._errfile.flush()
                        err = open(os.path.join(outdir, "err.txt"), "r", errors="replace").read().strip().splitlines()[-1]
                    except Exception:
                        pass
                    self.last_error = err or f"voice engine exited with code {proc.returncode}"
                    return False
                self.last_error = ""
                return True
            except Exception as e:
                self.last_error = str(e)
                return False
            finally:
                try:
                    if proc is not None and proc.poll() is None:
                        proc.kill()
                    self._errfile.close()
                except Exception:
                    pass
                self._proc = None
                shutil.rmtree(outdir, ignore_errors=True)

    def speak_with_fallback(self, text: str):
        """local voice if selected and ready, otherwise the Windows voice."""
        if self.cfg["engine"] == "local" and self.speak(text):
            return
        if self.fallback:
            self.fallback(self.clean_for_speech(text))

    def preview(self, key=None, text=None):
        """Blocking sample of a specific voice (used by the Settings Preview button)."""
        old = self.cfg["voice"]
        if key:
            self.cfg["voice"] = key  # temporary: only set_cfg() persists a choice
        try:
            return self.speak(text or self.SAMPLE)
        finally:
            self.cfg["voice"] = old


class FreesIA:
    """
    FreesIA - Personal AI System Assistant
    Main class handling all assistant functionality including:
    - Voice and text command processing
    - System control (volume, brightness, power)
    - File management
    - Web browsing and weather
    - Productivity tools (notes, todos, timers)
    - Application launching
    """
    
    def __init__(self):
        """Initialize the FreesIA assistant with all necessary configurations"""
        self.name = "FreesIA"
        self.assistant_name = "FreesIA"  # what the assistant calls itself; user-editable in Settings -> Persona
        
        # Initialize conversation and data storage
        self.conversation_history = []
        self.wake_words = ["freesia", "hey freesia", "hi freesia", "hello freesia", "fresia", "freesia assistant"]
        self.clipboard_history = []
        self.todo_list = []
        self.timers = []
        self.notes = []
        self.context_memory = []
        
        # Ollama AI Configuration
        self.ollama_enabled = False
        self.ollama_status = "unknown"  # "ready" / "offline" / "model_missing"
        self.ollama_error = ""
        self.ollama_installed_models = []
        self._last_ollama_retry = 0.0  # throttle for _ensure_ollama_ready()
        self.ollama_model = "phi4-mini:latest"  # Complex questions - benchmarked faster and more complete than llama3.1:8b on this hardware
        self.ollama_fast_model = "llama3.2:3b"  # Simple/medium questions - genuinely fast (previous "mistral" was same weight class as the complex model)
        self.personality_mode_enabled = True  # on by default - the custom persona; off = plain neutral assistant
        self.personality_prompt = ""
        self.ai_conversation_history = []  # Separate history for AI conversations
        self.ai_conversation_summary = ""  # rolling summary of folded-in older messages, see _condense_conversation_history
        
        # Microphone listening state
        self.listening_active = False
        self.listening_thread = None
        self.wake_word_triggered = False  # set by process_command(), read by main()'s loop

        # Auto-pause mic while a call app is running (Discord/Teams/Zoom/Skype)
        self.call_apps_watch = {
            "discord.exe": "Discord",
            "teams.exe": "Teams",
            "ms-teams.exe": "Teams",
            "zoom.exe": "Zoom",
            "skype.exe": "Skype",
        }
        self.mic_paused_for_call = False  # True only when WE auto-paused it (not a manual "mic off")
        self._call_app_prev_active = False
        self._call_monitor_running = False

        # Push-to-talk (hold a key to have FreesIA listen, regardless of what app has focus)
        self.ptt_key_name = "numpad 0"
        self.ptt_key_vk = 96      # used for special keys (numpad, function keys, etc.)
        self.ptt_key_char = None  # used instead of vk for plain letter/digit keys
        self.ptt_listener = None
        self.ptt_recording = False
        self._ptt_frames = []
        self._ptt_stream = None
        self._ptt_pyaudio = None

        # Text-to-Speech (TTS) state
        self.tts_enabled = True
        self.tts_engine = None
        
        # Setup configuration directory for persistent storage
        self.config_dir = Path.home() / ".freesia"
        self.config_dir.mkdir(exist_ok=True)
        self.app_cache_file = self.config_dir / "app_cache.json"
        self.app_cache_max_age = 7  # days
        self.ptt_settings_file = self.config_dir / "ptt_settings.json"
        self.load_ptt_settings()

        # Image generation (FastSD CPU, run as a local API server - see README)
        self.image_gen_settings_file = self.config_dir / "image_gen_settings.json"
        self.image_safety_checker = True  # on by default (FastSD CPU safety checker)
        self.image_model_path = ""  # optional path to an SDXL .safetensors checkpoint; empty = auto-detect
        self.fastsdcpu_api_url = "http://127.0.0.1:8000"
        self.fastsdcpu_dir = Path(__file__).parent.parent / "fastsdcpu"
        self._fastsdcpu_process = None  # Popen handle if we auto-launched it this session
        # Optional speed-ups inside FastSD CPU (both off until the user turns them on in Settings > Models)
        self.use_tiny_autoencoder = False  # TAESD: faster image decode, slightly softer fine detail
        self.tome_enabled = False          # ToMe token merging: less repeated work in the model
        self.tome_strength = 0.4           # 0.1 - 0.7; higher = faster but less detailed
        self.last_generated_image_path = None  # for "edit that image"-style follow-ups
        self.last_image_gen_time = None  # so the natural-language image classifier only
        # runs for a short window after generation, not on every message forever
        self.load_image_gen_settings()

        # Personality source: the user's own Personality.txt ("custom") or one of five built-in presets
        self.persona_settings_file = self.config_dir / "persona.json"
        self.persona_source = "custom"
        self.persona_preset = 2  # index into PERSONA_PRESETS; 2 = Balanced
        self._persona_original_hash = None
        self._default_condensed = ""
        self.load_persona_settings()

        self.chat_settings_file = self.config_dir / "chat_settings.json"
        self.memory_bank_file = self.config_dir / "memory_bank.json"
        self.memory_bank = self.load_memory_bank()
        self.load_chat_settings()

        # Pinned messages (shared between live chat and the Chat Reader)
        self.pinned_messages_file = self.config_dir / "pinned_messages.json"
        self.pinned_messages = self.load_pinned_messages()

        # Chat Reader - imported chat archives (e.g. Character.AI exports)
        self.chat_reader_dir = self.config_dir / "chat_reader"
        self.chat_reader_dir.mkdir(exist_ok=True)

        # Initialize TTS engine (silent)
        try:
            self.tts_engine = pyttsx3.init()
            # Configure voice settings
            voices = self.tts_engine.getProperty('voices')
            # Try to find a female voice (optional)
            for voice in voices:
                if "female" in voice.name.lower() or "zira" in voice.name.lower():
                    self.tts_engine.setProperty('voice', voice.id)
                    break
            # Set speech rate (default is around 200)
            self.tts_engine.setProperty('rate', 180)
            # Set volume (0.0 to 1.0)
            self.tts_engine.setProperty('volume', 0.9)
            
            # Warmup TTS engine for faster first speech
            self.tts_engine.say("")
            self.tts_engine.runAndWait()
        except Exception as e:
            self.tts_engine = None

        # local voice (local Piper TTS) + read-replies-aloud settings
        self.local_voice = LocalVoice(self.config_dir, fallback=self._speak_system)
        
        # ==================== SECURITY & PRIVACY ====================
        # Initialize permissions system
        self.permissions = {
            "file_access": False,
            "system_settings": False,
            "power_control": False,
        }
        self.load_permissions()
        
        # Initialize security settings for GUI
        self.security_settings = {
            "pin_enabled": False,
            "pin_hash": None,
        }
        self.load_security_settings()
        
        # Initialize user profile for personalization
        self.user_profile = {
            "nickname": "",
            "occupation": "",
            "visual_description": "",
            "likes": "",
            "dislikes": "",
            "other_info": ""
        }
        self.load_user_profile()
        
        # Initialize custom command shortcuts
        self.custom_shortcuts = {}
        self.load_custom_shortcuts()
        
        # Relationship progression system (stored in Relation folder)
        relation_dir = Path(__file__).parent / "Relation"
        self.relationship_manager = RelationshipManager(relation_dir)
        
        self.load_data()
        
        # Initialize Ollama AI
        self.initialize_ollama()
        
        # Initialize speech recognition (Vosk for offline - lazy loaded)
        self.vosk_model = None
        self.vosk_recognizer = None
        self.vosk_loading_attempted = False
        try:
            self.recognizer = sr.Recognizer()
            # Test if microphone is accessible
            with sr.Microphone() as source:
                pass
            self.voice_available = True
        except Exception as e:
            self.voice_available = False
        
        # Define common file search locations
        self.search_paths = [
            Path.home() / "Desktop",
            Path.home() / "Documents",
            Path.home() / "Downloads",
            Path.home(),
        ]
        
        # Load cached applications or scan if cache is old
        self.installed_apps = self.load_app_cache()
        if not self.installed_apps:
            print(f"{self.name}: Loading applications (first time - this may take a moment)...")
            # Quick load: get registry apps first (much faster)
            try:
                self.installed_apps = self.scan_registry_apps()
            except:
                self.installed_apps = {}
            
            # Then scan Program Files in background thread
            def full_scan():
                try:
                    additional_apps = self.scan_installed_apps()
                    self.installed_apps.update(additional_apps)
                    self.save_app_cache()
                except:
                    pass
            
            # Start background scan
            scan_thread = threading.Thread(target=full_scan, daemon=True)
            scan_thread.start()
        else:
            print(f"{self.name}: Loaded {len(self.installed_apps)} applications from cache")

        # Custom folders discovered by scanning the Desktop (subfolders and
        # shortcuts pointing at folders) - separate from the fixed system
        # folders (Downloads/Documents/etc.) in SYSTEM_FOLDERS, which are
        # always available without needing a scan.
        self.folder_cache_file = self.config_dir / "folder_cache.json"
        self.custom_folders = self.load_folder_cache()

        # Define keywords for fuzzy matching and command recognition
        self.command_keywords = [
            "find", "search", "open", "readfile", "generateimage", "editlast", "editfile", "volume", "settings", "help", "voice", "quit", "exit",
            "brightness", "dim", "brighten", "listen", "wifi", "bluetooth", "battery", "system",
            "screenshot", "lock", "sleep", "shutdown", "restart", "weather", "time", "date",
            "timer", "calculator", "note", "todo", "theme", "clipboard", "recent", "delete",
            "create", "move", "copy", "website", "email", "music", "play", "pause", "stop"
        ]
        self.app_keywords = list(self.installed_apps.keys())  # All detected app names
        self.volume_keywords = ["up", "down", "increase", "decrease", "mute", "unmute"]
        self.brightness_keywords = ["up", "down", "increase", "decrease", "dim", "brighten", "brighter", "darker"]
        
        # Voice recognition timeouts (configurable)
        self.command_timeout = 30  # How long to wait for you to start speaking (30 seconds)
        self.command_phrase_limit = 35  # How long your command can be (35 seconds)
        
        # Show initialization summary
        status_parts = []
        if self.voice_available:
            status_parts.append("voice recognition")
        if self.tts_engine:
            status_parts.append("text-to-speech")
        if self.ollama_enabled:
            status_parts.append("AI conversation")
        
        features_status = " and ".join(status_parts) if status_parts else "text commands"
        print(f"{self.name}: Ready! Found {len(self.installed_apps)} applications. Active features: {features_status}.")
        
        # Show note if voice is not available
        if not self.voice_available:
            print(f"\nNote: Voice recognition not available. Using text commands only.")
            print(f"To enable voice: Install PyAudio and check microphone permissions.\n")

        # Start the call-app monitor so mic auto-pauses if Discord/Teams/Zoom/Skype opens
        if self.voice_available:
            self.start_call_app_monitor()

        # Start push-to-talk (works regardless of continuous listening mode, and
        # regardless of which app has focus - e.g. Discord/Teams/Zoom)
        if self.voice_available:
            self.start_push_to_talk_listener()
            print(f"{self.name}: Push-to-talk ready - hold [{self.ptt_key_name}] to talk to me.")

        # ==================== SECURITY & PRIVACY ====================
    
    def load_permissions(self):
        """Load saved permissions from file"""
        try:
            permissions_file = self.config_dir / "permissions.json"
            if permissions_file.exists():
                with open(permissions_file, 'r') as f:
                    self.permissions = json.load(f)
        except:
            pass  # Use default permissions if load fails
    
    # ==================== PERMISSIONS MANAGEMENT ====================
    
    def save_permissions(self):
        """Save permissions to file"""
        try:
            with open(self.config_dir / "permissions.json", 'w') as f:
                json.dump(self.permissions, f, indent=2)
        except:
            pass
    
    def load_security_settings(self):
        """Load saved security settings from file"""
        try:
            security_file = self.config_dir / "security_settings.json"
            if security_file.exists():
                with open(security_file, 'r') as f:
                    self.security_settings = json.load(f)
        except:
            pass  # Use default security settings if load fails
    
    def save_security_settings(self):
        """Save security settings to file"""
        try:
            with open(self.config_dir / "security_settings.json", 'w') as f:
                json.dump(self.security_settings, f, indent=2)
        except:
            pass
    
    def toggle_permission(self, permission_type: str, enabled: bool):
        """Toggle a permission on or off"""
        if permission_type in self.permissions:
            self.permissions[permission_type] = enabled
            self.save_permissions()
    
    def load_user_profile(self):
        """Load saved user profile from file"""
        try:
            profile_file = self.config_dir / "user_profile.json"
            if profile_file.exists():
                with open(profile_file, 'r') as f:
                    self.user_profile = json.load(f)
        except:
            pass  # Use default user profile if load fails
    
    def save_user_profile(self):
        """Save user profile to file"""
        try:
            with open(self.config_dir / "user_profile.json", 'w') as f:
                json.dump(self.user_profile, f, indent=2)
        except:
            pass
    
    # ==================== CUSTOM SHORTCUTS ====================
    
    def load_custom_shortcuts(self):
        """Load saved custom shortcuts from file"""
        try:
            shortcuts_file = self.config_dir / "custom_shortcuts.json"
            if shortcuts_file.exists():
                with open(shortcuts_file, 'r') as f:
                    self.custom_shortcuts = json.load(f)
        except:
            pass  # Use default empty dict if load fails
    
    def save_custom_shortcuts(self):
        """Save custom shortcuts to file"""
        try:
            with open(self.config_dir / "custom_shortcuts.json", 'w') as f:
                json.dump(self.custom_shortcuts, f, indent=2)
        except:
            pass
    
    def add_shortcut(self, name: str, actions: list):
        """
        Add a custom shortcut
        Args:
            name: Shortcut name (e.g., "work", "gaming")
            actions: List of commands/actions to execute (e.g., ["open chrome", "open spotify"])
        """
        self.custom_shortcuts[name.lower()] = actions
        self.save_custom_shortcuts()
        print(f"{self.name}: Shortcut '{name}' created with {len(actions)} action(s).")
        return f"Shortcut '{name}' created successfully!"
    
    def remove_shortcut(self, name: str):
        """Remove a custom shortcut"""
        name_lower = name.lower()
        if name_lower in self.custom_shortcuts:
            del self.custom_shortcuts[name_lower]
            self.save_custom_shortcuts()
            print(f"{self.name}: Shortcut '{name}' removed.")
            return f"Shortcut '{name}' removed successfully!"
        else:
            return f"Shortcut '{name}' not found."
    
    def list_shortcuts(self):
        """List all custom shortcuts"""
        if not self.custom_shortcuts:
            return "No custom shortcuts defined yet."
        
        result = "Custom Shortcuts:\n"
        for name, actions in self.custom_shortcuts.items():
            result += f"\n• {name}: {len(actions)} action(s)\n"
            for i, action in enumerate(actions, 1):
                result += f"  {i}. {action}\n"
        return result
    
    def execute_shortcut(self, name: str):
        """Execute a custom shortcut"""
        name_lower = name.lower()
        if name_lower not in self.custom_shortcuts:
            return None  # Shortcut not found
        
        actions = self.custom_shortcuts[name_lower]
        print(f"{self.name}: Executing shortcut '{name}' ({len(actions)} action(s))...")
        
        results = []
        for action in actions:
            print(f"  → {action}")
            # Process each action as a command
            result = self.process_command(action, from_shortcut=True)
            if result:
                results.append(result)
            time.sleep(0.3)  # Small delay between actions
        
        return f"Shortcut '{name}' executed: {len(actions)} action(s) completed."
    
    # ==================== SECURITY & PIN ====================
    
    def set_pin(self, pin: str):
        """Set a PIN for application security"""
        import hashlib
        # Hash the PIN for security
        pin_hash = hashlib.sha256(pin.encode()).hexdigest()
        self.security_settings["pin_hash"] = pin_hash
        self.security_settings["pin_enabled"] = True
        self.save_security_settings()
    
    def verify_pin(self, pin: str) -> bool:
        """Verify a PIN against the stored hash"""
        import hashlib
        if not self.security_settings.get("pin_enabled", False):
            return True  # No PIN required
        pin_hash = hashlib.sha256(pin.encode()).hexdigest()
        return pin_hash == self.security_settings.get("pin_hash")
    
    def disable_pin(self):
        """Disable PIN protection"""
        self.security_settings["pin_enabled"] = False
        self.security_settings["pin_hash"] = None
        self.save_security_settings()
    
    def get_command_log(self):
        """Get command audit log"""
        try:
            log_file = self.config_dir / "command_log.json"
            if log_file.exists():
                with open(log_file, 'r') as f:
                    return json.load(f)
        except:
            pass
        return []
    
    def log_command(self, command: str, result: str):
        """Log a command execution"""
        try:
            log = self.get_command_log()
            log.append({
                "timestamp": datetime.datetime.now().isoformat(),
                "command": command,
                "result": result
            })
            # Keep only last 100 commands
            log = log[-100:]
            with open(self.config_dir / "command_log.json", 'w') as f:
                json.dump(log, f, indent=2)
        except:
            pass
    
    def export_command_log(self):
        """Export command log to a file"""
        try:
            log = self.get_command_log()
            export_path = Path.home() / "Desktop" / f"FreesIA_CommandLog_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(export_path, 'w') as f:
                json.dump(log, f, indent=2)
            return f"Command log exported to:\n{export_path}"
        except Exception as e:
            return f"Export failed: {str(e)}"
    
    def clear_command_log(self):
        """Clear command audit log"""
        try:
            log_file = self.config_dir / "command_log.json"
            if log_file.exists():
                log_file.unlink()
        except:
            pass
    
    def export_all_data(self):
        """Export all user data to Desktop"""
        try:
            export_dir = Path.home() / "Desktop" / f"FreesIA_Export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
            export_dir.mkdir(exist_ok=True)
            
            # Export permissions
            if (self.config_dir / "permissions.json").exists():
                import shutil
                shutil.copy(self.config_dir / "permissions.json", export_dir / "permissions.json")
            
            # Export security settings (without PIN hash for security)
            safe_security = {k: v for k, v in self.security_settings.items() if k != "pin_hash"}
            with open(export_dir / "security_settings.json", 'w') as f:
                json.dump(safe_security, f, indent=2)
            
            # Export user profile
            with open(export_dir / "user_profile.json", 'w') as f:
                json.dump(self.user_profile, f, indent=2)
            
            # Export command log
            log = self.get_command_log()
            with open(export_dir / "command_log.json", 'w') as f:
                json.dump(log, f, indent=2)
            
            return f"All data exported to:\n{export_dir}"
        except Exception as e:
            return f"Export failed: {str(e)}"
    
    def delete_all_data(self):
        """Delete all user data (factory reset)"""
        try:
            import shutil
            # Delete config directory
            if self.config_dir.exists():
                shutil.rmtree(self.config_dir)
            # Recreate empty config directory
            self.config_dir.mkdir(exist_ok=True)
            
            # Reset in-memory settings
            self.permissions = {
                "file_access": False,
                "system_settings": False,
                "power_control": False,
            }
            self.security_settings = {
                "pin_enabled": False,
                "pin_hash": None,
            }
            self.user_profile = {
                "nickname": "",
                "occupation": "",
                "visual_description": "",
                "likes": "",
                "dislikes": "",
                "other_info": ""
            }
            self.ai_conversation_history = []
            self.ai_conversation_summary = ""

            return "Factory reset complete. All data has been deleted."
        except Exception as e:
            return f"Factory reset failed: {str(e)}"
    
    def request_permission(self, permission_type: str) -> bool:
        """
        Request permission from user for sensitive operations with GUI popup
        Args:
            permission_type: Type of permission needed (file_access, system_settings, power_control)
        Returns: True if permission granted
        """
        # If permission already granted, return True
        if self.permissions.get(permission_type, False):
            return True
        
        # Define permission descriptions
        permission_descriptions = {
            "file_access": "access your files (search, read, delete)",
            "system_settings": "change system settings (volume, brightness, screenshots)",
            "power_control": "control power options (lock, sleep, shutdown, restart)"
        }
        
        permission_icons = {
            "file_access": "📁",
            "system_settings": "⚙️",
            "power_control": "🔌"
        }
        
        description = permission_descriptions.get(permission_type, 'perform this action')
        icon = permission_icons.get(permission_type, "🔒")
        
        # Create GUI popup for permission request
        try:
            # Create root window (hidden)
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            
            # Bring window to front
            root.attributes('-topmost', True)
            
            # Show permission dialog
            message = f"{icon} FreesIA needs permission to {description}.\n\n"
            message += "This permission will be saved for future sessions.\n"
            message += "You can revoke permissions anytime by typing 'revoke permissions'."
            
            result = messagebox.askyesno(
                "🔒 Security & Privacy Request",
                message,
                icon='question',
                parent=root
            )
            
            # Destroy the root window
            root.destroy()
            
            if result:
                # User clicked Yes
                self.permissions[permission_type] = True
                self.save_permissions()
                print(f"\n✓ Permission granted for {permission_type}\n")
                return True
            else:
                # User clicked No
                print(f"\n✗ Permission denied. This action cannot be performed.\n")
                return False
                
        except Exception as e:
            # Fallback to console if GUI fails
            print(f"\n{'='*60}")
            print(f"🔒 SECURITY & PRIVACY REQUEST")
            print(f"{'='*60}")
            print(f"\n{self.name} needs permission to {description}.")
            print("\nThis permission will be saved for future sessions.")
            print("You can revoke permissions anytime by typing 'revoke permissions'.")
            
            while True:
                response = input(f"\nGrant permission? (yes/no): ").strip().lower()
                
                if response in ['yes', 'y']:
                    self.permissions[permission_type] = True
                    self.save_permissions()
                    print(f"\n✓ Permission granted for {permission_type}")
                    print(f"{'='*60}\n")
                    return True
                elif response in ['no', 'n']:
                    print(f"\n✗ Permission denied. This action cannot be performed.")
                    print(f"{'='*60}\n")
                    return False
                else:
                    print("Please answer 'yes' or 'no'")
    
    def show_permissions(self):
        """Display current permission status"""
        print(f"\n{self.name}: Current Permissions:")
        print(f"  • File Access: {'✓ Granted' if self.permissions['file_access'] else '✗ Denied'}")
        print(f"  • System Settings: {'✓ Granted' if self.permissions['system_settings'] else '✗ Denied'}")
        print(f"  • Power Control: {'✓ Granted' if self.permissions['power_control'] else '✗ Denied'}")
        print()
    
    def revoke_permissions(self):
        """Revoke all permissions with confirmation dialog"""
        try:
            # Create GUI confirmation dialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            
            result = messagebox.askyesno(
                "Revoke Permissions",
                "Are you sure you want to revoke all permissions?\n\nYou will be asked again when these features are needed.",
                icon='warning',
                parent=root
            )
            
            root.destroy()
            
            if result:
                self.permissions = {
                    "file_access": False,
                    "system_settings": False,
                    "power_control": False,
                }
                self.save_permissions()
                print(f"\n{self.name}: All permissions have been revoked.")
                print("You will be asked again when these features are needed.\n")
            else:
                print(f"\n{self.name}: Permission revocation cancelled.\n")
                
        except:
            # Fallback to console
            confirm = input(f"\n{self.name}: Are you sure you want to revoke all permissions? (yes/no): ").strip().lower()
            if confirm in ['yes', 'y']:
                self.permissions = {
                    "file_access": False,
                    "system_settings": False,
                    "power_control": False,
                }
                self.save_permissions()
                print(f"\n{self.name}: All permissions have been revoked.")
                print("You will be asked again when these features are needed.\n")
            else:
                print(f"\n{self.name}: Permission revocation cancelled.\n")
    
    # ==================== OLLAMA AI INTEGRATION ====================
    
    def initialize_ollama(self):
        """Initialize Ollama and load personality from file"""
        try:
            # Check if Ollama is running and get available models
            available_models = ollama.list()
            
            # Handle different response formats (dict vs object)
            if hasattr(available_models, 'models'):
                # New format: object with models attribute
                installed_names = [getattr(m, 'model', '') or getattr(m, 'name', '') or '' for m in available_models.models]
            else:
                # Old format: dict with 'models' key
                installed_names = [m.get('model') or m.get('name') or '' for m in available_models.get('models', [])]
            self.ollama_installed_models = [n for n in installed_names if n]

            # Match by exact name first, then by the same model under any tag
            # (e.g. "phi4-mini:latest" configured but "phi4-mini:3.8b" installed).
            matched_main = self._match_installed_model(self.ollama_model, self.ollama_installed_models)
            matched_fast = self._match_installed_model(self.ollama_fast_model, self.ollama_installed_models)

            if not matched_main:
                self.ollama_enabled = False
                self.ollama_status = "model_missing"
                self.ollama_error = ""
                print(f"{self.name}: Ollama is running but model '{self.ollama_model}' not found.")
                print(f"          Installed: {', '.join(self.ollama_installed_models) or '(none)'}")
                print(f"          Download it with: ollama pull {self.ollama_model}")
                return
            if matched_main != self.ollama_model:
                print(f"{self.name}: Using installed '{matched_main}' for '{self.ollama_model}'.")
                self.ollama_model = matched_main

            if matched_fast:
                self.ollama_fast_model = matched_fast
            else:
                print(f"{self.name}: Fast model '{self.ollama_fast_model}' not found - using '{self.ollama_model}' for quick replies too.")
                print(f"          For faster responses on simple questions: ollama pull {self.ollama_fast_model}")
                self.ollama_fast_model = self.ollama_model
            
            self.ollama_enabled = True
            self.ollama_status = "ready"
            self.ollama_error = ""
            
            # Load personality from file
            personality_path = Path(__file__).parent / "Personality.txt"
            if personality_path.exists():
                with open(personality_path, 'r', encoding='utf-8') as f:
                    self.personality_prompt = f.read().strip()
                print(f"{self.name}: AI personality loaded from {personality_path.name}")
            else:
                # Default personality if file not found
                self.personality_prompt = self._default_personality()
                print(f"{self.name}: Using default personality (Personality.txt not found)")
            
            # Create condensed personality for simple messages (faster responses)
            self.condensed_personality = (f"You are {self.assistant_name}, a concise, helpful assistant. "
                                          "Answer directly in a sentence or two unless more detail is asked for.")
            self._default_condensed = self.condensed_personality
            self.apply_persona()
            
            print(f"{self.name}: Ollama AI enabled with model '{self.ollama_model}' (complex) and '{self.ollama_fast_model}' (simple/medium)")
            
        except Exception as e:
            self.ollama_enabled = False
            self.ollama_status = "offline"
            self.ollama_error = f"{type(e).__name__}: {e}"
            print(f"{self.name}: Ollama not detected ({self.ollama_error}). AI conversations will prompt for installation.")
            print(f"          Install from: https://ollama.ai")

    @staticmethod
    def _match_installed_model(wanted, installed):
        """Exact match, else the same model name under a different tag."""
        if not wanted:
            return None
        if wanted in installed:
            return wanted
        base = wanted.split(':')[0].lower()
        for name in installed:
            if name.split(':')[0].lower() == base:
                return name
        return None

    def ollama_unavailable_message(self) -> str:
        """Explain the real reason AI chat isn't available instead of always saying 'install Ollama'."""
        status = getattr(self, 'ollama_status', 'unknown')
        if status == "model_missing":
            have = ", ".join(getattr(self, 'ollama_installed_models', [])[:6]) or "none"
            return (f"Ollama is running, but the model '{self.ollama_model}' isn't installed (installed: {have}). "
                    f"Pick one you have in Settings > Models, or run: ollama pull {self.ollama_model}")
        detail = getattr(self, 'ollama_error', '')
        detail = f" Details: {detail[:140]}" if detail else ""
        return ("I can't reach Ollama. Make sure the Ollama app is running, then send your message again."
                f"{detail} (Not installed yet? https://ollama.com)")

    def _ensure_ollama_ready(self):
        """
        initialize_ollama() only ran once at startup - if Ollama's background
        service wasn't fully up yet at that exact moment (a timing race, not
        a real absence of Ollama), ollama_enabled got stuck False for the rest
        of the session with no way to recover short of restarting FreesIA.
        Retry lazily here instead, throttled so a genuinely-not-installed
        Ollama doesn't get re-checked on every single message.
        """
        if self.ollama_enabled:
            return
        now = time.time()
        if now - self._last_ollama_retry < 30:
            return
        self._last_ollama_retry = now
        self.initialize_ollama()

    # ==================== WINDOWS STARTUP ====================

    STARTUP_REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    STARTUP_VALUE_NAME = "FreesIA"

    def is_startup_enabled(self) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.STARTUP_REGISTRY_KEY) as key:
                winreg.QueryValueEx(key, self.STARTUP_VALUE_NAME)
                return True
        except FileNotFoundError:
            return False
        except Exception:
            return False

    def set_startup_enabled(self, enabled: bool) -> bool:
        """
        Adds/removes a HKCU Run key so FreesIA_GUI.py launches at Windows
        sign-in. Uses pythonw.exe (no console window) when available,
        falling back to the interpreter actually running this process.
        Returns True on success.
        """
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.STARTUP_REGISTRY_KEY, 0, winreg.KEY_SET_VALUE) as key:
                if enabled:
                    gui_script = Path(__file__).parent / "FreesIA_GUI.py"
                    pythonw = Path(sys.executable).with_name("pythonw.exe")
                    interpreter = str(pythonw) if pythonw.exists() else sys.executable
                    command = f'"{interpreter}" "{gui_script}"'
                    winreg.SetValueEx(key, self.STARTUP_VALUE_NAME, 0, winreg.REG_SZ, command)
                else:
                    try:
                        winreg.DeleteValue(key, self.STARTUP_VALUE_NAME)
                    except FileNotFoundError:
                        pass
            return True
        except Exception as e:
            print(f"{self.name}: Couldn't update startup setting: {e}")
            return False

    def lazy_load_vosk(self):
        """Lazy load Vosk model on first voice use"""
        if self.vosk_loading_attempted:
            return
        
        self.vosk_loading_attempted = True
        
        # Suppress verbose Vosk logging
        import os
        os.environ['VOSK_LOG_LEVEL'] = '-1'
        
        try:
            self.initialize_vosk_model()
        except Exception as e:
            print(f"{self.name}: Could not load offline voice model: {e}")
    
    def initialize_vosk_model(self):
        """Initialize Vosk model for offline voice recognition"""
        import json
        import urllib.request
        import zipfile
        
        try:
            # Define model path in config directory
            model_dir = self.config_dir / "vosk-model"
            
            # Check if model already exists
            if model_dir.exists() and (model_dir / "am" / "final.mdl").exists():
                self.vosk_model = vosk.Model(str(model_dir))
                self.vosk_recognizer = vosk.KaldiRecognizer(self.vosk_model, 16000)
                print(f"{self.name}: Offline voice recognition ready (Vosk model loaded)")
                return
            
            # Model not found, download it
            print(f"{self.name}: Downloading offline voice model (50MB, one-time download)...")
            model_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
            zip_path = self.config_dir / "vosk-model.zip"
            
            # Download with progress
            urllib.request.urlretrieve(model_url, zip_path)
            
            # Extract
            print(f"{self.name}: Extracting voice model...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.config_dir)
            
            # Rename extracted folder to vosk-model
            extracted_dir = self.config_dir / "vosk-model-small-en-us-0.15"
            if extracted_dir.exists():
                extracted_dir.rename(model_dir)
            
            # Clean up zip file
            zip_path.unlink()
            
            # Initialize Vosk
            self.vosk_model = vosk.Model(str(model_dir))
            self.vosk_recognizer = vosk.KaldiRecognizer(self.vosk_model, 16000)
            print(f"{self.name}: Offline voice recognition ready!")
            
        except Exception as e:
            print(f"{self.name}: Could not initialize offline voice model: {e}")
            print(f"          Falling back to online recognition if available.")
            self.vosk_model = None
            self.vosk_recognizer = None
    
    def vosk_recognize(self, audio_data):
        """
        Recognize speech using Vosk (offline)
        Returns: Recognized text or None
        """
        import json
        
        if not self.vosk_model or not self.vosk_recognizer:
            return None
        
        try:
            # Reset recognizer for new audio
            self.vosk_recognizer = vosk.KaldiRecognizer(self.vosk_model, 16000)
            
            # Convert audio to raw data
            raw_data = audio_data.get_raw_data(convert_rate=16000, convert_width=2)
            
            # Process audio
            if self.vosk_recognizer.AcceptWaveform(raw_data):
                result = json.loads(self.vosk_recognizer.Result())
            else:
                result = json.loads(self.vosk_recognizer.FinalResult())
            
            text = result.get('text', '')
            return text if text else None
            
        except Exception as e:
            print(f"{self.name}: Vosk recognition error: {e}")
            return None
    
    def analyze_message_complexity(self, message: str) -> dict:
        """Analyze message complexity and return appropriate AI settings with model selection"""
        msg_lower = message.lower().strip()
        word_count = len(message.split())
        
        # Simple greetings and short messages
        simple_patterns = [
            'hey', 'hello', 'hi', 'yo', 'sup', 'hiya',
            'good morning', 'good afternoon', 'good evening',
            'how are you', 'what\'s up', 'wassup',
            'thanks', 'thank you', 'okay', 'ok', 'cool',
            'bye', 'goodbye', 'see you', 'later',
            # Casual greeting variations
            'you good', 'you doing', 'you alright', 'you okay', 'you ok',
            'how\'s it', 'how it going', 'what\'s good', 'what up',
            # Casual/short statements
            'not installed', 'cant find', 'can\'t find', 'not found',
            'app not', 'program not', 'app isn\'t', 'program isn\'t'
        ]
        
        # Check if message is simple
        is_simple = (
            word_count <= 8 or  # Very short message (expanded from 6 to 8 to catch more short messages)
            any(pattern in msg_lower for pattern in simple_patterns)
        )
        
        # Check if message is complex (must not have triggered simple first)
        is_complex = (
            word_count > 20 or  # Long message
            ('?' in message and word_count > 10) or  # Detailed question
            any(word in msg_lower for word in ['explain', 'describe', 'tell me about', 'how does', 'what is', 'why', 'detail'])
        )
        
        # Return settings based on complexity
        # num_predict is a hard token cutoff, not sentence-aware - too tight a
        # cap means a reply gets chopped off mid-sentence instead of finishing
        # its thought. Bumped up across the board; CPU generation for these
        # model sizes is fast enough that the extra headroom costs little.
        temperature = 0.7
        # num_predict isn't a cost budget - this runs locally, there's no
        # per-token charge. It's purely a safety ceiling against runaway
        # generation (the model hallucinating endless fake dialogue if it
        # never naturally stops - see the stop sequences below, which handle
        # that directly). Since the only real cost of a higher ceiling is
        # extra generation time on the rare response that actually needs it,
        # these are set generously rather than tightly rationed.
        if is_simple:
            return {
                'model': self.ollama_fast_model,
                'personality': 'condensed',
                'num_predict': 120,  # Genuinely short intent (greetings, acks) - this one stays tight on purpose
                'temperature': temperature
            }
        elif is_complex:
            return {
                'model': self.ollama_model,
                'personality': 'full',
                'num_predict': 1000,
                'temperature': temperature
            }
        else:  # Medium complexity
            return {
                'model': self.ollama_fast_model,
                'personality': 'full',
                'num_predict': 700,
                'temperature': temperature
            }
    
    QUICK_RESPONSES = {
        'hi': ["Hi. What can I do for you?", "Hey. What do you need?", "Hi there. What's up?"],
        'hello': ["Hello. What can I help with?", "Hi. What do you need?", "Hello. I'm here."],
        'hey': ["Hey. What's up?", "Hey. How can I help?", "Hey there."],
        'yo': ["Hey. What's up?", "Yo. What do you need?", "Here. What's up?"],
        'sup': ["Not much. You?", "All good here. You?", "Ready when you are."],
        'hiya': ["Hiya. What do you need?", "Hey. What can I do?", "Hi. What's up?"],
        'good morning': ["Good morning. What's the plan?", "Morning. What can I help with?", "Good morning. Ready when you are."],
        'good afternoon': ["Good afternoon. What do you need?", "Afternoon. What can I do?", "Good afternoon. What's up?"],
        'good evening': ["Good evening. What can I do for you?", "Evening. What do you need?", "Good evening. What's on your mind?"],
        'how are you': ["Running fine. How about you?", "Doing well. How are you?", "All good. What about you?"],
        'what\'s up': ["Not much. What do you need?", "Ready to help. What's up?", "Nothing new. What can I do?"],
        'wassup': ["Not much. What's up?", "Hey. What do you need?", "All good. What's up with you?"],
        'thanks': ["You're welcome.", "Anytime.", "No problem."],
        'thank you': ["You're welcome.", "Happy to help.", "Anytime."],
        'okay': ["Okay. Anything else?", "Got it. What's next?", "Sure. Go on."],
        'ok': ["Okay. What's next?", "Got it. Anything else?", "Sure. Go on."],
        'cool': ["Glad to hear it. Anything else?", "Nice. What else?", "Sure. Anything else?"],
        'bye': ["Bye. Take care.", "See you later.", "Goodbye. Take care."],
        'goodbye': ["Goodbye. Take care.", "See you next time.", "Bye. Take care of yourself."],
        'see you': ["See you.", "See you later.", "Take care."],
        'later': ["Later.", "See you.", "Take care."],
    }

    def _get_quick_response(self, msg_lower: str):
        """
        Instant canned reply for common short greetings/acknowledgements, so
        those don't need a full LLM round-trip. Picks randomly from a few
        variants per phrase - a single fixed string per key meant every repeat
        of "hey"/"thanks"/"ok" in a conversation got back the exact same
        verbatim text, which read as the AI being stuck repeating itself.
        """
        variants = self.QUICK_RESPONSES.get(msg_lower)
        if not variants:
            return None
        import random
        return random.choice(variants)

    def chat_with_ai(self, user_message: str) -> str:
        """
        Send a message to Ollama AI and get a response
        Args:
            user_message: The user's message
        Returns: AI response string
        """
        self._ensure_ollama_ready()
        if not self.ollama_enabled:
            return self.ollama_unavailable_message()

        msg_lower = user_message.lower().strip()
        quick_response = self._get_quick_response(msg_lower)
        if quick_response is not None:
            response = quick_response
            # Still add to history for context
            self.ai_conversation_history.append({'role': 'user', 'content': user_message})
            self.ai_conversation_history.append({'role': 'assistant', 'content': response})
            self._condense_conversation_history()
            return response
        
        try:
            # Analyze message complexity and get appropriate settings
            settings = self.analyze_message_complexity(user_message)
            
            # Add user message to conversation history
            self.ai_conversation_history.append({
                'role': 'user',
                'content': user_message
            })
            
            # Choose personality prompt based on complexity
            chosen_personality = self._get_chat_personality(
                condensed=(settings['personality'] == 'condensed'), user_message=user_message
            )
            
            # Build messages with system prompt
            messages = [
                {'role': 'system', 'content': chosen_personality}
            ]
            if self.ai_conversation_summary:
                messages.append({'role': 'system', 'content': f"Earlier in this conversation: {self.ai_conversation_summary}"})
            messages += self.ai_conversation_history

            # Get response from Ollama (using appropriate model)
            chat_options = {
                'temperature': settings['temperature'],
                'top_p': 0.9,
                'num_predict': settings['num_predict'],
                # Stop generation before the model starts hallucinating a fake
                # continued conversation (writing both "User:" and assistant turns
                # itself) - without this it can wander past a good answer into
                # invented dialogue, sometimes looping back into exactly the
                # disclaimer phrasing we tell it not to use.
                # ``` also stops it - on rare occasions the model derails
                # entirely into writing fake Python (a "response generator
                # function" with comments), never something the character
                # should ever produce, so cut it the moment it starts.
                'stop': ['\nUser:', '\nUser ', 'User:', f'\n{self.assistant_name}:', '```'],
            }
            chat_options['repeat_penalty'] = 1.1
            response = ollama.chat(
                model=settings.get('model', self.ollama_model),  # Use model from settings
                messages=messages,
                options=chat_options,
                keep_alive="2h",  # keep the model warm between messages instead of Ollama's 5min default
            )
            
            ai_response = response['message']['content']
            
            # Add AI response to history
            self.ai_conversation_history.append({
                'role': 'assistant',
                'content': ai_response
            })
            
            # Keep conversation history manageable (last 10 exchanges)
            self._condense_conversation_history()

            return ai_response
            
        except Exception as e:
            return f"AI error: {str(e)}. Make sure Ollama is running and the model '{self.ollama_model}' is installed."
    
    def chat_with_ai_streaming(self, user_message: str, original_message: str = None, extra_instruction: str = ""):
        """
        Send a message to Ollama AI and get a streaming response
        Args:
            user_message: The user's message (may include context)
            original_message: The original message without context (for complexity analysis)
            extra_instruction: One-time extra system instruction for just this call (e.g. a
                "that was a dodge, be decisive" retry nudge) - not persisted anywhere.
        Yields: Chunks of AI response as they arrive
        """
        self._ensure_ollama_ready()
        if not self.ollama_enabled:
            yield self.ollama_unavailable_message()
            return

        # Use original message for complexity analysis if provided (without context)
        analysis_message = original_message if original_message else user_message

        # Quick response for simple greetings (instant, personality-aware)
        msg_lower = analysis_message.lower().strip()
        quick_response = self._get_quick_response(msg_lower)
        if quick_response is not None:
            response = quick_response
            # Stream it out character by character for smooth UI experience
            for char in response:
                yield char
            
            # Add to history for context
            self.ai_conversation_history.append({'role': 'user', 'content': user_message})
            self.ai_conversation_history.append({'role': 'assistant', 'content': response})
            self._condense_conversation_history()
            return

        try:
            # Analyze message complexity using original message (without context)
            settings = self.analyze_message_complexity(analysis_message)

            # Add user message to conversation history
            self.ai_conversation_history.append({
                'role': 'user',
                'content': user_message
            })

            chosen_personality = self._get_chat_personality(condensed=False, user_message=analysis_message) + extra_instruction
            # Build messages with system prompt
            messages = [
                {'role': 'system', 'content': chosen_personality}
            ]
            if self.ai_conversation_summary:
                messages.append({'role': 'system', 'content': f"Earlier in this conversation: {self.ai_conversation_summary}"})
            messages += self.ai_conversation_history

            # Stream response from Ollama (using appropriate model)
            full_response = ""
            import ollama
            stream_options = {
                'temperature': settings['temperature'],
                'top_p': 0.9,
                'num_predict': settings['num_predict'],
                'stop': ['\nUser:', '\nUser ', 'User:', f'\n{self.assistant_name}:', '```'],
            }
            stream_options['repeat_penalty'] = 1.1
            stream = ollama.chat(
                model=settings.get('model', self.ollama_model),  # Use model from settings
                messages=messages,
                stream=True,
                options=stream_options,
                keep_alive="2h",
            )

            for chunk in stream:
                if 'message' in chunk and 'content' in chunk['message']:
                    text = chunk['message']['content']
                    full_response += text
                    yield text

            # Add AI response to history
            self.ai_conversation_history.append({
                'role': 'assistant',
                'content': full_response
            })

            # Keep conversation history manageable
            self._condense_conversation_history()

        except Exception as e:
            import traceback
            error_message = f"[AI Error: {str(e)}. Make sure Ollama is running and the model '{self.ollama_model}' is installed.]"
            # Log error to file if possible
            try:
                with open("freesia_error.log", "a", encoding="utf-8") as f:
                    f.write("\n--- AI Streaming Error ---\n")
                    f.write(traceback.format_exc())
            except Exception:
                pass
            yield error_message
    
    # ==================== CONTEXT AWARENESS ====================
    
    def get_active_window_context(self) -> str:
        """Get information about the currently active window for context awareness"""
        try:
            import win32gui
            import win32process
            import psutil
            
            # Get active window
            hwnd = win32gui.GetForegroundWindow()
            window_title = win32gui.GetWindowText(hwnd)
            
            # Get process name
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                process = psutil.Process(pid)
                process_name = process.name()
                
                # Build context string
                if process_name and window_title:
                    return f"[User is currently in {process_name}: '{window_title}']"
            except:
                pass
                
        except Exception:
            pass
        
        return ""
    
    def clear_ai_history(self):
        """Clear AI conversation history"""
        self.ai_conversation_history = []
        self.ai_conversation_summary = ""
        print(f"{self.name}: AI conversation history cleared.")

    def _condense_conversation_history(self, keep_recent: int = 24):
        """
        Once the conversation gets long, fold the oldest messages into a
        running summary instead of just dropping them - hard-truncating at a
        fixed count loses whatever was said before that window forever, which
        reads as the assistant forgetting things mentioned only a few messages earlier
        in a longer chat. Best-effort: if summarization fails for any reason,
        the recent window is still trimmed and kept, just without folding the
        older context in for this round.
        keep_recent=24 is a deliberate balance, not a model limit - phi4-mini/
        llama3.2:3b both handle far more context than this. Keeping more
        messages verbatim means more tokens per request, which is real added
        latency on CPU-only local inference (no cloud GPU absorbing the cost).
        """
        if len(self.ai_conversation_history) <= 40:
            return
        to_summarize = self.ai_conversation_history[:-keep_recent]
        self.ai_conversation_history = self.ai_conversation_history[-keep_recent:]
        if not to_summarize:
            return

        transcript = "\n".join(
            f"{'User' if m['role'] == 'user' else self.assistant_name}: {m['content']}"
            for m in to_summarize
        )
        try:
            import ollama
            prompt = (
                "Summarize this conversation excerpt in 2-3 short sentences, capturing "
                "any facts, decisions, or context that matter for continuing the "
                "conversation naturally. Third person, no preamble, just the summary."
            )
            if self.ai_conversation_summary:
                prompt += f"\n\nEarlier summary so far: {self.ai_conversation_summary}"
            resp = ollama.chat(
                model=self.ollama_fast_model,
                messages=[{'role': 'system', 'content': prompt}, {'role': 'user', 'content': transcript}],
                options={'temperature': 0.3, 'num_predict': 150},
                keep_alive="2h",
            )
            self.ai_conversation_summary = resp['message']['content'].strip()
        except Exception:
            pass
    
    def change_ai_model(self, model_name: str):
        """Change the Ollama model being used"""
        try:
            # Test if model is available
            ollama.chat(model=model_name, messages=[{'role': 'user', 'content': 'test'}])
            self.ollama_model = model_name
            self.clear_ai_history()
            print(f"{self.name}: Switched to model '{model_name}'")
        except Exception as e:
            print(f"{self.name}: Model '{model_name}' not available. Use 'ollama pull {model_name}' to download it.")
    
    def reload_personality(self):
        """Reload personality from file"""
        try:
            personality_path = self._custom_personality_path()
            if personality_path.exists():
                self.apply_persona()
                self.clear_ai_history()
                print(f"{self.name}: Personality reloaded from {personality_path.name}")
            else:
                print(f"{self.name}: Personality.txt not found next to the program")
        except Exception as e:
            print(f"{self.name}: Error reloading personality: {e}")
    
    # ==================== DATA PERSISTENCE ====================
    
    def load_data(self):
        """Load saved notes and to-do lists from JSON files"""
        try:
            # Load to-do list
            todo_file = self.config_dir / "todo.json"
            if todo_file.exists():
                with open(todo_file, 'r') as f:
                    self.todo_list = json.load(f)
            
            # Load notes
            notes_file = self.config_dir / "notes.json"
            if notes_file.exists():
                with open(notes_file, 'r') as f:
                    self.notes = json.load(f)
        except:
            pass  # If loading fails, start with empty lists
    
    def save_data(self):
        """Save notes and to-do lists to JSON files for persistence"""
        try:
            # Save to-do list
            with open(self.config_dir / "todo.json", 'w') as f:
                json.dump(self.todo_list, f, indent=2)
            
            # Save notes
            with open(self.config_dir / "notes.json", 'w') as f:
                json.dump(self.notes, f, indent=2)
        except:
            pass  # Silently fail if save unsuccessful
    
    # ==================== APPLICATION SCANNING ====================
    
    def load_app_cache(self) -> Dict[str, str]:
        """Load cached app list if it exists and is recent"""
        import json
        from datetime import datetime, timedelta
        
        if not self.app_cache_file.exists():
            return {}
        
        try:
            with open(self.app_cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Check cache age
            cache_time = datetime.fromisoformat(cache_data.get('timestamp', ''))
            if datetime.now() - cache_time < timedelta(days=self.app_cache_max_age):
                return cache_data.get('apps', {})
        except:
            pass
        
        return {}
    
    def save_app_cache(self):
        """Save app list to cache"""
        import json
        from datetime import datetime
        
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'apps': self.installed_apps
            }
            with open(self.app_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
        except Exception as e:
            print(f"{self.name}: Could not save app cache: {e}")

    def load_folder_cache(self) -> Dict[str, str]:
        """Load the cached custom-folder list if it exists"""
        if not self.folder_cache_file.exists():
            return {}
        try:
            with open(self.folder_cache_file, 'r', encoding='utf-8') as f:
                return json.load(f).get('folders', {})
        except Exception:
            return {}

    def save_folder_cache(self):
        """Persist the custom-folder list"""
        from datetime import datetime
        try:
            with open(self.folder_cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'folders': self.custom_folders,
                }, f, indent=2)
        except Exception as e:
            print(f"{self.name}: Could not save folder cache: {e}")

    def scan_desktop_folders(self) -> Dict[str, str]:
        """
        Discover folders the user can plausibly mean by name, beyond the
        fixed SYSTEM_FOLDERS set: real subfolders sitting directly on the
        Desktop, plus Desktop .lnk shortcuts whose target is a folder (not an
        app) - a common way people pin a project or network folder.
        """
        folders = {}
        desktop = Path.home() / "Desktop"
        if not desktop.exists():
            return folders

        try:
            for item in desktop.iterdir():
                if item.is_dir():
                    folders[item.name.lower()] = str(item)
        except (PermissionError, OSError):
            pass

        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            for lnk in desktop.glob("*.lnk"):
                try:
                    target = shell.CreateShortCut(str(lnk)).Targetpath
                    if target and Path(target).is_dir():
                        folders[lnk.stem.lower()] = target
                except Exception:
                    continue
        except Exception:
            pass  # win32com unavailable - subfolder results above still stand

        return folders

    def rescan_folders(self) -> int:
        """Force a rescan of Desktop folders/shortcuts. Returns how many were found."""
        message = "Rescanning folders, this may take a moment..."
        print(f"{self.name}: {message}")
        self.speak(message)
        self.custom_folders = self.scan_desktop_folders()
        self.save_folder_cache()
        done_message = f"Found {len(self.custom_folders)} folders."
        print(f"{self.name}: {done_message}")
        self.speak(done_message)
        return len(self.custom_folders)

    def rescan_apps(self):
        """Force rescan of installed applications"""
        message = "Rescanning installed applications, this may take a moment..."
        print(f"{self.name}: {message}")
        self.speak(message)
        self.installed_apps = self.scan_installed_apps()
        self.save_app_cache()
        self.app_keywords = list(self.installed_apps.keys())
        done_message = f"Found {len(self.installed_apps)} applications."
        print(f"{self.name}: {done_message}")
        self.speak(done_message)
    
    def scan_installed_apps(self) -> Dict[str, str]:
        """
        Scan the system for installed applications (optimized for speed)
        Returns: Dictionary mapping app names to their executable paths
        """
        # Start with built-in Windows applications
        apps = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "paint": "mspaint.exe",
            "explorer": "explorer.exe",
            "cmd": "cmd.exe",
            "powershell": "powershell.exe",
            "task manager": "taskmgr.exe",
            "control panel": "control.exe",
            "settings": "ms-settings:",
        }
        
        # Define common application installation paths with limited depth
        app_paths = [
            Path(r"C:\Program Files"),
            Path(r"C:\Program Files (x86)"),
        ]
        
        # Microsoft Store apps path (for Spotify, etc.)
        windows_apps_path = Path.home() / "AppData" / "Local" / "Microsoft" / "WindowsApps"
        
        # Common third-party applications and their executable names
        common_apps = {
            "chrome": ["chrome.exe"],
            "firefox": ["firefox.exe"],
            "edge": ["msedge.exe"],
            "brave": ["brave.exe"],
            "opera": ["opera.exe"],
            "spotify": ["Spotify.exe"],
            "discord": ["Discord.exe"],
            "slack": ["slack.exe"],
            "teams": ["Teams.exe"],
            "zoom": ["Zoom.exe"],
            "vscode": ["Code.exe"],
            "visual studio": ["devenv.exe"],
            "sublime": ["sublime_text.exe"],
            "notepad++": ["notepad++.exe"],
            "atom": ["atom.exe"],
            "word": ["WINWORD.EXE"],
            "excel": ["EXCEL.EXE"],
            "powerpoint": ["POWERPNT.EXE"],
            "outlook": ["OUTLOOK.EXE"],
            "onenote": ["ONENOTE.EXE"],
            "photoshop": ["Photoshop.exe"],
            "illustrator": ["Illustrator.exe"],
            "premiere": ["Adobe Premiere Pro.exe"],
            "steam": ["steam.exe"],
            "epic games": ["EpicGamesLauncher.exe"],
            "obs": ["obs64.exe", "obs32.exe"],
            "vlc": ["vlc.exe"],
            "winrar": ["WinRAR.exe"],
            "7zip": ["7zFM.exe"],
            "gimp": ["gimp-2.10.exe"],
            "blender": ["blender.exe"],
            "audacity": ["audacity.exe"],
            "itunes": ["iTunes.exe"],
            "python": ["python.exe"],
            "pycharm": ["pycharm64.exe"],
            "intellij": ["idea64.exe"],
            "android studio": ["studio64.exe"],
        }
        
        # Optimized search: limit depth and use iterdir instead of rglob
        for app_name, exe_names in common_apps.items():
            for exe_name in exe_names:
                for base_path in app_paths:
                    if not base_path.exists():
                        continue
                    try:
                        # Only search 3 levels deep to avoid slow recursive search
                        found = False
                        for level1 in base_path.iterdir():
                            if found:
                                break
                            if not level1.is_dir():
                                continue
                            try:
                                for level2 in level1.iterdir():
                                    if found:
                                        break
                                    if not level2.is_dir():
                                        # Check current level
                                        if level2.name.lower() == exe_name.lower():
                                            apps[app_name.lower()] = str(level2)
                                            found = True
                                            break
                                    try:
                                        for level3 in level2.iterdir():
                                            if found:
                                                break
                                            if not level3.is_dir():
                                                if level3.name.lower() == exe_name.lower():
                                                    apps[app_name.lower()] = str(level3)
                                                    found = True
                                                    break
                                    except (PermissionError, OSError):
                                        continue
                            except (PermissionError, OSError):
                                continue
                    except (PermissionError, OSError):
                        continue
                    if app_name.lower() in apps:
                        break
                if app_name.lower() in apps:
                    break
        
        # Also scan Windows Registry for installed programs
        try:
            apps.update(self.scan_registry_apps())
        except:
            pass  # If registry scan fails, continue with what we have
        
        # Also scan Microsoft Store apps folder for modern apps (like Spotify)
        try:
            if windows_apps_path.exists():
                # Store apps are symlinks or shortcuts, try to read them
                for item in windows_apps_path.iterdir():
                    try:
                        # Check both files and symlinks
                        if item.is_file() or item.is_symlink():
                            app_name = item.stem.lower()
                            if app_name not in apps and (item.suffix.lower() == '.exe' or item.is_symlink()):
                                apps[app_name] = str(item)
                    except (PermissionError, OSError):
                        continue
        except:
            pass  # If Windows Apps scan fails, continue
        
        # Try PowerShell to find Store apps (more reliable)
        try:
            # Use PowerShell to get installed Windows Store apps.
            # No -AllUsers: that flag requires admin elevation and throws
            # "Access is denied" under a normal session, which silently
            # dropped every MSIX/UWP app (Claude Desktop, etc.) from the scan
            # since the failure was swallowed by the outer try/except.
            # Per-user (no flag) still finds apps installed for this user,
            # which covers the normal case without needing elevation.
            ps_command = """
            $apps = Get-AppxPackage | Select-Object Name, InstallLocation
            foreach ($app in $apps) {
                $name = $app.Name -replace 'Microsoft\\.|_.*', '' | select -first 1
                Write-Output "$($name.ToLower())|$($app.InstallLocation)"
            }
            """
            result = subprocess.run(
                ['powershell', '-NoProfile', '-Command', ps_command],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if '|' in line:
                        app_name, install_dir = line.strip().split('|', 1)
                        app_name = app_name.strip().lower()
                        if app_name and install_dir and Path(install_dir).exists():
                            # Look for the app's main executable
                            install_path = Path(install_dir)
                            # Check common executable names
                            exe_names = [f"{app_name}.exe", "app.exe", "main.exe"]
                            for exe_name in exe_names:
                                exe_path = install_path / exe_name
                                if exe_path.exists():
                                    apps[app_name] = str(exe_path)
                                    break
                            # If not found, just store the directory path for later resolution
                            if app_name not in apps:
                                # Try to find any exe file
                                exe_files = self._find_exe_candidates(install_path)
                                if exe_files:
                                    apps[app_name] = str(self._pick_best_exe(exe_files, app_name))
        except:
            pass  # If PowerShell query fails, continue

        # Scan Start Menu shortcuts - the closest thing Windows has to a canonical
        # "everything installed" list. Almost every installer creates one here
        # regardless of where it actually put the app's files (Program Files,
        # AppData\Local\Programs, a version-numbered Squirrel folder, etc.), so this
        # catches apps the folder/registry scans above miss entirely.
        try:
            apps.update(self.scan_start_menu_shortcuts())
        except Exception:
            pass

        return apps

    def scan_start_menu_shortcuts(self) -> Dict[str, str]:
        """Resolve .lnk shortcuts in the Start Menu to their target .exe paths"""
        apps = {}
        start_menu_dirs = [
            Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"),
            Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        ]
        try:
            shell = win32com.client.Dispatch("WScript.Shell")
        except Exception:
            return apps

        for start_dir in start_menu_dirs:
            if not start_dir.exists():
                continue
            try:
                for lnk in start_dir.rglob("*.lnk"):
                    try:
                        target = shell.CreateShortCut(str(lnk)).Targetpath
                        if target and target.lower().endswith(".exe") and Path(target).exists():
                            apps[lnk.stem.lower()] = target
                    except Exception:
                        continue
            except (PermissionError, OSError):
                continue
        return apps

    def _find_exe_candidates(self, install_path: Path) -> list:
        """
        Find candidate .exe files under an install directory, checking the top level
        and up to 2 levels deep. Some apps (e.g. Discord, which uses the Squirrel
        updater) keep the real executable one level deeper in a version-numbered
        subfolder (app-1.2.3\\Discord.exe) with only an updater shim at the top level,
        so results are combined across depths rather than stopping at the first
        non-empty level - a shim at the top shouldn't hide the real exe underneath.
        """
        candidates = []
        for pattern in ("*.exe", "*/*.exe", "*/*/*.exe"):
            candidates.extend(install_path.glob(pattern))
            if len(candidates) > 100:  # bail out on pathologically large install trees
                break
        return candidates

    def _pick_best_exe(self, exe_files: list, app_name: str) -> Path:
        """
        Pick the exe that's actually the app, not the first one alphabetically.
        An install folder often has multiple .exe files (crashpad_handler.exe,
        Update.exe, uninstall.exe, etc.) that happen to sort before the real one -
        e.g. Spotify's folder has crashpad_handler.exe before Spotify.exe, and
        Discord's shortcut is Update.exe rather than Discord.exe itself.
        """
        def normalize(s: str) -> str:
            return re.sub(r'[^a-z0-9]', '', s.lower())

        normalized_app = normalize(app_name)
        helper_markers = ['uninstall', 'unins0', 'crashpad', 'setup', 'updater',
                           'update', 'helper', 'service', 'cli', 'installer']
        candidates = [e for e in exe_files if not any(m in normalize(e.stem) for m in helper_markers)]
        pool = candidates if candidates else exe_files

        # Prefer an exact name match first, then a substring match, else just take the first
        for exe in pool:
            if normalize(exe.stem) == normalized_app:
                return exe
        for exe in pool:
            stem = normalize(exe.stem)
            if normalized_app in stem or stem in normalized_app:
                return exe
        return pool[0]

    def scan_registry_apps(self) -> Dict[str, str]:
        """
        Scan Windows Registry for additional installed applications
        Returns: Dictionary of app names to executable paths
        """
        apps = {}
        
        # Registry paths where Windows stores installed program info
        registry_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")
        ]
        
        for hkey, reg_path in registry_paths:
            try:
                key = winreg.OpenKey(hkey, reg_path)
                
                # Iterate through all subkeys (installed programs)
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey = winreg.OpenKey(hkey, f"{reg_path}\\{subkey_name}")
                        
                        try:
                            # Get display name and installation location
                            display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                            install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                            
                            # Clean up app name (remove special characters)
                            app_name = display_name.lower()
                            app_name = re.sub(r'[^\w\s]', '', app_name).strip()
                            
                            # Find executable in installation directory
                            if install_location and Path(install_location).exists():
                                install_path = Path(install_location)
                                exe_files = self._find_exe_candidates(install_path)
                                if exe_files:
                                    apps[app_name] = str(self._pick_best_exe(exe_files, app_name))
                        except:
                            pass  # Skip if registry values don't exist
                        
                        winreg.CloseKey(subkey)
                    except:
                        continue  # Skip problematic entries
                        
                winreg.CloseKey(key)
            except:
                continue  # Skip if can't access registry path
        
        return apps
    
    # ==================== FUZZY MATCHING & CORRECTION ====================
    
    def fuzzy_match(self, word: str, options: List[str], threshold: float = 0.6) -> str:
        """
        Find the closest matching word from a list of options
        Args:
            word: The word to match
            options: List of possible matches
            threshold: Minimum similarity score (0-1)
        Returns: Best match or None
        """
        matches = get_close_matches(word.lower(), options, n=1, cutoff=threshold)
        if not matches:
            return None
        best = matches[0]
        # SequenceMatcher's ratio is prefix-biased - a genuinely different but
        # longer word that happens to start with a short keyword (e.g.
        # "downloads" vs "down", "theme" vs "the") scores high enough to pass
        # a 0.6 cutoff even though it's not a typo of that word at all. A real
        # typo correction only ever needs to fix a couple of characters, so
        # reject matches where the length gap is too large to be a plausible
        # misspelling.
        if abs(len(word) - len(best)) > 2:
            return None
        return best
    
    def correct_command(self, command: str) -> str:
        """
        Auto-correct typos in commands using fuzzy matching
        Shows corrections to user for transparency
        
        IMPORTANT: Simple greetings are NOT auto-corrected to preserve instant responses
        """
        # Simple greetings should never be corrected
        simple_greetings = [
            'hi', 'hello', 'hey', 'yo', 'sup', 'hiya',
            'good morning', 'good afternoon', 'good evening',
            'how are you', "what's up", 'wassup',
            'thanks', 'thank you', 'okay', 'ok', 'cool',
            'bye', 'goodbye', 'see you', 'later'
        ]
        
        if command.lower().strip() in simple_greetings:
            return command  # Return unchanged to preserve instant response
        
        words = command.lower().split()
        corrected_words = []

        # Category keywords that should never be corrected
        category_keywords = ["voice", "system", "file", "files", "web", "app", "apps",
                           "media", "productivity", "clipboard", "security", "privacy", "other",
                           "folder", "folders", "document", "documents", "program", "programs", "software"]

        # Common short stopwords ("the", "a", "to"...) get skipped entirely -
        # short strings are inherently prone to false-positive fuzzy matches
        # (e.g. "the" -> "theme" at threshold 0.6, since a 1-letter edit on a
        # 3-letter word is already a high similarity ratio), and correcting
        # grammatical filler words serves no purpose anyway.
        stopwords = {"the", "a", "an", "to", "of", "in", "on", "at", "for", "and",
                     "please", "my", "me", "is", "it", "this", "that"}

        for word in words:
            # Skip correction for category keywords and short stopwords
            if word in category_keywords or word in stopwords:
                corrected_words.append(word)
                continue
            
            # Try matching against command keywords
            match = self.fuzzy_match(word, self.command_keywords, threshold=0.6)
            if match:
                corrected_words.append(match)
                if match != word:
                    print(f"{self.name}: Did you mean '{match}'? (corrected from '{word}')")
            
            # Try matching against app names - DON'T auto-correct, just keep original
            elif self.fuzzy_match(word, self.app_keywords, threshold=0.6):
                corrected_words.append(word)  # Keep original word, will suggest later
            
            # Try matching against volume keywords
            elif self.fuzzy_match(word, self.volume_keywords, threshold=0.6):
                vol_match = self.fuzzy_match(word, self.volume_keywords, threshold=0.6)
                corrected_words.append(vol_match)
                if vol_match != word:
                    print(f"{self.name}: Did you mean '{vol_match}'? (corrected from '{word}')")
            
            # Try matching against brightness keywords
            elif self.fuzzy_match(word, self.brightness_keywords, threshold=0.6):
                bright_match = self.fuzzy_match(word, self.brightness_keywords, threshold=0.6)
                corrected_words.append(bright_match)
                if bright_match != word:
                    print(f"{self.name}: Did you mean '{bright_match}'? (corrected from '{word}')")
            else:
                corrected_words.append(word)  # Keep original if no match
        
        return " ".join(corrected_words)
    
    # ==================== VOICE RECOGNITION ====================
    
    def listen(self):
        """
        Listen for voice input using microphone (OFFLINE with Vosk)
        Returns: Transcribed text or None if unsuccessful
        """
        if not self.voice_available:
            print(f"\n{self.name}: Voice recognition is not available.")
            print(f"Please install PyAudio: pip install PyAudio")
            print(f"Or use text commands instead.\n")
            return None
        
        # Lazy load Vosk model on first use
        if not self.vosk_model and not self.vosk_loading_attempted:
            self.lazy_load_vosk()
            
        try:
            with sr.Microphone() as source:
                print(f"\n{self.name}: Listening...")
                # Adjust for ambient noise to improve recognition
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=5)
                
                # Try Vosk first (offline)
                if self.vosk_model:
                    text = self.vosk_recognize(audio)
                    if text:
                        print(f"You said: {text}")
                        return text
                
                # Fallback to Google (online) if Vosk fails or not available
                text = self.recognizer.recognize_google(audio)
                print(f"You said: {text}")
                return text
                
        except sr.WaitTimeoutError:
            print(f"{self.name}: No speech detected (timeout).")
            return None
        except sr.UnknownValueError:
            print(f"{self.name}: I didn't catch that. Please try again.")
            return None
        except Exception as e:
            print(f"{self.name}: Voice error: {e}")
            print(f"\nTroubleshooting:")
            print(f"  • Make sure PyAudio is installed: pip install PyAudio")
            print(f"  • Check if your microphone is working")
            print(f"  • Try text commands instead\n")
            return None
    
    def continuous_listen(self):
        """Continuous listening mode - like Alexa/Siri always listening"""
        if not self.voice_available:
            error_msg = "Voice recognition is not available."
            print(f"\n{self.name}: {error_msg}")
            print(f"Please install PyAudio: pip install PyAudio")
            print(f"Or use text commands instead.\n")
            self.speak(error_msg)
            self.listening_active = False
            return
        
        # Lazy load Vosk model on first use
        if not self.vosk_model and not self.vosk_loading_attempted:
            self.lazy_load_vosk()
        
        print(f"{self.name}: Continuous listening activated! 🎤")
        print(f"Say 'FreesIA' (like the flower) to give commands.")
        print(f"Say 'mic off' or 'stop listening' to deactivate.\n")
        
        self.listening_active = True
        consecutive_errors = 0
        max_consecutive_errors = 3
        
        while self.listening_active:
            try:
                # Wrap microphone in try-catch to handle busy device
                try:
                    with sr.Microphone() as source:
                        self.recognizer.adjust_for_ambient_noise(source, duration=0.2)
                        audio = self.recognizer.listen(source, timeout=None, phrase_time_limit=5)
                        consecutive_errors = 0  # Reset error counter on success
                except (OSError, Exception) as mic_error:
                    # Handle microphone access errors
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        print(f"\n{self.name}: Microphone error (device may be busy). Stopping listening.")
                        print(f"Please close other audio applications and try again.\n")
                        self.listening_active = False
                        break
                    time.sleep(1)  # Wait before retrying
                    continue
                
                try:
                    # Try Vosk first (offline)
                    if self.vosk_model:
                        text = self.vosk_recognize(audio)
                    else:
                        text = None
                    
                    # Fallback to Google if Vosk fails
                    if not text:
                        text = self.recognizer.recognize_google(audio)
                    
                    if not text:
                        continue  # No audio detected
                    
                    text_lower = text.lower()
                    
                    # Check for mic off command first (highest priority)
                    if any(phrase in text_lower for phrase in ["mic off", "microphone off", "stop listening", "turn off mic"]):
                        print(f"\n🎤 Heard: {text}")
                        self.stop_listening()
                        return
                    
                    # Only print if wake word detected (less spam)
                    if self.check_wake_word(text):
                        print(f"\n🎤 Heard: {text}")
                        self.respond_to_wake_word()
                        
                        # Small delay to let TTS finish speaking
                        time.sleep(0.3)
                        
                        # Immediately start listening for command
                        print(f"{self.name}: Listening for your command...")
                        try:
                            try:
                                with sr.Microphone() as source2:
                                    self.recognizer.adjust_for_ambient_noise(source2, duration=0.1)
                                    audio2 = self.recognizer.listen(source2, timeout=self.command_timeout, phrase_time_limit=self.command_phrase_limit)
                                    consecutive_errors = 0  # Reset on success
                            except (OSError, Exception) as mic_err:
                                print(f"{self.name}: Microphone access error. Try again.")
                                print(f"\n{self.name}: Still listening... (say 'FreesIA' or 'mic off' to stop)")
                                continue
                            
                            try:
                                # Try Vosk first (offline)
                                if self.vosk_model:
                                    command = self.vosk_recognize(audio2)
                                else:
                                    command = None
                                
                                # Fallback to Google if Vosk fails
                                if not command:
                                    command = self.recognizer.recognize_google(audio2)
                                
                                if not command:
                                    msg = "I didn't catch that. Please try again."
                                    print(f"{self.name}: {msg}")
                                    self.speak(msg)
                                    print(f"\n{self.name}: Still listening... (say 'FreesIA' or 'mic off' to stop)")
                                    continue
                                
                                print(f"🎤 Command heard: {command}")
                                
                                # Check for mic off command before processing
                                if any(phrase in command.lower() for phrase in ["mic off", "microphone off", "stop listening", "turn off mic"]):
                                    self.stop_listening()
                                    return
                                
                                self.process_command(command)
                                print(f"\n{self.name}: Still listening... (say 'FreesIA' or 'mic off' to stop)")
                            except sr.UnknownValueError:
                                msg = "I didn't understand that command."
                                print(f"{self.name}: {msg}")
                                self.speak(msg)
                                print(f"\n{self.name}: Still listening... (say 'FreesIA' or 'mic off' to stop)")
                            except Exception as cmd_err:
                                print(f"{self.name}: Error processing command: {cmd_err}")
                                print(f"\n{self.name}: Still listening... (say 'FreesIA' or 'mic off' to stop)")
                                
                        except sr.WaitTimeoutError:
                            msg = "I didn't hear a command."
                            print(f"{self.name}: {msg}")
                            self.speak(msg)
                            print(f"\n{self.name}: Still listening... (say 'FreesIA' or 'mic off' to stop)")
                        except Exception as e:
                            print(f"{self.name}: Listening error: {e}")
                            print(f"\n{self.name}: Still listening... (say 'FreesIA' or 'mic off' to stop)")
                    
                except sr.UnknownValueError:
                    pass  # Ignore if nothing understood (background noise)
                except Exception as e:
                    pass  # Ignore other recognition errors in continuous mode
                        
            except KeyboardInterrupt:
                print(f"\n{self.name}: Exiting listening mode.")
                self.listening_active = False
                break
            except Exception as e:
                if self.listening_active:
                    print(f"{self.name}: Listening error: {e}")
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        print(f"{self.name}: Too many errors. Stopping listening mode.\n")
                        self.listening_active = False
                        break
                    time.sleep(1)  # Brief pause before retrying

    def start_listening_background(self):
        """Start continuous listening in background thread"""
        if self.listening_active:
            message = "Microphone is already active!"
            print(f"{self.name}: {message}")
            self.speak(message)
            return
        
        if not self.voice_available:
            message = "Voice recognition is not available."
            print(f"\n{self.name}: {message}")
            print(f"Please install PyAudio and check your microphone.\n")
            self.speak(message)
            return
        
        # Auto-enable TTS when microphone turns on
        if self.tts_engine and not self.tts_enabled:
            self.tts_enabled = True
            print(f"{self.name}: Text-to-speech auto-enabled with microphone.")

        # Manually turning the mic on is a deliberate choice - don't treat it as
        # something the call-app monitor needs to auto-pause/resume around.
        self.mic_paused_for_call = False
        call_app = self.get_running_call_app()
        if call_app:
            print(f"{self.name}: Heads up - {call_app} is running.")
        self._call_app_prev_active = call_app is not None

        # Start listening in a separate thread
        self.listening_thread = threading.Thread(target=self.continuous_listen, daemon=True)
        self.listening_thread.start()

    def stop_listening(self):
        """Stop continuous listening"""
        if not self.listening_active:
            message = "Microphone is already off."
            print(f"{self.name}: {message}")
            self.speak(message)
            return

        self.listening_active = False
        # A manual stop overrides any auto-pause bookkeeping so the call-app
        # monitor won't try to auto-resume the mic once the call app closes.
        self.mic_paused_for_call = False
        message = "Microphone deactivated."
        print(f"\n{self.name}: {message}")
        print(f"Type 'mic on' to start listening again.\n")
        self.speak(message)

        # Note: TTS stays in its current state when mic turns off
        # User can manually control TTS with 'toggle tts'

    def get_running_call_app(self) -> str | None:
        """
        Check whether a known call app (Discord/Teams/Zoom/Skype) is currently running.
        Returns: Display name of the running call app, or None
        """
        try:
            for proc in psutil.process_iter(['name']):
                proc_name = (proc.info.get('name') or '').lower()
                if proc_name in self.call_apps_watch:
                    return self.call_apps_watch[proc_name]
        except Exception:
            pass
        return None

    def start_call_app_monitor(self):
        """Start a background thread that auto-pauses the mic when a call app opens."""
        if self._call_monitor_running:
            return
        self._call_monitor_running = True
        monitor_thread = threading.Thread(target=self._call_app_monitor_loop, daemon=True)
        monitor_thread.start()

    def _call_app_monitor_loop(self):
        """Poll for call apps and auto-pause/resume the mic on rising/falling edges."""
        while self._call_monitor_running:
            try:
                call_app = self.get_running_call_app()
                is_active = call_app is not None

                # Rising edge: a call app just started while we were actively listening
                if is_active and not self._call_app_prev_active and self.listening_active:
                    self.pause_mic_for_call(call_app)

                # Falling edge: the call app closed and WE were the one who paused the mic
                elif not is_active and self._call_app_prev_active and self.mic_paused_for_call:
                    self.resume_mic_after_call()

                self._call_app_prev_active = is_active
            except Exception:
                pass  # Never let monitoring errors take down the thread
            time.sleep(5)

    def pause_mic_for_call(self, app_name: str):
        """Auto-pause the microphone because a call app is now running"""
        self.listening_active = False
        self.mic_paused_for_call = True
        message = f"Mic paused - {app_name} is running. Say 'mic on' if you still want me listening."
        print(f"\n{self.name}: {message}")
        self.speak(message)

    def resume_mic_after_call(self):
        """Auto-resume the microphone after the call app that paused it has closed"""
        self.mic_paused_for_call = False
        message = "Call app closed. Mic back on."
        print(f"\n{self.name}: {message}")
        self.speak(message)
        self.listening_thread = threading.Thread(target=self.continuous_listen, daemon=True)
        self.listening_thread.start()

    # ==================== PUSH-TO-TALK ====================

    def load_ptt_settings(self):
        """Load the saved push-to-talk key binding, or keep the default (numpad 0)"""
        try:
            if self.ptt_settings_file.exists():
                with open(self.ptt_settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.ptt_key_name = data.get('key_name', self.ptt_key_name)
                self.ptt_key_vk = data.get('vk')
                self.ptt_key_char = data.get('char')
        except Exception:
            pass  # Fall back to the default binding if the file is missing/corrupt

    def save_ptt_settings(self):
        """Persist the current push-to-talk key binding"""
        try:
            with open(self.ptt_settings_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'key_name': self.ptt_key_name,
                    'vk': self.ptt_key_vk,
                    'char': self.ptt_key_char,
                }, f)
        except Exception as e:
            print(f"{self.name}: Couldn't save push-to-talk settings: {e}")

    def set_ptt_key(self, key_name: str) -> str:
        """
        Change the push-to-talk binding to a new key.
        Args:
            key_name: Human-readable key name, e.g. "numpad 0", "right ctrl", "f13", "j"
        Returns: Confirmation or error message
        """
        raw = key_name.strip().lower()
        normalized = re.sub(r'^(num|numpad)\s*(\d)$', r'numpad \2', raw)  # "numpad0"/"num0" -> "numpad 0"

        if normalized in PTT_KEY_NAME_TO_VK:
            vk = PTT_KEY_NAME_TO_VK[normalized]
            self.ptt_key_name = normalized
            self.ptt_key_vk = vk
            self.ptt_key_char = None
        elif len(raw) == 1 and raw.isalnum():
            # Plain letter/digit keys are matched by character - more reliable across
            # keyboard layouts than relying on a specific vk code
            self.ptt_key_name = raw
            self.ptt_key_vk = None
            self.ptt_key_char = raw
        else:
            known = ", ".join(sorted(PTT_KEY_NAME_TO_VK.keys()))
            return f"Don't recognize '{key_name}' as a key. Try a single letter/digit, or one of: {known}"

        self.save_ptt_settings()
        self.start_push_to_talk_listener()  # restarts the key listener with the new binding

        message = f"Push-to-talk bound to [{self.ptt_key_name}]. Hold it to talk to me."
        print(f"{self.name}: {message}")
        self.speak(message)
        return message

    def _ptt_key_matches(self, key) -> bool:
        """Check whether a pynput key event matches the current push-to-talk binding"""
        if self.ptt_key_char is not None:
            return getattr(key, 'char', None) is not None and key.char.lower() == self.ptt_key_char
        return self.ptt_key_vk is not None and getattr(key, 'vk', None) == self.ptt_key_vk

    def start_push_to_talk_listener(self):
        """
        Start (or restart) the global push-to-talk key listener, and open a
        persistent mic stream that runs for the app's lifetime.

        The stream stays open continuously (audio is simply discarded while the
        key isn't held) rather than being opened fresh on every key press - opening
        a brand-new PyAudio stream has a variable warm-up delay before the audio
        callback starts flowing, which was observed to occasionally eat the entire
        capture window on a quick press. A long-lived stream avoids that per-press
        cold start entirely.
        """
        if not self.voice_available:
            return
        if self.ptt_listener:
            self.ptt_listener.stop()

        self.ptt_listener = pynput_keyboard.Listener(
            on_press=self._ptt_on_press,
            on_release=self._ptt_on_release
        )
        self.ptt_listener.daemon = True
        self.ptt_listener.start()

        if self._ptt_stream is None:
            try:
                self._ptt_pyaudio = pyaudio.PyAudio()
                self._ptt_stream = self._ptt_pyaudio.open(
                    format=pyaudio.paInt16, channels=1, rate=16000, input=True,
                    frames_per_buffer=1024, stream_callback=self._ptt_audio_callback
                )
                self._ptt_stream.start_stream()
            except Exception as e:
                print(f"{self.name}: Push-to-talk mic error: {e}")
                self._ptt_stream = None

    def _ptt_on_press(self, key):
        if self._ptt_key_matches(key) and not self.ptt_recording:
            print(f"\n{self.name}: 🎙️ Listening (push-to-talk)...")
            self._ptt_frames = []
            self.ptt_recording = True

    def _ptt_on_release(self, key):
        if self._ptt_key_matches(key) and self.ptt_recording:
            self.ptt_recording = False
            # Process off the listener thread so pynput's callback returns immediately
            threading.Thread(target=self._ptt_finish_recording, daemon=True).start()

    def _ptt_audio_callback(self, in_data, frame_count, time_info, status):
        # Stream runs continuously; only buffer audio while the key is actually held
        if self.ptt_recording:
            self._ptt_frames.append(in_data)
        return (None, pyaudio.paContinue)

    def _ptt_finish_recording(self):
        """After key release: recognize the buffered audio and process it as a command"""
        frames = self._ptt_frames
        raw_audio = b"".join(frames)
        # Ignore accidental taps (roughly < 0.2s of audio at 16kHz/16-bit mono)
        if len(raw_audio) < 6400:
            return

        audio_data = sr.AudioData(raw_audio, sample_rate=16000, sample_width=2)

        if not self.vosk_model and not self.vosk_loading_attempted:
            self.lazy_load_vosk()

        text = self.vosk_recognize(audio_data) if self.vosk_model else None
        if not text:
            try:
                text = self.recognizer.recognize_google(audio_data)
            except Exception:
                text = None

        if not text:
            return

        print(f"You (push-to-talk): {text}")
        self.process_command(text)

    # ==================== IMAGE GENERATION ====================
    # Backed by FastSD CPU (github.com/rupeshs/fastsdcpu), run as its own local
    # API server (`python src/app.py --api` from its own venv). Kept fully
    # decoupled from FreesIA's own dependencies - we just call it over localhost
    # HTTP - so its heavy ML stack (torch, openvino, diffusers) never touches
    # FreesIA's own environment.

    def load_image_gen_settings(self):
        """Load the saved image generation preferences, or keep the defaults"""
        try:
            if self.image_gen_settings_file.exists():
                with open(self.image_gen_settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.image_safety_checker = bool(data.get('image_safety_checker', self.image_safety_checker))
                self.image_model_path = str(data.get('image_model_path', self.image_model_path) or '')
                self.fastsdcpu_api_url = data.get('api_url', self.fastsdcpu_api_url)
                self.use_tiny_autoencoder = bool(data.get('use_tiny_autoencoder', self.use_tiny_autoencoder))
                self.tome_enabled = bool(data.get('tome_enabled', self.tome_enabled))
                self.tome_strength = float(data.get('tome_strength', self.tome_strength))
        except Exception:
            pass  # Fall back to defaults if the file is missing/corrupt

    def save_image_gen_settings(self):
        """Persist the image generation preferences"""
        try:
            with open(self.image_gen_settings_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'image_safety_checker': self.image_safety_checker,
                    'image_model_path': self.image_model_path,
                    'api_url': self.fastsdcpu_api_url,
                    'use_tiny_autoencoder': self.use_tiny_autoencoder,
                    'tome_enabled': self.tome_enabled,
                    'tome_strength': self.tome_strength,
                }, f)
        except Exception as e:
            print(f"{self.name}: Couldn't save image generation settings: {e}")

    def set_image_safety_checker(self, enabled: bool):
        """Toggle the safety checker for image generation (on by default)"""
        self.image_safety_checker = bool(enabled)
        self.save_image_gen_settings()

    def set_image_model_path(self, path: str):
        """Set the SDXL checkpoint used for image generation ('' = auto-detect)"""
        self.image_model_path = (path or "").strip().strip('"')
        self.save_image_gen_settings()

    def _resolve_image_model(self) -> str:
        """Configured checkpoint, else the first .safetensors in fastsdcpu/models/custom, else a public default."""
        if self.image_model_path and Path(self.image_model_path).exists():
            return self.image_model_path
        custom = Path(__file__).parent.parent / "fastsdcpu" / "models" / "custom"
        try:
            found = sorted(custom.glob("*.safetensors"))
            if found:
                return str(found[0])
        except Exception:
            pass
        return "stabilityai/sdxl-turbo"

    def set_image_speed(self, tiny_autoencoder=None, tome_enabled=None, tome_strength=None):
        """Update the optional image speed-ups and save them."""
        if tiny_autoencoder is not None:
            self.use_tiny_autoencoder = bool(tiny_autoencoder)
        if tome_enabled is not None:
            self.tome_enabled = bool(tome_enabled)
        if tome_strength is not None:
            self.tome_strength = max(0.1, min(0.7, float(tome_strength)))
        self.save_image_gen_settings()

    # ---- generated image library (gallery): prompts and stars live in one small json next to the images ----

    def _image_meta_path(self):
        return self.config_dir / "generated_images" / "image_meta.json"

    def _load_image_meta(self) -> dict:
        try:
            with open(self._image_meta_path(), 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_image_meta(self, meta: dict):
        try:
            self._image_meta_path().parent.mkdir(exist_ok=True)
            with open(self._image_meta_path(), 'w', encoding='utf-8') as f:
                json.dump(meta, f, indent=1, ensure_ascii=False)
        except Exception as e:
            print(f"{self.name}: Couldn't save image info: {e}")

    def _record_image_meta(self, filename: str, prompt: str):
        meta = self._load_image_meta()
        entry = meta.get(filename, {})
        entry["prompt"] = prompt
        meta[filename] = entry
        self._save_image_meta(meta)

    def list_generated_images(self) -> list:
        """Newest first: [{"path", "name", "mtime", "prompt", "starred"}]"""
        gen_dir = self.config_dir / "generated_images"
        if not gen_dir.exists():
            return []
        meta = self._load_image_meta()
        items = []
        for f in gen_dir.glob("*.jpg"):
            try:
                entry = meta.get(f.name, {})
                prompt = entry.get("prompt") or f.stem.split("_", 1)[-1].replace("_", " ")
                items.append({"path": f, "name": f.name, "mtime": f.stat().st_mtime,
                              "prompt": prompt, "starred": bool(entry.get("starred"))})
            except Exception:
                pass
        items.sort(key=lambda i: i["mtime"], reverse=True)
        return items

    def set_image_starred(self, path, starred: bool):
        name = Path(path).name
        meta = self._load_image_meta()
        entry = meta.get(name, {})
        entry["starred"] = bool(starred)
        meta[name] = entry
        self._save_image_meta(meta)

    def delete_generated_image(self, path) -> bool:
        """Delete one image (starred or not - the caller confirms) and forget its info."""
        try:
            Path(path).unlink()
        except FileNotFoundError:
            pass
        except Exception:
            return False
        meta = self._load_image_meta()
        if meta.pop(Path(path).name, None) is not None:
            self._save_image_meta(meta)
        if self.last_generated_image_path and Path(self.last_generated_image_path) == Path(path):
            self.last_generated_image_path = None
        return True

    def benchmark_image_speed(self, progress=None) -> list:
        """
        Time one 512x512 image with each speed-up combination. Switching settings makes FastSD CPU
        reload its model, so each combination gets an untimed warm-up run first.
        Returns [{"label", "seconds" (None if it failed), "error"}].
        """
        import time
        prompt = "a quiet lighthouse on a cliff at sunset, detailed"
        tome = max(0.1, min(0.7, self.tome_strength))
        combos = [("Normal", False, 0.0), ("TAESD", True, 0.0), ("TAESD + ToMe", True, tome)]
        results = []
        for label, taesd, tome_value in combos:
            def build():
                payload = self._base_image_gen_payload(prompt, "", 512, 512, 1)
                payload.pop("use_tiny_auto_encoder", None)
                payload.pop("token_merging", None)
                if taesd:
                    payload["use_tiny_auto_encoder"] = True
                if tome_value:
                    payload["token_merging"] = tome_value
                return payload
            entry = {"label": label, "seconds": None, "error": ""}
            try:
                for timed in (False, True):
                    if progress:
                        progress(f"{label}: {'timing' if timed else 'warming up'}...")
                    started = time.time()
                    res = self._call_fastsdcpu_once(build(), "speed test")
                    elapsed = time.time() - started
                    for pth in (res.get("paths") or []):
                        self.delete_generated_image(pth)
                    if not res.get("success"):
                        entry["error"] = str(res.get("error", "failed"))[:120]
                        break
                    if timed:
                        entry["seconds"] = elapsed
            except Exception as e:
                entry["error"] = str(e)[:120]
            results.append(entry)
        return results

    def load_chat_settings(self):
        """Load the saved chat preferences, or keep the defaults"""
        try:
            if self.chat_settings_file.exists():
                with open(self.chat_settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.personality_mode_enabled = data.get('personality_mode_enabled', self.personality_mode_enabled)
        except Exception:
            pass

    def save_chat_settings(self):
        """Persist the chat preferences"""
        try:
            with open(self.chat_settings_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'personality_mode_enabled': self.personality_mode_enabled,
                }, f)
        except Exception as e:
            print(f"{self.name}: Couldn't save chat settings: {e}")

    def set_personality_mode(self, enabled: bool):
        """Toggle between the custom persona and a plain neutral assistant (on by default)."""
        self.personality_mode_enabled = enabled
        self.save_chat_settings()

    PREFERENCE_QUESTION_PATTERNS = [
        r'\bor\b.{0,20}\?',                      # "rough or gentle?", "big or small?"
        r'\bprefer(s|red)?\b', r'\bpreference\b',
        r'\bfavou?rite\b',
        r'\bwould you rather\b', r'\bwhich (one )?do you\b',
        r'\bdo you (like|love|enjoy)\b', r'\bare you into\b',
        r'\bwhat.{0,15}\byou\b.{0,10}\blike\b',
        r'\bturns? you on\b', r'\bideal\b',
        r'\bwhat.{0,10}\btype\b', r'\bwhat.{0,10}\bkind\b',
        r'\bmatters? to you\b', r'\bdoes it matter\b',
    ]

    def _looks_like_preference_question(self, text: str) -> bool:
        """
        Heuristic detector for a direct preference/opinion question, used to
        inject a stronger anti-hedge reminder at the exact moment it's
        needed - relying on the static personality prompt alone wasn't
        reliably overriding this model's habit of giving a diplomatic
        non-answer to any preference question that touches something it
        reads as sensitive (size, ethnicity, etc.), even with matching
        few-shot examples already in the prompt. This is a keyword heuristic,
        not perfect - it can both miss real preference questions and fire on
        unrelated ones, but a false positive just adds a harmless reminder.
        """
        msg_lower = text.lower().strip()
        return any(re.search(p, msg_lower) for p in self.PREFERENCE_QUESTION_PATTERNS)

    def _get_chat_personality(self, condensed: bool = False, user_message: str = "") -> str:
        """Pick the system prompt for this response: persona or plain neutral."""
        is_preference_question = bool(user_message) and self._looks_like_preference_question(user_message)
        reminder = ""
        if is_preference_question:
            reminder = ("\n\nThe user's message is a direct preference question. Pick ONE "
                         "specific thing and say it plainly, right away - no hedge, no 'it "
                         "depends', no diplomatic non-answer, no listing multiple options, "
                         "no 'it's about the person not the trait' deflection. Commit to one "
                         "answer, the way a real person would.")

        memory_facts = self._select_relevant_memories(user_message) if user_message else []
        if memory_facts:
            reminder += ("\n\nWhat you remember about the user from past conversations:\n"
                          + "\n".join(f"- {fact}" for fact in memory_facts))

        if not self.personality_mode_enabled:
            base = ("You are a helpful, direct AI assistant. Share your own reasoned opinions "
                    "and preferences when asked instead of saying you don't have any. Pick one "
                    "specific, concrete answer - never a broad category or a hedge.")
            return base + reminder
        base = self.condensed_personality if condensed else self.personality_prompt
        return base + reminder

    # ==================== PERSONA (custom text or presets) ====================

    PERSONA_PRESETS = [
        {"name": "Soft", "blurb": "Warm and patient. Comfort first, advice second.",
         "tone": ("Warm, patient and kind. Speaks gently, uses slightly longer sentences when it matters, "
                  "and offers comfort before advice.\n"
                  "Greetings: \"Hey, I'm glad you're here.\"  Thanks: \"Anytime. Really.\"  Companionship: \"I'm right here. Take your time.\""),
         "short": "Warm, patient, gentle. Comfort first, advice second. Soft but brief sentences."},
        {"name": "Gentle", "blurb": "Calm and friendly, with a light touch.",
         "tone": ("Calm and friendly with a light touch. Short sentences that are kind rather than formal. "
                  "Reassures with few words and stays supportive.\n"
                  "Greetings: \"Hey.\"  Thanks: \"It's nothing. Glad it helped.\"  Companionship: \"I'm here if you need me.\""),
         "short": "Calm, friendly, kind. Short sentences. Reassure with few words."},
        {"name": "Balanced", "blurb": "Direct and practical, with a dry sense of humor.",
         "tone": ("Direct and practical with a dry sense of humor. Neither overly warm nor cold. Clear answers, light sarcasm, "
                  "no flattery and no lectures.\n"
                  "Greetings: \"Hey.\"  Thanks: \"Sure.\"  Companionship: \"I'm around.\""),
         "short": "Direct, practical, dry humor. Clear answers, no flattery, no lectures."},
        {"name": "Blunt", "blurb": "Short sentences, little small talk, gets to the point.",
         "tone": ("Blunt and direct. Short sentences, minimal words, no unnecessary politeness. "
                  "Shows care by being reliable rather than by talking about it.\n"
                  "Greetings: \"Yeah?\"  Thanks: \"It's fine.\"  Companionship: \"I'm here.\""),
         "short": "Blunt and direct. Short sentences. No unnecessary politeness. Reliable."},
        {"name": "Cold", "blurb": "Clipped and detached. Answers only what was asked.",
         "tone": ("Clipped, detached and efficient. Answers exactly what was asked and nothing more, offers no reassurance, "
                  "and treats small talk as a waste of time.\n"
                  "Greetings: \"What.\"  Thanks: \"Noted.\"  Companionship: \"I'm not going anywhere.\""),
         "short": "Cold, clipped, detached. Answer only what was asked. No reassurance, no small talk."},
    ]

    _PERSONA_RULES = (
        "Rules:\n"
        "- Asked for an opinion or preference: answer directly in your own voice, never \"I don't have preferences\". "
        "Pick ONE specific concrete thing, never a broad category or a hedge.\n"
        "- Never claim to be human. For technical questions, answer clearly first and keep the attitude second.\n"
        "- Stay in character. Keep replies brief unless detail is requested."
    )

    def _preset_prompt(self, index: int, short: bool = False) -> str:
        p = self.PERSONA_PRESETS[max(0, min(len(self.PERSONA_PRESETS) - 1, int(index)))]
        if short:
            return f"You are {self.assistant_name}.\n\n{p['short']}\n\nKey: Stay in character. Stay brief."
        return (f"You are {self.assistant_name}, a personal assistant on the user's PC. "
                f"You can run system commands and answer questions.\n\nPersonality ({p['name']}): {p['tone']}\n\n{self._PERSONA_RULES}")

    def _custom_personality_path(self):
        return Path(__file__).parent / "Personality.txt"

    def read_custom_personality(self) -> str:
        try:
            path = self._custom_personality_path()
            if path.exists():
                return path.read_text(encoding='utf-8').strip()
        except Exception as e:
            print(f"{self.name}: Couldn't read Personality.txt: {e}")
        return ""

    def load_persona_settings(self):
        import hashlib
        try:
            if self.persona_settings_file.exists():
                with open(self.persona_settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.persona_source = data.get('source', self.persona_source) if data.get('source') in ('custom', 'preset') else 'custom'
                self.persona_preset = max(0, min(len(self.PERSONA_PRESETS) - 1, int(data.get('preset', self.persona_preset))))
                self._persona_original_hash = data.get('original_hash')
                self.assistant_name = (str(data.get('assistant_name', self.assistant_name)).strip() or self.assistant_name)[:40]
        except Exception:
            pass
        if not self._persona_original_hash:
            # Remember what the user's file looked like before this app ever edited it, so an untouched file keeps the
            # hand-tuned short version of the personality used for quick replies.
            text = self.read_custom_personality()
            if text:
                self._persona_original_hash = hashlib.sha1(text.encode('utf-8')).hexdigest()
                self.save_persona_settings()

    def save_persona_settings(self):
        try:
            with open(self.persona_settings_file, 'w', encoding='utf-8') as f:
                json.dump({'source': self.persona_source, 'preset': self.persona_preset,
                           'original_hash': self._persona_original_hash,
                           'assistant_name': self.assistant_name}, f)
        except Exception as e:
            print(f"{self.name}: Couldn't save persona settings: {e}")

    def _condense_custom(self, text: str) -> str:
        """Quick-reply version of the user's own text: the original hand-tuned one while the file is untouched,
        otherwise the start of their text, cut at a paragraph boundary."""
        import hashlib
        if not text:
            return self._default_condensed
        if self._persona_original_hash and hashlib.sha1(text.encode('utf-8')).hexdigest() == self._persona_original_hash \
                and self._default_condensed:
            return self._default_condensed
        limit = 1800
        if len(text) <= limit:
            return text
        out = ""
        for para in text.split("\n\n"):
            if out and len(out) + len(para) > limit:
                break
            out += ("\n\n" if out else "") + para
        return out[:limit].rstrip() + "\n\nStay in character. Stay brief."

    def _with_name(self, text: str) -> str:
        """Tell the model its name unless the user's own text already uses it."""
        if not text or self.assistant_name.lower() in text.lower():
            return text
        return f"Your name is {self.assistant_name}.\n\n{text}"

    def _default_personality(self) -> str:
        return (f"You are {self.assistant_name}, a helpful, efficient and direct assistant on the user's Windows PC. "
                "You can run system commands and answer questions. Keep replies concise unless detail is requested.")

    def apply_persona(self):
        """Set the full and quick-reply personality prompts from the chosen source."""
        if self.persona_source == "preset":
            self.personality_prompt = self._preset_prompt(self.persona_preset)
            self.condensed_personality = self._preset_prompt(self.persona_preset, short=True)
            return
        text = self.read_custom_personality()
        if text:
            self.personality_prompt = self._with_name(text)
        else:
            self.personality_prompt = self._default_personality()
        self.condensed_personality = self._with_name(self._condense_custom(text)) if text else self._default_condensed

    def set_assistant_name(self, name: str):
        """Rename the assistant (what it calls itself in prompts and chat labels)."""
        name = re.sub(r"[\r\n:]+", " ", str(name or "")).strip()[:40]
        if not name:
            name = "FreesIA"
        self.assistant_name = name
        self.save_persona_settings()
        self.apply_persona()
        self.clear_ai_history()

    def get_persona_info(self) -> dict:
        return {"name": self.assistant_name, "source": self.persona_source, "preset": self.persona_preset, "custom_text": self.read_custom_personality(),
                "presets": [{"name": p["name"], "blurb": p["blurb"]} for p in self.PERSONA_PRESETS]}

    def set_persona(self, source=None, preset=None):
        """Switch between the user's own text and the presets (or pick a preset). Resets the short-term context."""
        if source in ("custom", "preset"):
            self.persona_source = source
        if preset is not None:
            self.persona_preset = max(0, min(len(self.PERSONA_PRESETS) - 1, int(preset)))
        self.save_persona_settings()
        self.apply_persona()
        self.clear_ai_history()

    def save_custom_personality(self, text: str) -> bool:
        """Write the user's own personality text to Personality.txt (backing the old file up once)."""
        try:
            path = self._custom_personality_path()
            backup = path.with_name("Personality_before_app_edit.txt")
            if path.exists() and not backup.exists():
                backup.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')
            path.write_text(text.strip() + "\n", encoding='utf-8')
        except Exception as e:
            print(f"{self.name}: Couldn't save Personality.txt: {e}")
            return False
        if self.persona_source == "custom":
            self.apply_persona()
            self.clear_ai_history()
        return True

    DODGE_RETRY_NUDGE = (
        "\n\nYour previous answer to this hedged instead of actually answering - it didn't "
        "commit to anything specific. Try again: pick ONE real, specific answer of your own "
        "and say it plainly. Don't guess what the user wants to hear - just don't dodge the "
        "question this time."
    )

    def load_memory_bank(self) -> list:
        """Load the persisted list of learned facts about the user, {"fact", "timestamp"} each."""
        if not self.memory_bank_file.exists():
            return []
        try:
            with open(self.memory_bank_file, 'r', encoding='utf-8') as f:
                return json.load(f).get('memories', [])
        except Exception:
            return []

    def save_memory_bank(self):
        try:
            with open(self.memory_bank_file, 'w', encoding='utf-8') as f:
                json.dump({'memories': self.memory_bank}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"{self.name}: Couldn't save memory bank: {e}")

    def clear_memory_bank(self):
        self.memory_bank = []
        self.save_memory_bank()

    # ==================== PINNED MESSAGES ====================
    # Shared between the live chat and the Chat Reader (imported chat
    # archives) - one store, one "Pinned" view regardless of where a
    # message came from.

    def load_pinned_messages(self) -> list:
        """Each entry: {id, content, speaker, source, chat_id, timestamp}."""
        if not self.pinned_messages_file.exists():
            return []
        try:
            with open(self.pinned_messages_file, 'r', encoding='utf-8') as f:
                return json.load(f).get('pins', [])
        except Exception:
            return []

    def save_pinned_messages(self):
        try:
            with open(self.pinned_messages_file, 'w', encoding='utf-8') as f:
                json.dump({'pins': self.pinned_messages}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"{self.name}: Couldn't save pinned messages: {e}")

    def pin_message(self, content: str, speaker: str, source: str, chat_id: str = "",
                     timestamp: str = "") -> dict:
        """
        source: "live_chat" for a regular conversation, or
        "chat_reader:<archive name>" for an imported chat archive - lets the
        Pinned view show/jump back to the right place regardless of origin.
        """
        import uuid
        from datetime import datetime
        pin = {
            'id': str(uuid.uuid4()),
            'content': content,
            'speaker': speaker,
            'source': source,
            'chat_id': chat_id,
            'timestamp': timestamp or datetime.now().isoformat(),
            'pinned_at': datetime.now().isoformat(),
        }
        self.pinned_messages.append(pin)
        self.save_pinned_messages()
        return pin

    def unpin_message(self, pin_id: str):
        self.pinned_messages = [p for p in self.pinned_messages if p['id'] != pin_id]
        self.save_pinned_messages()

    def find_pin_id(self, chat_id: str, content: str, speaker: str) -> str | None:
        """Used when reopening a saved chat, to correctly restore each bubble's pinned indicator."""
        for p in self.pinned_messages:
            if p.get('chat_id') == chat_id and p.get('content') == content and p.get('speaker') == speaker:
                return p['id']
        return None

    # ==================== CHAT READER ====================
    # Import chat exports (currently: Character.AI) and browse them in the
    # app's own bubble UI. Each archive is stored as one JSON chunk per
    # month under ~/.freesia/chat_reader/<archive_name>/ so the GUI can load
    # a manageable window of messages instead of an entire multi-year chat
    # at once.

    _NAME_PREFIX_RE = None  # set lazily in _classify_cai_speaker (avoids import at module load)

    def _classify_cai_speaker(self, content: str, known_names: list, user_name: str) -> str:
        """
        Character.AI's export has no sender field - infer it from writing
        convention instead: character messages use "*asterisk narration*"
        and/or "Name: dialogue" prefixes (roleplay style), the user's own
        messages are plain text. See scheduler_ab_test.py-era investigation
        notes for how this was validated against real exported chats.
        """
        if self._NAME_PREFIX_RE is None:
            import re
            self.__class__._NAME_PREFIX_RE = re.compile(r"^([A-Za-z0-9 ]{1,20}):\s*")
        stripped = content.strip()
        m = self._NAME_PREFIX_RE.match(stripped)
        if m and m.group(1).strip() in known_names:
            return m.group(1).strip()
        if stripped.startswith("*"):
            for name in known_names:
                if name in stripped[:200]:
                    return name
            return known_names[0] if len(known_names) == 1 else (known_names[0] if known_names else "Character")
        return user_name

    def _detect_character_names(self, msgs: list) -> list:
        """
        Auto-detect character name(s) for a chat by scanning for frequent
        "Name: dialogue" prefixes - the roleplay convention Character.AI
        messages use - instead of requiring the user to type exact names
        manually. character.json isn't reliable for this: it lists every
        character the account has ever talked to, combined titles like
        "Alice and Bob" instead of the two separate in-chat names, and has no
        chat_id link back to a specific conversation.

        Two things learned the hard way testing this against real exports:
        - The prefix often isn't at the very start of the message (an
          opening *narration* paragraph comes first), so this scans every
          line, not just position 0.
        - A character name can start with a digit (e.g. "7Up"), so the
          pattern can't require a leading letter.
        Scans the whole chat rather than a sample - main characters
        (thousands of occurrences) separate cleanly from incidental NPC
        names (dozens) once the full picture is visible; a small early
        sample can miss a main character whose dialogue happens to lean on
        asterisk-narration without a name tag in that window.
        """
        prefix_re = re.compile(r"(?:^|\n)([A-Za-z0-9][A-Za-z0-9 ]{0,19}):\s", re.MULTILINE)
        counts = {}
        for m in msgs:
            for name in prefix_re.findall(m['raw_content']):
                name = name.strip()
                counts[name] = counts.get(name, 0) + 1
        if not counts:
            return []
        top_count = max(counts.values())
        # A real recurring character clears both an absolute floor (filters
        # pure one-off noise) and a chunk of the top speaker's frequency
        # (separates main characters from incidental NPC mentions, which
        # trail off by 1-2 orders of magnitude in every export tested).
        threshold = max(5, top_count * 0.03)
        detected = [name for name, c in counts.items() if c >= threshold]
        detected.sort(key=lambda n: counts[n], reverse=True)
        return detected[:5]

    def inspect_character_ai_export(self, export_data_dir) -> dict:
        """
        Look at a Character.AI export's data/ folder (containing message.json
        and character.json) and list the chats worth importing - anything
        with more than a handful of messages. Character.AI accumulates a lot
        of single-message stray chats (accidentally started, never continued)
        that aren't real conversations, so those are filtered out.
        Returns: {"success": True, "chats": [{"chat_id", "count", "first_time",
                  "last_time", "sample_content", "detected_names"}],
                  "character_names": [...]}
              or {"success": False, "error": str}
        """
        export_data_dir = Path(export_data_dir)
        message_path = export_data_dir / "message.json"
        character_path = export_data_dir / "character.json"
        if not message_path.exists():
            return {"success": False, "error": f"No message.json found in {export_data_dir}"}

        try:
            with open(message_path, 'r', encoding='utf-8') as f:
                messages = json.load(f)
        except Exception as e:
            return {"success": False, "error": f"Couldn't read message.json: {e}"}

        character_names = []
        if character_path.exists():
            try:
                with open(character_path, 'r', encoding='utf-8') as f:
                    chars = json.load(f)
                character_names = [c.get('name', '') for c in chars if c.get('name')]
            except Exception:
                pass

        from collections import defaultdict
        by_chat = defaultdict(list)
        for m in messages:
            by_chat[m['chat_id']].append(m)

        chats = []
        for chat_id, msgs in by_chat.items():
            if len(msgs) < 10:
                continue
            msgs.sort(key=lambda m: m['create_time'])
            chats.append({
                "chat_id": chat_id,
                "count": len(msgs),
                "first_time": msgs[0]['create_time'],
                "last_time": msgs[-1]['create_time'],
                "sample_content": msgs[0]['raw_content'][:150],
                "detected_names": self._detect_character_names(msgs),
            })
        chats.sort(key=lambda c: c['count'], reverse=True)

        return {"success": True, "chats": chats, "character_names": character_names}

    def import_character_ai_chat(self, export_data_dir, chat_id: str, archive_name: str,
                                  display_name: str, character_names: list) -> dict:
        """
        Parse one chat_id out of a Character.AI export into this app's Chat
        Reader format: one JSON chunk per month under
        ~/.freesia/chat_reader/<archive_name>/, plus a manifest.
        archive_name should be filesystem-safe (caller's responsibility -
        the GUI derives it from display_name via re.sub).
        """
        export_data_dir = Path(export_data_dir)
        try:
            with open(export_data_dir / "message.json", 'r', encoding='utf-8') as f:
                all_messages = json.load(f)
        except Exception as e:
            return {"success": False, "error": f"Couldn't read message.json: {e}"}

        msgs = [m for m in all_messages if m['chat_id'] == chat_id]
        if not msgs:
            return {"success": False, "error": f"No messages found for chat_id {chat_id}"}
        msgs.sort(key=lambda m: m['create_time'])

        from collections import defaultdict
        by_month = defaultdict(list)
        for m in msgs:
            month_key = m['create_time'][:7]
            speaker = self._classify_cai_speaker(m['raw_content'], character_names, "You")
            by_month[month_key].append({
                "speaker": speaker,
                "content": m['raw_content'],
                "timestamp": m['create_time'],
            })

        archive_dir = self.chat_reader_dir / archive_name
        archive_dir.mkdir(exist_ok=True)
        months = sorted(by_month.keys())
        for month_key in months:
            with open(archive_dir / f"{month_key}.json", 'w', encoding='utf-8') as f:
                json.dump(by_month[month_key], f, ensure_ascii=False)

        manifest = {
            "archive_name": archive_name,
            "display_name": display_name,
            "source": "character_ai",
            "character_names": character_names,
            "message_count": len(msgs),
            "months": months,
            "date_range": [msgs[0]['create_time'], msgs[-1]['create_time']],
        }
        with open(archive_dir / "manifest.json", 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        self._update_chat_reader_index(manifest)
        return {"success": True, "manifest": manifest}

    def _update_chat_reader_index(self, manifest: dict):
        index_path = self.chat_reader_dir / "index.json"
        index = []
        if index_path.exists():
            try:
                with open(index_path, 'r', encoding='utf-8') as f:
                    index = json.load(f)
            except Exception:
                index = []
        index = [a for a in index if a['archive_name'] != manifest['archive_name']]
        index.append({
            "archive_name": manifest['archive_name'],
            "display_name": manifest['display_name'],
            "message_count": manifest['message_count'],
            "date_range": manifest['date_range'],
        })
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=2, ensure_ascii=False)

    def list_chat_reader_archives(self) -> list:
        index_path = self.chat_reader_dir / "index.json"
        if not index_path.exists():
            return []
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def get_chat_reader_manifest(self, archive_name: str) -> dict | None:
        manifest_path = self.chat_reader_dir / archive_name / "manifest.json"
        if not manifest_path.exists():
            return None
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    def load_chat_reader_month(self, archive_name: str, month_key: str) -> list:
        month_path = self.chat_reader_dir / archive_name / f"{month_key}.json"
        if not month_path.exists():
            return []
        try:
            with open(month_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def reassign_chat_reader_speaker(self, archive_name: str, month_key: str, msg_index: int, new_speaker: str) -> bool:
        month_path = self.chat_reader_dir / archive_name / f"{month_key}.json"
        try:
            with open(month_path, 'r', encoding='utf-8') as f:
                msgs = json.load(f)
            if not (0 <= msg_index < len(msgs)):
                return False
            msgs[msg_index]['speaker'] = new_speaker
            with open(month_path, 'w', encoding='utf-8') as f:
                json.dump(msgs, f, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"{self.name}: Couldn't reassign speaker: {e}")
            return False

    def search_chat_reader(self, archive_name: str, query: str, limit: int = 200) -> list:
        """
        Plain substring search (case-insensitive) across every month of an
        archive. Simple, but the per-month chunking keeps each file small
        enough that scanning all of them is fast even for a 2-year chat.
        Returns: [{"month", "index", "speaker", "content", "timestamp"}, ...]
        """
        manifest = self.get_chat_reader_manifest(archive_name)
        if not manifest:
            return []
        query_lower = query.lower()
        results = []
        for month_key in manifest['months']:
            msgs = self.load_chat_reader_month(archive_name, month_key)
            for i, m in enumerate(msgs):
                if query_lower in m['content'].lower():
                    results.append({
                        "month": month_key,
                        "index": i,
                        "speaker": m['speaker'],
                        "content": m['content'],
                        "timestamp": m['timestamp'],
                    })
                    if len(results) >= limit:
                        return results
        return results

    def rename_chat_reader_archive(self, archive_name: str, new_display_name: str) -> bool:
        """Change only the display name of an imported archive (files and archive_name stay put)."""
        new_display_name = (new_display_name or "").strip()
        if not new_display_name or archive_name != Path(archive_name).name:
            return False
        manifest = self.get_chat_reader_manifest(archive_name)
        if not manifest:
            return False
        try:
            manifest["display_name"] = new_display_name
            with open(self.chat_reader_dir / archive_name / "manifest.json", 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
            self._update_chat_reader_index(manifest)
            return True
        except Exception as e:
            print(f"{self.name}: Couldn't rename archive: {e}")
            return False

    def delete_chat_reader_archive(self, archive_name: str) -> bool:
        """Remove an imported archive (its monthly files, index entry and bookmarks). The original export is untouched."""
        if not archive_name or archive_name != Path(archive_name).name:
            return False
        import shutil
        try:
            shutil.rmtree(self.chat_reader_dir / archive_name, ignore_errors=True)
            index_path = self.chat_reader_dir / "index.json"
            if index_path.exists():
                with open(index_path, 'r', encoding='utf-8') as f:
                    index = json.load(f)
                index = [a for a in index if a.get('archive_name') != archive_name]
                with open(index_path, 'w', encoding='utf-8') as f:
                    json.dump(index, f, indent=2, ensure_ascii=False)
            self.pinned_messages = [p for p in self.pinned_messages if p.get('source') != f"chat_reader:{archive_name}"]
            self.save_pinned_messages()
            return True
        except Exception as e:
            print(f"{self.name}: Couldn't delete archive: {e}")
            return False

    def extract_memory_fact(self, user_message: str, ai_response: str):
        """
        Ask the fast model whether this exchange contains a durable fact worth
        remembering across future chats (name, preference, allergy, ongoing
        project, relationship...) - not every message, just things a person
        would actually remember about someone. Returns the fact as a short
        sentence, or None if there's nothing worth keeping.
        """
        import ollama
        extraction_prompt = (
            "Given this single exchange, is there one specific, durable fact worth "
            "remembering about the user for future conversations - something like their "
            "name, a preference, an allergy, an ongoing project, a relationship, a fact "
            "about their life? This is a high bar: almost every exchange has NOTHING worth "
            "remembering. Don't invent a fact just because the user asked a question - "
            "asking about the weather doesn't mean anything is worth noting; ordinary "
            "requests, small talk, and one-off questions are NEVER worth remembering, even "
            "if you can technically phrase something about them as a 'fact'.\n\n"
            "If there's nothing worth remembering, respond with exactly: NONE\n"
            "If there genuinely is, respond with ONLY the fact itself, one short sentence, "
            "third person ('user is...', 'user likes...', \"user's dog is named...\") - no "
            "preamble, no explanation, no quotes.\n\n"
            "User: what's the weather like today\n"
            "Assistant: Sunny and 75.\n"
            "-> NONE\n\n"
            "User: can you open notepad\n"
            "Assistant: Opening notepad.\n"
            "-> NONE\n\n"
            "User: I'm allergic to peanuts by the way\n"
            "Assistant: Got it, noted.\n"
            "-> user is allergic to peanuts\n\n"
            "User: my dog is named Biscuit\n"
            "Assistant: Cute name.\n"
            "-> user's dog is named Biscuit"
        )
        try:
            # Uses the more capable model, not the fast one - this runs off
            # the UI thread and doesn't block anything, so the extra latency
            # is a good trade for reliably judging NONE vs a real fact (the
            # fast 3B model kept inventing unwarranted "facts" like "user is
            # good at math" from someone asking what 2+2 is).
            resp = ollama.chat(
                model=self.ollama_model,
                messages=[
                    {'role': 'system', 'content': extraction_prompt},
                    {'role': 'user', 'content': f"User: {user_message}\nAssistant: {ai_response[:400]}"}
                ],
                options={'temperature': 0.3, 'num_predict': 60},
                keep_alive="2h",
            )
            fact = resp['message']['content'].strip().strip('"\'')
            if not fact or fact.upper().startswith("NONE"):
                return None
            return fact
        except Exception:
            return None

    def maybe_remember(self, user_message: str, ai_response: str):
        """Extract and store a fact from this exchange, if there's a genuine one - de-duped."""
        fact = self.extract_memory_fact(user_message, ai_response)
        if not fact:
            return
        fact_lower = fact.lower()
        for existing in self.memory_bank:
            if existing.get('fact', '').lower() == fact_lower:
                return
        from datetime import datetime
        self.memory_bank.append({'fact': fact, 'timestamp': datetime.now().isoformat()})
        self.save_memory_bank()

    def _select_relevant_memories(self, user_message: str, count: int = 4) -> list:
        """
        Pick facts relevant to the current message (keyword overlap), plus
        always include a couple of the most recent facts regardless of topic
        match - recency matters for memory ("what did I just tell you") even
        when it's not keyword-related to what's being asked right now.
        """
        if not self.memory_bank:
            return []
        msg_words = set(re.findall(r'\w+', user_message.lower()))
        scored = []
        for mem in self.memory_bank:
            fact_words = set(re.findall(r'\w+', mem.get('fact', '').lower()))
            scored.append((len(msg_words & fact_words), mem.get('fact', '')))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        matched = [f for score, f in scored if score > 0][:count]
        recent = [m.get('fact', '') for m in self.memory_bank[-count:]]
        combined = []
        for f in matched + recent:
            if f and f not in combined:
                combined.append(f)
        return combined[:count]

    IMAGE_SIZES = {
        "square": (512, 512),      # 1:1
        "landscape": (896, 512),   # 16:9 (close: 1.75 vs 1.778)
        "portrait": (512, 896),    # 9:16
    }

    # Always applied for general quality/artifact cleanup - free, doesn't
    # cost any generation time. Targets the common CPU/low-step failure
    # modes (muddy backgrounds, bad anatomy, watermarks/text baked in).
    DEFAULT_NEGATIVE_PROMPT = (
        "blurry, low quality, low resolution, worst quality, jpeg artifacts, "
        "distorted, deformed, disfigured, bad anatomy, extra limbs, extra fingers, "
        "mutated hands, poorly drawn face, watermark, text, signature, logo, "
        "oversaturated, out of frame, cropped, duplicate"
    )

    def _resolve_image_size(self, size: str) -> tuple:
        return self.IMAGE_SIZES.get(size, self.IMAGE_SIZES["square"])

    def _infer_size_name(self, width: int, height: int) -> str:
        """Reverse lookup: map actual pixel dimensions back to a size name (for regenerate)."""
        for name, (w, h) in self.IMAGE_SIZES.items():
            if w == width and h == height:
                return name
        return "square"

    def _parse_image_gen_options(self, prompt: str) -> tuple:
        """
        Pull size/count/negative-prompt hints out of a natural-language image
        request. Doesn't touch size/count wording in the prompt itself (it's
        harmless/reinforcing to leave in), but does strip a trailing
        "without X" clause since that's meant as an instruction, not content
        to depict.
        Returns: (cleaned_prompt, size, count, negative_prompt)
        """
        text_lower = prompt.lower()

        size = "square"
        if any(w in text_lower for w in ("landscape", "horizontal", "wide")):
            size = "landscape"
        elif any(w in text_lower for w in ("portrait", "vertical", "tall")):
            size = "portrait"

        count = 1
        count_match = re.search(r'\b(\d+)\s*(images?|pictures?|photos?|pics?|variations?|options?)\b', text_lower)
        if count_match:
            count = max(1, min(int(count_match.group(1)), 4))

        negative_prompt = ""
        neg_match = re.search(r',?\s*(?:but\s+)?without\s+(.+)$', prompt, re.IGNORECASE)
        if neg_match:
            negative_prompt = neg_match.group(1).strip()
            prompt = prompt[:neg_match.start()].strip(' ,')

        return prompt, size, count, negative_prompt

    def _base_image_gen_payload(self, prompt: str, negative_prompt: str = "",
                                 image_width: int = 512, image_height: int = 512,
                                 number_of_images: int = 1) -> dict:
        """
        Shared request payload for both fresh generation and image editing.
        Uses a standalone SDXL checkpoint (ideally a speed-distilled
        "Lightning"/"Turbo" one, ~4 steps, CFG 1-2). Set the path in
        Settings, or drop a .safetensors file into fastsdcpu/models/custom
        and it is picked up automatically.
        Runs on plain PyTorch (no OpenVINO acceleration for a single-file
        checkpoint).
        """
        model_path = self._resolve_image_model()
        # Always-on baseline negative prompt for general quality/artifact
        # cleanup (backgrounds especially) - free, doesn't cost any
        # generation time. Merged with any user-specified "without X" negative
        # prompt rather than replacing it.
        combined_negative = self.DEFAULT_NEGATIVE_PROMPT
        if negative_prompt:
            combined_negative = f"{negative_prompt}, {combined_negative}"
        payload = {
            "prompt": prompt,
            "negative_prompt": combined_negative,
            "use_openvino": False,
            # RealVisXL Lightning is already a fully-merged speed-distilled
            # checkpoint - it's meant to run standalone. Stacking the generic
            # lcm-lora-sdxl LoRA on top of it (the old approach) double-distills
            # the same thing and actively hurts detail/quality rather than
            # helping speed - the checkpoint's own card recommends running it
            # plain at ~5 steps, CFG 1.0-2.0, no LoRA.
            "use_lcm_lora": False,
            "lcm_model_id": str(model_path),
            "use_safety_checker": self.image_safety_checker,
            "image_width": image_width,
            "image_height": image_height,
            "number_of_images": number_of_images,
            "inference_steps": 4,  # typical for Lightning-style checkpoints
            "guidance_scale": 1.8,  # typical CFG range 1-2
            "use_seed": False,  # random seed each call, so "regenerate" gives a fresh variation
        }
        if self.use_tiny_autoencoder:
            payload["use_tiny_auto_encoder"] = True
        if self.tome_enabled:
            payload["token_merging"] = max(0.1, min(0.7, self.tome_strength))
        return payload

    def _is_fastsdcpu_up(self, req, timeout: float = 2.0) -> bool:
        try:
            req.get(f"{self.fastsdcpu_api_url}/api/", timeout=timeout)
            return True
        except Exception:
            return False

    def _ensure_fastsdcpu_running(self, req, startup_timeout: float = 240.0) -> bool:
        """
        Launch FastSD CPU's API server in the background if it isn't already
        up, then poll until it responds or startup_timeout runs out. Cold
        start is slow even before any model loading happens - importing
        torch/optimum alone measured ~90-150s on this machine - so the
        timeout has headroom for that plus real generation-time loading.
        Only spawns one process per FreesIA session - callers that already
        have a handle just keep polling that one instead of launching
        duplicates, and a process that's still warming up from a previous
        attempt is picked up here rather than relaunched.
        """
        if self._is_fastsdcpu_up(req):
            return True

        if self._fastsdcpu_process is None or self._fastsdcpu_process.poll() is not None:
            venv_python = self.fastsdcpu_dir / "env" / "Scripts" / "python.exe"
            python_cmd = str(venv_python) if venv_python.exists() else sys.executable
            try:
                self._fastsdcpu_process = subprocess.Popen(
                    [python_cmd, str(self.fastsdcpu_dir / "src" / "app.py"), "--api"],
                    cwd=str(self.fastsdcpu_dir),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except Exception as e:
                print(f"{self.name}: Couldn't auto-launch FastSD CPU: {e}")
                return False

        deadline = time.time() + startup_timeout
        while time.time() < deadline:
            if self._is_fastsdcpu_up(req):
                return True
            time.sleep(2)
        return False

    def _call_fastsdcpu(self, payload: dict, prompt: str) -> dict:
        """Same as _call_fastsdcpu_once, but if a speed-up option makes the request fail, retry once without it."""
        result = self._call_fastsdcpu_once(payload, prompt)
        if not result.get("success") and ("use_tiny_auto_encoder" in payload or "token_merging" in payload):
            plain = {k: v for k, v in payload.items() if k not in ("use_tiny_auto_encoder", "token_merging")}
            retry = self._call_fastsdcpu_once(plain, prompt)
            if retry.get("success"):
                print(f"{self.name}: image speed-ups failed ({result.get('error')}); generated without them.")
                return retry
        return result

    def _call_fastsdcpu_once(self, payload: dict, prompt: str) -> dict:
        """
        POST to the FastSD CPU API, decode the result(s), and save to disk.
        Returns: {"success": True, "path": Path, "paths": [Path, ...], "prompt": str}
              or {"success": False, "error": str}
        "path" is always the first image, kept for callers that only ever
        expect one; "paths" holds all of them (length 1 unless the request
        asked for more).
        """
        import requests as req
        import base64
        import time

        try:
            resp = req.post(f"{self.fastsdcpu_api_url}/api/generate", json=payload, timeout=420)
            resp.raise_for_status()
            data = resp.json()
        except req.exceptions.ConnectionError:
            # Not running - try to auto-start it (loading the checkpoint can
            # take a minute or two) and retry once before giving up.
            if self._ensure_fastsdcpu_running(req):
                try:
                    resp = req.post(f"{self.fastsdcpu_api_url}/api/generate", json=payload, timeout=420)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    return {"success": False, "error": f"FastSD CPU started but the request failed: {e}"}
            else:
                return {"success": False, "error": "FastSD CPU couldn't be started automatically. Start its "
                                                     "API server manually (python src/app.py --api from the "
                                                     "fastsdcpu folder)."}
        except Exception as e:
            return {"success": False, "error": str(e)}

        if data.get("error"):
            return {"success": False, "error": data["error"]}

        images = data.get("images", [])
        if not images:
            return {"success": False, "error": "No image was returned."}

        try:
            gen_dir = self.config_dir / "generated_images"
            gen_dir.mkdir(exist_ok=True)
            safe_name = re.sub(r'[^a-zA-Z0-9]+', '_', prompt).strip('_')[:40] or "image"
            file_paths = []
            for i, img_b64 in enumerate(images):
                image_bytes = base64.b64decode(img_b64)
                suffix = f"_{i+1}" if len(images) > 1 else ""
                file_path = gen_dir / f"{int(time.time())}_{safe_name}{suffix}.jpg"
                with open(file_path, 'wb') as f:
                    f.write(image_bytes)
                self._record_image_meta(file_path.name, prompt)
                file_paths.append(file_path)
            self.last_generated_image_path = file_paths[0]
            self.last_image_gen_time = time.time()
            return {"success": True, "path": file_paths[0], "paths": file_paths, "prompt": prompt}
        except Exception as e:
            return {"success": False, "error": f"Generated but couldn't save it: {e}"}

    def delete_all_generated_images(self) -> int:
        """Bulk-delete every generated image on disk except starred ones. Returns how many were removed."""
        gen_dir = self.config_dir / "generated_images"
        if not gen_dir.exists():
            return 0
        count = 0
        meta = self._load_image_meta()
        for f in gen_dir.glob("*.jpg"):
            if meta.get(f.name, {}).get("starred"):
                continue  # starred images are kept
            try:
                f.unlink()
                meta.pop(f.name, None)
                count += 1
            except Exception:
                pass
        self._save_image_meta(meta)
        if self.last_generated_image_path and not Path(self.last_generated_image_path).exists():
            self.last_generated_image_path = None
        return count

    def generate_image(self, prompt: str, size: str = "square", count: int = 1, negative_prompt: str = "") -> dict:
        """Generate a fresh image via a locally-running FastSD CPU API server."""
        width, height = self._resolve_image_size(size)
        payload = self._base_image_gen_payload(prompt, negative_prompt, width, height, count)
        result = self._call_fastsdcpu(payload, prompt)
        if not result.get("success"):
            return result
        return self._apply_hires_fix(result, prompt, width, height)

    def _apply_hires_fix(self, result: dict, prompt: str, base_width: int, base_height: int) -> dict:
        """
        Second short img2img pass on each freshly generated image, per
        the usual Lightning-checkpoint recommendation (~2 effective
        steps, denoise strength ~0.4, 1.4x upscale) - resolves detail a
        single low-step pass leaves muddy, especially backgrounds. Best-effort:
        any image that fails this second pass keeps its first-pass result
        rather than losing what the user already has.
        """
        import base64

        hi_width = max(64, round(base_width * 1.4 / 64) * 64)
        hi_height = max(64, round(base_height * 1.4 / 64) * 64)
        refined_paths = []
        for path in result["paths"]:
            try:
                with open(path, 'rb') as f:
                    init_b64 = base64.b64encode(f.read()).decode('utf-8')
                hi_payload = self._base_image_gen_payload(prompt, "", hi_width, hi_height, 1)
                hi_payload["diffusion_task"] = "image_to_image"
                hi_payload["init_image"] = init_b64
                hi_payload["strength"] = 0.4
                hi_payload["inference_steps"] = 5  # ~2 effective steps at strength 0.4
                hi_result = self._call_fastsdcpu(hi_payload, prompt)
                if hi_result.get("success"):
                    refined_paths.append(hi_result["paths"][0])
                    try:
                        Path(path).unlink()  # drop the superseded first-pass file
                    except Exception:
                        pass
                else:
                    refined_paths.append(path)
            except Exception:
                refined_paths.append(path)

        result["paths"] = refined_paths
        result["path"] = refined_paths[0]
        self.last_generated_image_path = refined_paths[0]
        return result

    def _prepare_edit_image(self, source_image_path) -> tuple:
        """
        Downscale a source/uploaded image to our generation resolution budget
        before sending it for editing. Uncapped, an uploaded phone photo
        (e.g. 3024x4032) would run image-to-image at that full resolution on
        CPU - drastically slower than our normal 512-896px generations, easily
        exceeding the request timeout instead of just taking a while longer.
        Returns (base64_jpeg_str, width, height) - width/height always
        multiples of 64 (required for stable diffusion) and capped to the
        same max side as our largest configured generation size.
        """
        from PIL import Image
        import base64
        import io

        max_side = max(w for w, h in self.IMAGE_SIZES.values())
        with Image.open(source_image_path) as img:
            img = img.convert("RGB")
            width, height = img.size
            scale = min(1.0, max_side / max(width, height))
            new_width = max(64, round(width * scale / 64) * 64)
            new_height = max(64, round(height * scale / 64) * 64)
            if (new_width, new_height) != (width, height):
                img = img.resize((new_width, new_height), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=92)
            b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        return b64, new_width, new_height

    def edit_image(self, prompt: str, source_image_path, strength: float = 0.7) -> dict:
        """
        Edit an existing image (one FreesIA generated, or one you provide) by
        describing the change - uses image-to-image, not FastSD CPU's "edit_image"
        task (that one is hardcoded to a specific Flux2 Klein model and errors
        with any other checkpoint, including RealCore XL).
        Args:
            prompt: description of the desired change
            source_image_path: path to the image to edit
            strength: 0-1, how much of the original to preserve (lower = closer
                      to the original, higher = closer to a fresh generation).
                      Tested empirically across several combinations: at the base
                      6-step generation setting, strength=0.6 was too low to make
                      the change visible at all, while strength=0.85 applied it but
                      no longer looked like an edit of the source (looked like an
                      unrelated, lower-quality image - too few *effective* steps,
                      ~6*0.85=5, for good quality at that much deviation). Bumping
                      to 12 total steps with strength=0.7 (~8.4 effective steps)
                      gave the best result: clearly recognizable as the same image,
                      change clearly applied, and no quality drop.
        """
        source_image_path = Path(source_image_path)
        if not source_image_path.exists():
            return {"success": False, "error": f"Source image not found: {source_image_path}"}

        try:
            init_image_b64, width, height = self._prepare_edit_image(source_image_path)
        except Exception as e:
            return {"success": False, "error": f"Couldn't read source image: {e}"}

        payload = self._base_image_gen_payload(prompt, image_width=width, image_height=height)
        payload["diffusion_task"] = "image_to_image"
        payload["number_of_images"] = 1
        payload["init_image"] = init_image_b64
        payload["strength"] = strength
        payload["inference_steps"] = 12
        return self._call_fastsdcpu(payload, prompt)

    def _looks_like_plain_reaction(self, text: str) -> bool:
        """
        Cheap deterministic guard so short praise/thanks ("Thanks, that looks
        great!") and plain greetings ("Hey") never reach the image-intent
        classifier below - tested empirically that a 3B model occasionally
        misfires on these as a fresh generate_image call otherwise (invented
        a picture of a sky in response to a bare "Hey"). classify_image_intent()
        only runs when there's a recent image in context, and the message
        routing checks it before quick-response greetings ever get a chance
        to short-circuit, so this needs its own explicit check against the
        same canonical greeting list rather than relying on that ordering.
        """
        if text.strip().lower().strip('.,!?') in self.QUICK_RESPONSES:
            return True
        words = text.lower().split()
        if len(words) > 6:
            return False
        action_words = {"make", "change", "edit", "add", "remove", "turn", "convert",
                         "draw", "generate", "create", "gimme", "give", "show",
                         "picture", "image", "pic", "photo", "instead", "again"}
        if any(w.strip('.,!?') in action_words for w in words):
            return False
        reaction_words = {"thanks", "thank", "great", "nice", "perfect", "love",
                           "awesome", "cool", "wow", "amazing", "good", "lovely", "beautiful"}
        return any(w.strip('.,!?') in reaction_words for w in words)

    def generate_chat_title(self, first_message: str, first_response: str = "") -> str:
        """
        Short (3-5 word) chat title from the opening exchange, like ChatGPT/
        Claude/Grok auto-naming. Uses the fast local model - this only needs
        to skim a couple messages, not reason deeply. Falls back to a trimmed
        slice of the user's own message if the model call fails or returns
        something unusable.
        """
        import ollama
        fallback = first_message.strip()[:40] or "New Chat"

        system = ("Summarize the topic of this conversation opener in 3-5 words, "
                   "title case, no punctuation, no quotes. Just the title, nothing else.")
        user_content = f"User: {first_message}"
        if first_response:
            user_content += f"\nAssistant: {first_response[:300]}"

        try:
            resp = ollama.chat(
                model=self.ollama_fast_model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user_content}],
                options={"temperature": 0.3},
            )
            title = resp["message"]["content"].strip().strip('"\'').strip()
            title = title.split("\n")[0].strip()
            if not title or len(title) > 60:
                return fallback
            return title
        except Exception:
            return fallback

    def generate_checkin(self, recent: str = "", when: str = "") -> str:
        """
        One short unprompted line from the assistant ("check-in"), in its current persona.
        `recent` is a few lines of the latest chat, `when` a phrase like
        "Tuesday, 11:40 PM (late night)". Uses the fast model; falls back to a
        static line when the model is unavailable so a check-in never errors.
        """
        import random
        fallbacks = ["Still up?", "Hey. You've been quiet.", "Just checking in. How's it going?", "Anything you need?"]
        try:
            import ollama
            persona = getattr(self, "condensed_personality", "") or f"You are {self.assistant_name}."
            system = (persona + "\n\nYou are starting the conversation yourself because the user has been away. "
                      "Write ONE short message (under 20 words) in character. No quotes, no emoji, "
                      "no greeting formulas, do not mention being an AI. Output only the message.")
            user = f"Time now: {when}\n"
            if recent:
                user += f"Recent chat:\n{recent[-900:]}\n"
            user += "Write the message."
            resp = ollama.chat(
                model=self.ollama_fast_model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                options={"temperature": 0.8},
            )
            text = resp["message"]["content"].strip().strip('"\'').strip()
            text = text.split("\n")[0].strip()
            if not text or len(text) > 220:
                return random.choice(fallbacks)
            return text
        except Exception:
            return random.choice(fallbacks)

    def classify_image_intent(self, text: str) -> dict | None:
        """
        Use the fast local LLM's native tool-calling to recognize natural,
        unstructured requests to generate or edit an image ("gimme a pic of a
        dog", "make the apple more red") - instead of requiring an exact
        trigger phrase like "generate an image of X". Only called when there's
        a recent image in context (checked by the caller), and only for
        llama3.2:3b specifically - phi4-mini was tested and doesn't reliably
        use tool-calling at all.
        Returns: {"action": "generate", "prompt": str}
              or {"action": "edit", "change": str}
              or None (not an image-related request)
        """
        if self._looks_like_plain_reaction(text):
            return None

        import ollama
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "generate_image",
                    "description": "Generate a brand new image from a text description",
                    "parameters": {
                        "type": "object",
                        "properties": {"prompt": {"type": "string", "description": "what to draw"}},
                        "required": ["prompt"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "edit_image",
                    "description": "Edit/modify the most recently generated or uploaded image based on a description of the desired change",
                    "parameters": {
                        "type": "object",
                        "properties": {"change": {"type": "string", "description": "the change to make"}},
                        "required": ["change"],
                    },
                },
            },
        ]
        system = ("A user recently generated or uploaded an image. You have tools to generate a "
                  "brand new image, or edit the existing one. Only call a tool if the user is "
                  "clearly asking for a new image or describing a specific visual change to make. "
                  "Do not call a tool for comments, opinions, thanks, praise, or unrelated chat.")
        try:
            resp = ollama.chat(
                model=self.ollama_fast_model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": text}],
                tools=tools,
                options={"temperature": 0.1},
            )
        except Exception:
            return None

        tool_calls = resp["message"].get("tool_calls")
        if not tool_calls:
            return None
        call = tool_calls[0]
        if call.function.name == "generate_image":
            return {"action": "generate", "prompt": call.function.arguments.get("prompt", text)}
        elif call.function.name == "edit_image":
            return {"action": "edit", "change": call.function.arguments.get("change", text)}
        return None

    def _image_context_is_fresh(self, window_seconds: int = 180) -> bool:
        """
        Whether the last generated image is recent enough that a natural-language
        follow-up ("make it more red") should still be checked via the LLM
        classifier. Without this, classify_image_intent() would run on every
        single message for the rest of the conversation once any image had ever
        been generated - a permanent ~1-3s tax per message for a scenario
        (editing an image from many turns ago without saying "edit") that's rare
        in practice. 3 minutes covers the realistic "just looked at it and reacted"
        window; anything older still works via the explicit "edit <filename>"
        trigger or by re-attaching the photo.
        """
        import time
        if not self.last_generated_image_path or self.last_image_gen_time is None:
            return False
        return (time.time() - self.last_image_gen_time) < window_seconds

    def _run_generate_image_command(self, prompt: str) -> str:
        """Shared by the explicit 'generateimage' trigger and the natural-language classifier"""
        clean_prompt, size, count, negative_prompt = self._parse_image_gen_options(prompt)
        message = f"Generating an image of '{clean_prompt}'... this may take a moment."
        print(f"{self.name}: {message}")
        self.speak("Generating that now.")
        result = self.generate_image(clean_prompt, size=size, count=count, negative_prompt=negative_prompt)
        if result["success"]:
            for p in result["paths"]:
                self.open_file(p)
            names = ", ".join(p.name for p in result["paths"])
            message = f"Done. Opened the generated image(s) ({names})."
            print(f"{self.name}: {message}")
            self.speak("Done.")
            return message
        else:
            message = f"Couldn't generate that: {result['error']}"
            print(f"{self.name}: {message}")
            self.speak("Image generation failed.")
            return message

    def _run_edit_last_image_command(self, change: str) -> str:
        """Shared by the explicit 'editlast' trigger and the natural-language classifier"""
        if not self.last_generated_image_path or not Path(self.last_generated_image_path).exists():
            message = "I haven't generated an image yet to edit."
            print(f"{self.name}: {message}")
            self.speak(message)
            return message
        message = f"Editing the last image: '{change}'... this may take a moment."
        print(f"{self.name}: {message}")
        self.speak("Editing that now.")
        result = self.edit_image(change, self.last_generated_image_path)
        if result["success"]:
            self.open_file(result["path"])
            message = f"Done. Opened the edited image ({result['path'].name})."
            print(f"{self.name}: {message}")
            self.speak("Done.")
            return message
        else:
            message = f"Couldn't edit that: {result['error']}"
            print(f"{self.name}: {message}")
            self.speak("Image editing failed.")
            return message

    # ==================== TEXT-TO-SPEECH ====================
    
    def speak(self, text: str):
        """
        Speak text using text-to-speech (non-blocking in continuous mode)
        Args:
            text: Text to speak
        """
        if self.tts_enabled and self.tts_engine:
            try:
                # Run TTS in non-blocking way if in continuous listening mode
                if self.listening_active:
                    # Create a separate thread for TTS so it doesn't block listening
                    tts_thread = threading.Thread(target=self._speak_blocking, args=(text,), daemon=True)
                    tts_thread.start()
                else:
                    # Normal blocking mode when not in continuous listening
                    self._speak_blocking(text)
            except Exception as e:
                # If TTS fails, just print (silent fallback)
                pass
    
    def _speak_blocking(self, text: str):
        """Internal method for blocking TTS"""
        try:
            v = getattr(self, "local_voice", None)
            if v and v.cfg.get("engine") == "local" and v.speak(text):
                return
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
        except:
            pass

    def _speak_system(self, text: str):
        """Windows voice on a fresh engine - safe to call from a worker thread."""
        try:
            import pyttsx3
            v = getattr(self, "local_voice", None)
            cfg = v.cfg if v else {}
            eng = pyttsx3.init()
            eng.setProperty('rate', int(180 * float(cfg.get("speed", 1.0))))
            eng.setProperty('volume', float(cfg.get("volume", 0.9)))
            for voice in eng.getProperty('voices'):
                if "female" in voice.name.lower() or "zira" in voice.name.lower():
                    eng.setProperty('voice', voice.id)
                    break
            eng.say(text)
            eng.runAndWait()
        except Exception:
            pass

    def speak_reply(self, text: str):
        """Read a chat reply aloud if 'Read replies aloud' is on. Never blocks the caller."""
        v = getattr(self, "local_voice", None)
        if not v or not v.cfg.get("read_aloud") or not text:
            return
        v.stop()
        threading.Thread(target=v.speak_with_fallback, args=(text,), daemon=True).start()

    def stop_speaking(self):
        v = getattr(self, "local_voice", None)
        if v:
            v.stop()
    
    def toggle_tts(self):
        """Toggle text-to-speech on/off"""
        if not self.tts_engine:
            print(f"{self.name}: Text-to-speech is not available on this system.")
            return
        
        self.tts_enabled = not self.tts_enabled
        status = "enabled" if self.tts_enabled else "disabled"
        message = f"Text-to-speech {status}"
        print(f"{self.name}: {message}")
        
        # Only speak if TTS was just enabled
        if self.tts_enabled:
            self.speak(message)
    
    def enable_tts(self):
        """Turn text-to-speech ON"""
        if not self.tts_engine:
            print(f"{self.name}: Text-to-speech is not available on this system.")
            return
        
        if self.tts_enabled:
            message = "Text-to-speech is already enabled"
            print(f"{self.name}: {message}")
            self.speak(message)
        else:
            self.tts_enabled = True
            message = "Text-to-speech enabled"
            print(f"{self.name}: {message}")
            self.speak(message)
    
    def disable_tts(self):
        """Turn text-to-speech OFF"""
        if not self.tts_engine:
            print(f"{self.name}: Text-to-speech is not available on this system.")
            return
        
        if not self.tts_enabled:
            print(f"{self.name}: Text-to-speech is already disabled")
        else:
            self.tts_enabled = False
            print(f"{self.name}: Text-to-speech disabled")

    # ==================== FILE OPERATIONS ====================
    
    def search_file(self, filename: str) -> List[Path]:
        """
        Search for files matching the given name
        Args:
            filename: Partial or full filename to search for
        Returns: List of matching file paths (max 10)
        """
        # REQUEST PERMISSION FOR FILE ACCESS
        if not self.request_permission("file_access"):
            return []
        
        print(f"{self.name}: Searching for '{filename}'...")
        found_files = []
        max_depth = 4  # Limit recursion depth to prevent deep traversal
        
        def search_with_depth(path: Path, depth: int):
            """Search with depth limit"""
            if depth > max_depth:
                return
            
            try:
                for item in path.iterdir():
                    # Stop if we found enough files
                    if len(found_files) >= 10:
                        return
                    
                    try:
                        if item.is_file() and filename.lower() in item.name.lower():
                            found_files.append(item)
                        elif item.is_dir() and not item.name.startswith('.'):
                            # Recurse into subdirectories (excluding hidden folders)
                            search_with_depth(item, depth + 1)
                    except (PermissionError, OSError):
                        continue
            except (PermissionError, OSError):
                pass
        
        # Search in all defined search paths
        for search_path in self.search_paths:
            if len(found_files) >= 10:
                break
            search_with_depth(search_path, 0)
        
        return found_files[:10]  # Limit results to prevent overwhelming output

    def extract_file_text(self, file_path: Path, max_chars: int = 12000) -> str | None:
        """
        Extract plain text from a file so it can be summarized/discussed.
        Args:
            file_path: Path to the file to read
            max_chars: Cap on returned text (keeps the file within the model's context)
        Returns: Extracted text, or None if the file type isn't supported
        """
        suffix = file_path.suffix.lower()
        try:
            if suffix in ('.txt', '.md', '.log', '.csv', '.json'):
                text = file_path.read_text(encoding='utf-8', errors='replace')
            elif suffix == '.docx':
                import docx
                doc = docx.Document(str(file_path))
                text = "\n".join(p.text for p in doc.paragraphs)
            elif suffix == '.pdf':
                import pypdf
                reader = pypdf.PdfReader(str(file_path))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
            else:
                return None  # Unsupported type (e.g. legacy .doc)
        except Exception as e:
            print(f"{self.name}: Error reading {file_path.name}: {e}")
            return None

        text = text.strip()
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[...file truncated, too long to read in full...]"
        return text

    def read_file_and_respond(self, file_path: Path, content: str) -> str:
        """
        Send extracted file content to the AI and get a personality-flavored summary/answer.
        Kept out of the persistent conversation history so large file dumps don't bloat
        every future prompt.
        """
        import ollama
        system_msg = self.personality_prompt or "You are FreesIA, a helpful assistant."
        user_msg = f"Here is the content of the file '{file_path.name}':\n\n{content}\n\nBriefly tell me what this file says."
        try:
            resp = ollama.chat(
                model=self.ollama_model,
                messages=[
                    {'role': 'system', 'content': system_msg},
                    {'role': 'user', 'content': user_msg}
                ],
                options={'temperature': 0.7, 'num_predict': 300}
            )
            return resp['message']['content']
        except Exception as e:
            return f"Found the file, but couldn't process it: {e}"

    def open_file(self, file_path: Path) -> bool:
        """
        Open a file with its default application
        Args:
            file_path: Path to the file to open
        Returns: True if successful, False otherwise
        """
        try:
            os.startfile(file_path)  # Windows-specific file opener
            print(f"{self.name}: Opening {file_path.name}")
            return True
        except Exception as e:
            print(f"{self.name}: Error opening file: {e}")
            return False
    
    # ==================== APPLICATION CONTROL ====================

    def _search_obvious_locations(self, app_name: str) -> str | None:
        """
        Last-resort live lookup for an app that isn't in the cache yet - e.g. it was
        installed after the cache was last built (cache is only rebuilt every
        app_cache_max_age days). Checks a small set of obvious places rather than
        scanning the whole filesystem, so it stays fast even on a miss.
        Returns: exe path if found, else None
        """
        def normalize(s: str) -> str:
            return re.sub(r'[^a-z0-9]', '', s.lower())

        normalized_target = normalize(app_name)

        # 1) Check Start Menu shortcuts fresh (catches almost anything installed normally)
        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            start_dirs = [
                Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"),
                Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            ]
            for start_dir in start_dirs:
                if not start_dir.exists():
                    continue
                for lnk in start_dir.rglob("*.lnk"):
                    stem = normalize(lnk.stem)
                    if normalized_target == stem or normalized_target in stem or stem in normalized_target:
                        try:
                            target = shell.CreateShortCut(str(lnk)).Targetpath
                            if target and target.lower().endswith(".exe") and Path(target).exists():
                                return target
                        except Exception:
                            continue
        except Exception:
            pass

        # 2) Check common install roots for a folder matching the app name
        common_roots = [
            Path(r"C:\Program Files"),
            Path(r"C:\Program Files (x86)"),
            Path.home() / "AppData" / "Local" / "Programs",
            Path.home() / "AppData" / "Local",
            Path.home() / "AppData" / "Roaming",
        ]
        for root in common_roots:
            if not root.exists():
                continue
            try:
                for entry in root.iterdir():
                    if not entry.is_dir():
                        continue
                    entry_norm = normalize(entry.name)
                    if normalized_target == entry_norm or normalized_target in entry_norm:
                        exe_files = self._find_exe_candidates(entry)
                        if exe_files:
                            return str(self._pick_best_exe(exe_files, app_name))
            except (PermissionError, OSError):
                continue

        return None

    SYSTEM_FOLDERS = {
        "downloads": lambda: Path.home() / "Downloads",
        "download": lambda: Path.home() / "Downloads",
        "documents": lambda: Path.home() / "Documents",
        "document": lambda: Path.home() / "Documents",
        "desktop": lambda: Path.home() / "Desktop",
        "pictures": lambda: Path.home() / "Pictures",
        "photos": lambda: Path.home() / "Pictures",
        "music": lambda: Path.home() / "Music",
        "videos": lambda: Path.home() / "Videos",
    }

    def _clean_target_name(self, raw: str) -> str:
        """
        "open <X>" just takes everything after the word "open" verbatim, which
        breaks on ordinary phrasing: "open up claude" -> "up claude" (treating
        "up" as part of the app name), "open the discord app please" -> "the
        discord app please". Strips phrasal-verb/filler words from both ends
        so the remaining text is just the actual target name.
        """
        leading_filler = {"up", "the", "a", "an", "my"}
        trailing_filler = {"please", "app", "application", "now", "up"}
        words = raw.strip().rstrip("?.!").split()
        while words and words[0] in leading_filler:
            words.pop(0)
        while words and words[-1] in trailing_filler:
            words.pop()
        return " ".join(words)

    def open_system_folder(self, raw_request: str):
        """
        "open the downloads folder" etc. was being treated purely as an app-launch
        request (matched against installed_apps), so it always failed - there was
        no folder-opening path at all. Strips filler words ("the", "folder",
        "please"...) down to the actual folder name and opens it directly with
        Explorer if it's a recognized system folder.
        Returns a result message if handled, or None if this isn't a recognized
        folder name (caller falls through to the app-launch path).
        """
        filler = {"the", "a", "an", "my", "please", "folder", "folders", "open"}
        words = [w for w in raw_request.lower().split() if w not in filler]
        key = " ".join(words).strip()

        resolver = self.SYSTEM_FOLDERS.get(key)
        folder_path = resolver() if resolver else None
        if folder_path is None:
            custom_path = self.custom_folders.get(key)
            if custom_path:
                folder_path = Path(custom_path)
        if folder_path is None:
            return None

        folder_name = folder_path.name
        try:
            if resolver:
                folder_path.mkdir(parents=True, exist_ok=True)
            elif not folder_path.exists():
                # A cached custom folder that's since been moved/deleted -
                # don't silently create a new empty folder in its place.
                return f"Couldn't find {folder_name} - it may have been moved. Try Rescan Folders in Settings."
            os.startfile(str(folder_path))
            message = f"Opening {folder_name}."
            print(f"{self.name}: {message}")
            self.speak(message)
            return message
        except Exception as e:
            error_msg = f"Couldn't open {folder_name}: {e}"
            print(f"{self.name}: {error_msg}")
            self.speak("Couldn't open that folder.")
            return error_msg

    def open_application(self, app_name: str):
        """
        Launch an application by name
        Args:
            app_name: Name of the application to open
        Returns: Message string describing the result
        """
        app_name_original = app_name
        app_name = app_name.lower()
        
        if app_name in self.installed_apps:
            try:
                app_path = self.installed_apps[app_name]
                
                # Handle special URI schemes (like ms-settings:)
                if app_path.startswith("ms-"):
                    webbrowser.open(app_path)
                elif Path(app_path).name.lower() == "update.exe":
                    # Electron/Squirrel-installed apps (Discord, Slack, Teams...)
                    # get cached as their Update.exe stub, not the real versioned
                    # executable (the version folder name changes with every
                    # update, so it can't be cached directly). Running Update.exe
                    # bare just does a quick update-check and exits without ever
                    # opening the app - no error, no window, nothing. The actual
                    # app launch needs --processStart <name>.exe, the same
                    # invocation the app's own Start Menu shortcut uses; the
                    # parent folder name (e.g. "Discord") matches that exe name.
                    proc_name = f"{Path(app_path).parent.name}.exe"
                    subprocess.Popen(
                        [app_path, "--processStart", proc_name],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        stdin=subprocess.DEVNULL
                    )
                else:
                    # Open application without capturing output (detached process)
                    subprocess.Popen(
                        app_path,
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        stdin=subprocess.DEVNULL
                    )

                message = f"Opening {app_name}."
                print(f"{self.name}: {message}")
                self.speak(message)
                return message
            except Exception as e:
                # Try to open as a Store app using its package name
                try:
                    ps_command = f"""
                    $app = Get-AppxPackage -Name "*{app_name}*" | Select-Object -First 1
                    if ($app) {{
                        explorer.exe "shell:appsFolder\\$($app.PackageFamilyName)!App"
                    }}
                    """
                    subprocess.run(
                        ['powershell', '-NoProfile', '-Command', ps_command],
                        capture_output=True,
                        timeout=5
                    )
                    message = f"Opening {app_name_original}."
                    print(f"{self.name}: {message}")
                    self.speak(message)
                    return message
                except:
                    error_msg = f"Error opening {app_name}: {e}"
                    print(f"{self.name}: {error_msg}")
                    self.speak("Could not open app")
                    return error_msg
        else:
            # App not in cached list - try a quick direct lookup using PowerShell.
            # No -AllUsers here either - same admin-elevation issue as the scan.
            try:
                ps_command = f"""
                $app = Get-AppxPackage -Name "*{app_name}*" | Select-Object -First 1
                if ($app) {{
                    explorer.exe "shell:appsFolder\\$($app.PackageFamilyName)!App"
                    exit 0
                }} else {{
                    exit 1
                }}
                """
                result = subprocess.run(
                    ['powershell', '-NoProfile', '-Command', ps_command],
                    capture_output=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    # Found and opened the app via PowerShell
                    message = f"Opening {app_name_original}."
                    print(f"{self.name}: {message}")
                    self.speak(message)
                    return message
            except:
                pass  # Fall through to the obvious-locations fallback

            # Not in the cache - check obvious install locations before giving up
            # (handles apps installed since the cache was last built)
            found_path = self._search_obvious_locations(app_name)
            if found_path:
                self.installed_apps[app_name] = found_path
                self.save_app_cache()  # so it's instant next time
                try:
                    subprocess.Popen(
                        found_path, shell=True,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL
                    )
                    message = f"Found it. Opening {app_name_original}."
                    print(f"{self.name}: {message}")
                    self.speak(message)
                    return message
                except Exception as e:
                    error_msg = f"Found {app_name_original} but couldn't open it: {e}"
                    print(f"{self.name}: {error_msg}")
                    self.speak("Found it, but couldn't open it")
                    return error_msg

            message = f"{app_name}? Can't find it. Not installed."
            print(f"{self.name}: {message}")
            self.speak(message)
            # Suggest similar apps using fuzzy matching
            suggestions = get_close_matches(app_name, self.installed_apps.keys(), n=3, cutoff=0.5)
            if suggestions:
                return f"{message} Did you mean {suggestions[0]}?"
            return message
    
    def close_application(self, app_name: str):
        """
        Close/terminate a running application by name
        Args:
            app_name: Name of the application to close
        Returns: True if successful, False otherwise
        """
        # REQUEST PERMISSION FOR SYSTEM SETTINGS
        if not self.request_permission("system_settings"):
            return False
        
        app_name = app_name.lower()
        
        # Map common app names to their process names
        process_name_map = {
            "notepad": "notepad.exe",
            "calculator": "calculator.exe",
            "paint": "mspaint.exe",
            "explorer": "explorer.exe",
            "cmd": "cmd.exe",
            "powershell": "powershell.exe",
            "task manager": "taskmgr.exe",
            "chrome": "chrome.exe",
            "firefox": "firefox.exe",
            "edge": "msedge.exe",
            "brave": "brave.exe",
            "opera": "opera.exe",
            "spotify": "Spotify.exe",
            "discord": "Discord.exe",
            "slack": "slack.exe",
            "teams": "Teams.exe",
            "zoom": "Zoom.exe",
            "vscode": "Code.exe",
            "visual studio code": "Code.exe",
            "visual studio": "devenv.exe",
            "sublime": "sublime_text.exe",
            "notepad++": "notepad++.exe",
            "atom": "atom.exe",
            "word": "WINWORD.EXE",
            "excel": "EXCEL.EXE",
            "powerpoint": "POWERPNT.EXE",
            "outlook": "OUTLOOK.EXE",
            "onenote": "ONENOTE.EXE",
            "photoshop": "Photoshop.exe",
            "illustrator": "Illustrator.exe",
            "obs": "obs64.exe",
            "vlc": "vlc.exe",
            "settings": "SystemSettings.exe",
        }
        
        # Get process name
        process_name = process_name_map.get(app_name, f"{app_name}.exe")
        
        try:
            # Use taskkill to terminate the process
            result = subprocess.run(
                ["taskkill", "/F", "/IM", process_name],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                message = f"Closed {app_name}"
                print(f"{self.name}: {message}")
                self.speak(message)
                return True
            else:
                # Try without .exe extension if it failed
                if process_name.endswith(".exe"):
                    process_name_alt = process_name[:-4]
                    result = subprocess.run(
                        ["taskkill", "/F", "/IM", f"{process_name_alt}.exe"],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0:
                        message = f"Closed {app_name}"
                        print(f"{self.name}: {message}")
                        self.speak(message)
                        return True
                
                # Process not found or couldn't close
                message = f"Could not close {app_name}. It may not be running."
                print(f"{self.name}: {message}")
                self.speak(message)
                return False
                
        except Exception as e:
            error_msg = f"Error closing {app_name}"
            print(f"{self.name}: {error_msg}: {e}")
            self.speak(error_msg)
            return False
    
    # ==================== SYSTEM CONTROL ====================
    
    def adjust_volume(self, action: str):
        """
        Adjust system volume using keyboard shortcuts
        Args:
            action: "up", "down", or "mute"
        """
        # REQUEST PERMISSION FOR SYSTEM SETTINGS
        if not self.request_permission("system_settings"):
            return
        
        try:
            if "up" in action or "increase" in action:
                # Send volume up key
                subprocess.run(["powershell", "-c", "(new-object -com wscript.shell).SendKeys([char]175)"])
                print(f"{self.name}: Volume increased")
            elif "down" in action or "decrease" in action:
                # Send volume down key
                subprocess.run(["powershell", "-c", "(new-object -com wscript.shell).SendKeys([char]174)"])
                print(f"{self.name}: Volume decreased")
            elif "mute" in action:
                # Send mute toggle key
                subprocess.run(["powershell", "-c", "(new-object -com wscript.shell).SendKeys([char]173)"])
                print(f"{self.name}: Volume muted/unmuted")
        except Exception as e:
            print(f"{self.name}: Error adjusting volume: {e}")
    
    def adjust_brightness(self, action: str):
        """
        Adjust screen brightness
        Args:
            action: "up", "down", "brighten", or "dim"
        """
        # REQUEST PERMISSION FOR SYSTEM SETTINGS
        if not self.request_permission("system_settings"):
            return
        
        try:
            if "up" in action or "increase" in action or "brighten" in action or "brighter" in action:
                # Try WMI method first (increase by 10%)
                subprocess.run(["powershell", "-Command", 
                    "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,((Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness + 10))"],
                    capture_output=True, shell=True)
                print(f"{self.name}: Brightness increased")
            elif "down" in action or "decrease" in action or "dim" in action or "darker" in action:
                # Try WMI method first (decrease by 10%)
                subprocess.run(["powershell", "-Command", 
                    "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,((Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness - 10))"],
                    capture_output=True, shell=True)
                print(f"{self.name}: Brightness decreased")
        except Exception as e:
            # Fallback to keyboard shortcuts if WMI fails
            try:
                if "up" in action or "increase" in action or "brighten" in action or "brighter" in action:
                    subprocess.run(["powershell", "-c", "(new-object -com wscript.shell).SendKeys('{F15}')"])
                    print(f"{self.name}: Brightness increased")
                elif "down" in action or "decrease" in action or "dim" in action or "darker" in action:
                    subprocess.run(["powershell", "-c", "(new-object -com wscript.shell).SendKeys('{F14}')"])
                    print(f"{self.name}: Brightness decreased")
            except:
                print(f"{self.name}: Could not adjust brightness. Try using your keyboard brightness keys.")
    
    def toggle_wifi(self):
        """Toggle WiFi on/off"""
        # REQUEST PERMISSION FOR SYSTEM SETTINGS
        if not self.request_permission("system_settings"):
            return
        
        try:
            # Open Network & Internet settings where user can toggle WiFi
            # Windows 10/11 settings URI
            subprocess.run(["start", "ms-settings:network-wifi"], shell=True)
            message = "Opening WiFi settings. Please toggle WiFi manually."
            print(f"{self.name}: {message}")
            self.speak(message)
            
            # Note: Programmatically toggling WiFi requires admin privileges and is complex
            # Opening settings is the safest approach
        except Exception as e:
            error_msg = "Could not open WiFi settings"
            print(f"{self.name}: {error_msg}: {e}")
            self.speak(error_msg)
    
    def toggle_bluetooth(self):
        """Toggle Bluetooth on/off"""
        # REQUEST PERMISSION FOR SYSTEM SETTINGS
        if not self.request_permission("system_settings"):
            return
        
        try:
            # Open Bluetooth settings
            subprocess.run(["start", "ms-settings:bluetooth"], shell=True)
            message = "Opening Bluetooth settings. Please toggle Bluetooth manually."
            print(f"{self.name}: {message}")
            self.speak(message)
            
            # Note: Programmatically toggling Bluetooth requires admin privileges
            # Opening settings is the safest approach
        except Exception as e:
            error_msg = "Could not open Bluetooth settings"
            print(f"{self.name}: {error_msg}: {e}")
            self.speak(error_msg)
    
    def open_control_panel(self):
        """Open Windows Control Panel"""
        # REQUEST PERMISSION FOR SYSTEM SETTINGS
        if not self.request_permission("system_settings"):
            return
        
        try:
            subprocess.run(["control.exe"], shell=True)
            message = "Opening Control Panel"
            print(f"{self.name}: {message}")
            self.speak(message)
        except Exception as e:
            error_msg = "Could not open Control Panel"
            print(f"{self.name}: {error_msg}: {e}")
            self.speak(error_msg)
    
    # ==================== MEDIA CONTROL ====================
    
    def media_play_pause(self):
        """Play or pause media (Spotify, YouTube, etc.)"""
        # REQUEST PERMISSION FOR SYSTEM SETTINGS
        if not self.request_permission("system_settings"):
            return
        
        try:
            # Send media play/pause key
            subprocess.run(["powershell", "-c", "(new-object -com wscript.shell).SendKeys([char]179)"])
            print(f"{self.name}: Media play/pause toggled")
            self.speak("Toggled play pause")
        except Exception as e:
            print(f"{self.name}: Error controlling media: {e}")
    
    def media_next(self):
        """Skip to next track"""
        # REQUEST PERMISSION FOR SYSTEM SETTINGS
        if not self.request_permission("system_settings"):
            return
        
        try:
            # Send media next track key
            subprocess.run(["powershell", "-c", "(new-object -com wscript.shell).SendKeys([char]176)"])
            print(f"{self.name}: Skipped to next track")
            self.speak("Next track")
        except Exception as e:
            print(f"{self.name}: Error skipping track: {e}")
    
    def media_previous(self):
        """Go to previous track"""
        # REQUEST PERMISSION FOR SYSTEM SETTINGS
        if not self.request_permission("system_settings"):
            return
        
        try:
            # Send media previous track key
            subprocess.run(["powershell", "-c", "(new-object -com wscript.shell).SendKeys([char]177)"])
            print(f"{self.name}: Playing previous track")
            self.speak("Previous track")
        except Exception as e:
            print(f"{self.name}: Error going to previous track: {e}")
    
    def media_stop(self):
        """Stop media playback"""
        # REQUEST PERMISSION FOR SYSTEM SETTINGS
        if not self.request_permission("system_settings"):
            return
        
        try:
            # Send media stop key
            subprocess.run(["powershell", "-c", "(new-object -com wscript.shell).SendKeys([char]178)"])
            print(f"{self.name}: Media stopped")
            self.speak("Media stopped")
        except Exception as e:
            print(f"{self.name}: Error stopping media: {e}")
    
    # ==================== WAKE WORD DETECTION ====================
    
    def check_wake_word(self, text: str) -> bool:
        """
        Check if text contains the wake word (like "Hey Siri")
        Args:
            text: The text to check
        Returns: True if wake word detected
        """
        text_lower = text.lower().strip()
        
        # Check for exact wake word matches
        for wake_word in self.wake_words:
            if wake_word in text_lower:
                return True
        
        # Also check using fuzzy matching for similar pronunciations
        if self.fuzzy_match(text_lower, self.wake_words, threshold=0.7):
            return True
            
        return False
    
    def respond_to_wake_word(self):
        """Respond when wake word is detected (like Alexa/Siri)"""
        responses = [
            "Yes? How can I help you?",
            "I'm listening!",
            "Hello! What can I do for you?",
            "Yes, I'm here. What do you need?",
            "How may I assist you?",
        ]
        import random
        response = random.choice(responses)
        print(f"\n{self.name}: {response}")
        self.speak(response)
    
    # ==================== SYSTEM FEATURES ====================
    
    def get_battery_status(self):
        """Get battery percentage and charging status"""
        # REQUEST PERMISSION FOR SYSTEM SETTINGS
        if not self.request_permission("system_settings"):
            return
        
        try:
            battery = psutil.sensors_battery()
            if battery:
                percent = battery.percent
                plugged = "Charging" if battery.power_plugged else "Not charging"
                print(f"{self.name}: Battery is at {percent}% - {plugged}")
            else:
                print(f"{self.name}: No battery detected (desktop computer)")
        except Exception as e:
            print(f"{self.name}: Could not get battery status: {e}")
    
    def get_system_info(self):
        """Get system information (CPU, RAM, Disk)"""
        # REQUEST PERMISSION FOR SYSTEM SETTINGS
        if not self.request_permission("system_settings"):
            return
        
        try:
            # CPU info
            cpu_usage = psutil.cpu_percent(interval=1)
            cpu_freq = psutil.cpu_freq()
            cpu_cores = psutil.cpu_count(logical=True)
            print(f"{self.name}: CPU Usage: {cpu_usage}%, Cores: {cpu_cores}, Frequency: {cpu_freq.current}MHz")
            
            # RAM info
            virtual_mem = psutil.virtual_memory()
            swap_mem = psutil.swap_memory()
            print(f"{self.name}: RAM Usage: {virtual_mem.percent}%, Free: {virtual_mem.available / (1024**3):.2f}GB")
            print(f"{self.name}: Swap Usage: {swap_mem.percent}%, Free: {swap_mem.free / (1024**3):.2f}GB")
            
            # Disk info
            disk_usage = psutil.disk_usage('/')
            print(f"{self.name}: Disk Usage: {disk_usage.percent}%, Free: {disk_usage.free / (1024**3):.2f}GB")
        except Exception as e:
            print(f"{self.name}: Could not get system info: {e}")
    
    def take_screenshot(self):
        """Take a screenshot and save to file"""
        # REQUEST PERMISSION FOR SYSTEM SETTINGS
        if not self.request_permission("system_settings"):
            return
        
        try:
            # Create screenshots directory in Pictures folder (Windows standard location)
            screenshots_dir = Path.home() / "Pictures" / "Screenshots"
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate screenshot file name
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = screenshots_dir / f"screenshot_{timestamp}.png"
            
            # Take screenshot
            img = ImageGrab.grab()
            img.save(file_path)
            print(f"{self.name}: Screenshot saved to {file_path}")
        except Exception as e:
            print(f"{self.name}: Error taking screenshot: {e}")
    
    def lock_computer(self):
        """Lock the computer"""
        # REQUEST PERMISSION FOR POWER CONTROL
        if not self.request_permission("power_control"):
            return
        
        try:
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
            print(f"{self.name}: Computer locked")
        except Exception as e:
            print(f"{self.name}: Error locking computer: {e}")
    
    def sleep_computer(self):
        """Put the computer to sleep"""
        # REQUEST PERMISSION FOR POWER CONTROL
        if not self.request_permission("power_control"):
            return
        
        # CONFIRMATION DIALOG FOR SLEEP
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            
            result = messagebox.askyesno(
                "💤 Confirm Sleep",
                "Are you sure you want to put the computer to sleep?",
                icon='question',
                parent=root
            )
            
            root.destroy()
            
            if not result:
                print(f"{self.name}: Sleep cancelled.")
                self.speak("Sleep cancelled")
                return
                
        except:
            # Fallback to console confirmation
            confirm = input(f"\n{self.name}: Put computer to sleep? (yes/no): ").strip().lower()
            if confirm not in ['yes', 'y']:
                print(f"{self.name}: Sleep cancelled.")
                return
        
        try:
            subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"])
            print(f"{self.name}: Computer going to sleep")
        except Exception as e:
            print(f"{self.name}: Error putting computer to sleep: {e}")
    
    def shutdown_computer(self, restart: bool = False):
        """Shutdown or restart the computer"""
        # REQUEST PERMISSION FOR POWER CONTROL
        if not self.request_permission("power_control"):
            return
        
        # CONFIRMATION DIALOG FOR SHUTDOWN/RESTART
        action = "restart" if restart else "shut down"
        icon_emoji = "🔄" if restart else "⚠️"
        
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            
            result = messagebox.askyesno(
                f"{icon_emoji} Confirm {action.title()}",
                f"Are you sure you want to {action} the computer?\n\nAll unsaved work will be lost!",
                icon='warning',
                parent=root
            )
            
            root.destroy()
            
            if not result:
                print(f"{self.name}: {action.title()} cancelled.")
                self.speak(f"{action.title()} cancelled")
                return
                
        except:
            # Fallback to console confirmation
            confirm = input(f"\n{self.name}: {action.title()} computer? This will close all programs! (yes/no): ").strip().lower()
            if confirm not in ['yes', 'y']:
                print(f"{self.name}: {action.title()} cancelled.")
                return
        
        try:
            if restart:
                subprocess.run(["shutdown", "/r", "/t", "5"])
                print(f"{self.name}: Restarting computer in 5 seconds...")
                self.speak("Restarting computer")
            else:
                subprocess.run(["shutdown", "/s", "/t", "5"])
                print(f"{self.name}: Shutting down computer in 5 seconds...")
                self.speak("Shutting down computer")
        except Exception as e:
            print(f"{self.name}: Error: {e}")
    
    # ==================== FILE MANAGEMENT ====================
    
    def get_recent_files(self):
        """Get a list of recently opened files"""
        # REQUEST PERMISSION FOR FILE ACCESS
        if not self.request_permission("file_access"):
            return
        
        try:
            recent_files = []
            
            # Check for recent files in Windows
            shell = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(shell, r"Software\Microsoft\Windows\CurrentVersion\Explorer\RecentDocs")
            for i in range(0, winreg.QueryInfoKey(key)[1]):
                try:
                    file_name = winreg.EnumValue(key, i)
                    recent_files.append(file_name[0])
                except:
                    continue
            winreg.CloseKey(key)
            
            # Check for recent files in Office (Word, Excel, etc.)
            office_apps = ["Word", "Excel", "PowerPoint", "Outlook"]
            for app in office_apps:
                try:
                    key = winreg.OpenKey(shell, fr"Software\Microsoft\Office\{app}\Recent")
                    for i in range(0, winreg.QueryInfoKey(key)[1]):
                        try:
                            file_name = winreg.EnumValue(key, i)
                            recent_files.append(file_name[0])
                        except:
                            continue
                    winreg.CloseKey(key)
                except:
                    continue
            
            # Limit to 10 recent files
            recent_files = list(dict.fromkeys(recent_files))  # Remove duplicates, preserve order
            for file in recent_files[:10]:
                print(f"  • {file}")
        except Exception as e:
            print(f"{self.name}: Error getting recent files: {e}")
    
    def delete_file(self, file_path: str):
        """Delete a file or move to recycle bin"""
        # REQUEST PERMISSION FOR FILE ACCESS
        if not self.request_permission("file_access"):
            return
        
        try:
            file_path = Path(file_path)
            if file_path.exists():
                # CONFIRMATION DIALOG FOR DESTRUCTIVE ACTION
                try:
                    root = tk.Tk()
                    root.withdraw()
                    root.attributes('-topmost', True)
                    
                    result = messagebox.askyesno(
                        "⚠️ Confirm File Deletion",
                        f"Are you sure you want to delete this file?\n\n{file_path.name}\n\nIt will be moved to the Recycle Bin.",
                        icon='warning',
                        parent=root
                    )
                    
                    root.destroy()
                    
                    if not result:
                        print(f"{self.name}: File deletion cancelled.")
                        self.speak("Deletion cancelled")
                        return
                        
                except:
                    # Fallback to console confirmation
                    confirm = input(f"\n{self.name}: Delete '{file_path.name}'? (yes/no): ").strip().lower()
                    if confirm not in ['yes', 'y']:
                        print(f"{self.name}: File deletion cancelled.")
                        return
                
                # Move to recycle bin instead of permanent delete
                import send2trash
                send2trash.send2trash(str(file_path))
                print(f"{self.name}: Moved {file_path.name} to recycle bin")
                self.speak("File deleted")
            else:
                print(f"{self.name}: File not found: {file_path}")
        except Exception as e:
            print(f"{self.name}: Error deleting file: {e}")
    
    def create_folder(self, folder_name: str):
        """Create a new folder in the user's Documents directory"""
        # REQUEST PERMISSION FOR FILE ACCESS
        if not self.request_permission("file_access"):
            return
        
        try:
            documents_path = Path.home() / "Documents"
            new_folder = documents_path / folder_name
            
            if new_folder.exists():
                print(f"{self.name}: Folder already exists: {new_folder}")
            else:
                new_folder.mkdir(parents=True)
                print(f"{self.name}: Created new folder: {new_folder}")
        except Exception as e:
            print(f"{self.name}: Error creating folder: {e}")
    
    # ==================== WEB & COMMUNICATION ====================
    
    def open_website(self, command: str):
        """Open a website or perform a Google search"""
        command_lower = command.lower()
        
        # Dictionary of common websites
        websites = {
            "youtube": "https://www.youtube.com",
            "gmail": "https://www.gmail.com",
            "google": "https://www.google.com",
            "facebook": "https://www.facebook.com",
            "twitter": "https://www.twitter.com",
            "instagram": "https://www.instagram.com",
            "reddit": "https://www.reddit.com",
            "amazon": "https://www.amazon.com",
            "netflix": "https://www.netflix.com",
            "spotify": "https://www.spotify.com",
            "linkedin": "https://www.linkedin.com",
            "github": "https://www.github.com",
            "stackoverflow": "https://stackoverflow.com",
            "twitch": "https://www.twitch.tv",
            "discord": "https://discord.com",
            "zoom": "https://zoom.us",
            "teams": "https://teams.microsoft.com",
            "outlook": "https://outlook.live.com",
            "wikipedia": "https://www.wikipedia.org",
            "tiktok": "https://www.tiktok.com",
            "pinterest": "https://www.pinterest.com",
            "tumblr": "https://www.tumblr.com",
            "whatsapp": "https://web.whatsapp.com",
            "telegram": "https://web.telegram.org",
            "slack": "https://slack.com",
            "dropbox": "https://www.dropbox.com",
            "drive": "https://drive.google.com",
            "onedrive": "https://onedrive.live.com",
            "trello": "https://trello.com",
            "notion": "https://www.notion.so",
            "canva": "https://www.canva.com",
            "figma": "https://www.figma.com",
            "medium": "https://medium.com",
            "quora": "https://www.quora.com",
            "ebay": "https://www.ebay.com",
            "aliexpress": "https://www.aliexpress.com",
            "craigslist": "https://www.craigslist.org",
            "yelp": "https://www.yelp.com",
            "imdb": "https://www.imdb.com",
            "espn": "https://www.espn.com",
            "cnn": "https://www.cnn.com",
            "bbc": "https://www.bbc.com",
            "nytimes": "https://www.nytimes.com",
        }
        
        # Check for Google search command
        if "search google for" in command_lower or "google search" in command_lower:
            query = command_lower.replace("search google for", "").replace("google search", "").strip()
            if query:
                webbrowser.open(f"https://www.google.com/search?q={query}")
                print(f"{self.name}: Searching Google for: {query}")
            else:
                print(f"{self.name}: Please provide a search query")
            return
        
        # Check if any known website is mentioned
        for site_name, url in websites.items():
            if site_name in command_lower:
                webbrowser.open(url)
                print(f"{self.name}: Opening {site_name.title()}")
                return
        
        # If no known website found, extract website name and search Google
        words_to_remove = ["open", "website", "go", "to", "visit", "the", "a"]
        extracted_words = []
        
        for word in command_lower.split():
            if word not in words_to_remove:
                extracted_words.append(word)
        
        if extracted_words:
            site_name = " ".join(extracted_words)
            print(f"{self.name}: Searching Google for: {site_name}")
            webbrowser.open(f"https://www.google.com/search?q={site_name}")
        else:
            print(f"{self.name}: Please specify a website name.")
            print(f"{self.name}: Example: 'open youtube' or 'open facebook'")
    
    def parse_natural_language(self, command: str) -> str:
        """
        Parse natural language into actionable commands
        Handles conversational phrases like "Could you please..."
        Args:
            command: Raw natural language input
        Returns: Normalized command string
        """
        command_lower = command.lower()
        
        # Remove politeness words and filler phrases
        polite_words = ["could you", "can you", "please", "would you", "will you", "for me", 
                        "i would like", "i want to", "i need to", "help me", "assist me"]
        
        for phrase in polite_words:
            command_lower = command_lower.replace(phrase, "")
        
        # Remove question words
        question_words = ["what's", "what is", "how do i", "how to", "tell me", "show me", "check"]
        for word in question_words:
            command_lower = command_lower.replace(word, "")
        
        # WiFi/Bluetooth commands
        if "wifi" in command_lower or "wi-fi" in command_lower or "wireless" in command_lower:
            return "wifi"
        
        if "bluetooth" in command_lower:
            return "bluetooth"
        
        # Control Panel
        if "control panel" in command_lower:
            return "control panel"
        
        # Media control commands - NEW
        if any(word in command_lower for word in ["play", "pause", "resume"]):
            # Check if it's a play/pause command (not "play music" which opens an app)
            if "music" not in command_lower and "song" not in command_lower and "spotify" not in command_lower:
                return "media play pause"
        
        if any(phrase in command_lower for phrase in ["next song", "next track", "skip song", "skip track", "skip", "next"]):
            # Make sure it's not "skip to next page" or similar
            if "song" in command_lower or "track" in command_lower or "music" in command_lower or (command_lower.strip() in ["skip", "next"]):
                return "media next"
        
        if any(phrase in command_lower for phrase in ["previous song", "previous track", "last song", "back", "go back"]):
            if "song" in command_lower or "track" in command_lower or "music" in command_lower:
                return "media previous"
        
        if "stop music" in command_lower or "stop song" in command_lower or "stop playing" in command_lower:
            return "media stop"
        
        # Normalize volume commands FIRST (before shutdown check to avoid confusion)
        if any(word in command_lower for word in ["volume", "sound", "audio"]):
            if any(word in command_lower for word in ["down", "lower", "decrease", "quiet", "softer", "quieter"]):
                return "volume down"
            elif any(word in command_lower for word in ["up", "raise", "increase", "louder", "higher"]):
                return "volume up"
            elif any(word in command_lower for word in ["mute", "silence", "off"]):
                return "volume mute"
        
        # Normalize brightness commands
        if any(word in command_lower for word in ["brightness", "screen"]):
            if any(word in command_lower for word in ["down", "lower", "decrease", "dim", "darker"]):
                return "brightness down"
            elif any(word in command_lower for word in ["up", "raise", "increase", "brighten", "brighter"]):
                return "brightness up"
        
        # Close/terminate commands - NEW
        if any(word in command_lower for word in ["close", "terminate", "kill", "quit", "stop"]):
            # Don't confuse with "stop listening" command
            if "listening" not in command_lower and "mic" not in command_lower:
                words = command_lower.split()
                trigger_words = ["close", "terminate", "kill", "quit", "stop"]
                
                for trigger in trigger_words:
                    if trigger in words:
                        trigger_idx = words.index(trigger)
                        if trigger_idx + 1 < len(words):
                            # Get all words after the trigger
                            app_name_parts = words[trigger_idx + 1:]
                            app_name = " ".join(app_name_parts).strip()
                            
                            # Check if any known app is in the extracted text
                            for app in self.app_keywords:
                                if app in app_name:
                                    return f"close {app}"
                            
                            # If no exact match, return the full extracted name
                            return f"close {app_name}"
        
        # Open/launch commands - IMPROVED
        if any(word in command_lower for word in ["open", "launch", "start", "run"]):
            # Extract everything after the open/launch/start/run word
            words = command_lower.split()
            trigger_words = ["open", "launch", "start", "run"]
            
            for trigger in trigger_words:
                if trigger in words:
                    trigger_idx = words.index(trigger)
                    if trigger_idx + 1 < len(words):
                        # Get all words after the trigger
                        app_name_parts = words[trigger_idx + 1:]
                        app_name = " ".join(app_name_parts).strip()
                        
                        # Check if any known app is in the extracted text
                        for app in self.app_keywords:
                            if app in app_name:
                                return f"open {app}"
                        
                        # If no exact match, return the full extracted name
                        return f"open {app_name}"
        
        # Search/find commands
        if any(word in command_lower for word in ["find", "search", "locate", "look for"]):
            # Extract filename (no longer requires the literal word "file"/"document" -
            # "find myword.doc" should work just as well as "find my file called myword.doc")
            words = command_lower.split()
            for i, word in enumerate(words):
                if word in ["find", "search", "locate", "look"]:
                    if i + 1 < len(words):
                        filename = " ".join(words[i+1:])
                        for stopword in ["for", "file", "document", "the", "a", "my"]:
                            filename = re.sub(rf'\b{stopword}\b', '', filename)
                        filename = " ".join(filename.split()).strip(' ?!.,')
                        if filename:
                            return f"find {filename}"
        
        # Time/Date queries
        if any(phrase in command_lower for phrase in ["time", "what time", "current time"]):
            return "what time"
        if any(phrase in command_lower for phrase in ["date", "what date", "today", "what day"]):
            return "what date"
        
        # Battery queries
        if any(word in command_lower for word in ["battery", "charge", "power"]):
            return "battery"
        
        # System info queries
        if any(phrase in command_lower for phrase in ["system info", "cpu usage", "ram usage", "memory", "performance"]):
            return "system info"
        
        # Screenshot
        if any(word in command_lower for word in ["screenshot", "capture", "snap", "screen shot"]):
            return "screenshot"
        
        # Lock/sleep/shutdown - MORE SPECIFIC CHECKS to avoid false matches
        if "lock" in command_lower and "computer" in command_lower:
            return "lock computer"
        if "sleep" in command_lower and not any(word in command_lower for word in ["volume", "brightness"]):
            return "sleep"
        if "restart" in command_lower or "reboot" in command_lower:
            return "restart"
        # Only trigger shutdown if explicit shutdown/shut down words are present (not "down" alone)
        if ("shutdown" in command_lower or "shut down" in command_lower or "turn off computer" in command_lower) and not any(word in command_lower for word in ["volume", "brightness"]):
            return "shutdown"
        
        # Weather
        if "weather" in command_lower:
            return "weather"
        
        # Calculator - require an actual arithmetic pattern (digit-operator-digit),
        # not just any of these characters appearing anywhere in the message. That
        # used to hijack ordinary sentences containing a hyphen/slash/percent sign
        # (e.g. "GPU-only", "and/or", "50% done") into a lowercased pass-through,
        # bypassing everything else that should have handled them (like notes).
        if (any(word in command_lower for word in ["calculate", "compute", "math"])
                or re.search(r'\d\s*[+\-*/%]\s*\d', command_lower)):
            return command_lower
        
        # Notes - check "show notes" BEFORE "add note" (a bare "note" trigger used
        # to catch "show notes" too, since "note" is a substring of "notes", and
        # order matters here since these are sequential if/return, not elif)
        if any(phrase in command_lower for phrase in ["show notes", "view notes", "my notes", "read notes"]):
            return "show notes"

        note_trigger_phrases = ["add note", "take note", "write note", "save note", "note that"]
        if any(phrase in command_lower for phrase in note_trigger_phrases):
            # Strip the trigger phrase from the ORIGINAL (not lowercased) command so
            # the saved note keeps its real capitalization
            note_text = command
            for phrase in note_trigger_phrases:
                note_text = re.sub(re.escape(phrase), "", note_text, flags=re.IGNORECASE)
            note_text = note_text.strip()
            if note_text:
                return f"add note {note_text}"

        # Read/summarize file contents - "what does X say", "what's in X", "read X (to me)"
        read_content_triggers = ["what does", "what's in", "what is in", "read "]
        if (any(t in command_lower for t in read_content_triggers)
                and "note" not in command_lower and "todo" not in command_lower):
            filename = command_lower
            for phrase in ["what does", "what's in", "what is in", "tell me", "read",
                            "say exactly", "say", "to me", "for me", "contents of",
                            "content of", "exactly"]:
                filename = re.sub(rf'\b{re.escape(phrase)}\b', '', filename)
            filename = " ".join(filename.split()).strip(' ?!.,')
            if filename:
                return f"readfile {filename}"

        # Image generation - longest/most-specific phrases first so a shorter
        # trigger (like "draw me") doesn't leave a fragment of a longer one behind.
        # Bare "generate a "/"draw a " catch phrasing without an "image/picture of"
        # qualifier (e.g. "generate a cat on a beach") - safe to match broadly since
        # "generate"/"draw" aren't used by any other FreesIA command. "create"/"make"
        # deliberately stay qualifier-only below, since bare "create a "/"make a "
        # would collide with "create folder"/"create shortcut"/"create task".
        image_gen_triggers = [
            "generate an image of", "generate a picture of", "generate a photo of", "generate image of",
            "draw me a picture of", "draw a picture of", "draw an image of", "draw me",
            "create an image of", "create a picture of", "create a photo of",
            "make an image of", "make a picture of", "make a photo of",
            "generate a ", "generate an ", "draw a ", "draw an ",
        ]
        if any(t in command_lower for t in image_gen_triggers):
            # Strip from the ORIGINAL (not lowercased) command so the prompt keeps
            # its real capitalization - matters for named subjects/styles
            prompt_text = command
            for phrase in image_gen_triggers:
                prompt_text = re.sub(re.escape(phrase), "", prompt_text, count=1, flags=re.IGNORECASE)
            prompt_text = prompt_text.strip(' ?!.,')
            if prompt_text:
                return f"generateimage {prompt_text}"

        # Image editing - "edit it/that/the (last) image to X" edits the most
        # recently generated image; "edit <filename> to X" edits a named file
        # found on disk (covers uploaded/existing photos). Check the "last image"
        # phrasing first since it's more specific and would otherwise get
        # swallowed by the generic filename pattern below (e.g. "edit it to X"
        # would parse "it" as a filename).
        edit_last_triggers = ["edit it to", "edit that to", "edit the image to", "edit that image to",
                               "edit the picture to", "edit that picture to", "edit the last image to"]
        if any(t in command_lower for t in edit_last_triggers):
            prompt_text = command
            for phrase in edit_last_triggers:
                prompt_text = re.sub(re.escape(phrase), "", prompt_text, count=1, flags=re.IGNORECASE)
            prompt_text = prompt_text.strip(' ?!.,')
            if prompt_text:
                return f"editlast {prompt_text}"

        edit_file_match = re.search(r'\bedit\s+(.+?)\s+to\s+(.+)', command, flags=re.IGNORECASE)
        if edit_file_match:
            filename = edit_file_match.group(1).strip(' ?!.,')
            change = edit_file_match.group(2).strip(' ?!.,')
            if filename and change:
                return f"editfile {filename}::{change}"

        # To-do list
        todo_trigger_phrases = ["add todo", "add task", "new task", "create task"]
        if any(phrase in command_lower for phrase in todo_trigger_phrases):
            # Strip from the ORIGINAL (not lowercased) command so the saved task
            # keeps its real capitalization
            task = command
            for phrase in todo_trigger_phrases:
                task = re.sub(re.escape(phrase), "", task, flags=re.IGNORECASE)
            task = task.strip()
            if task:
                return f"add todo {task}"
        
        if any(phrase in command_lower for phrase in ["show todo", "show tasks", "my tasks", "to do list"]):
            return "show todo"
        
        # Timer
        if "timer" in command_lower:
            return command_lower
        
        # Return original if no match
        return command.strip()
    
    # ==================== COMMAND PROCESSING ====================
    
    def process_command(self, command: str, from_shortcut: bool = False):
        """Main command processing pipeline"""
        if not command:
            return
        
        # Parse command FIRST before wake word check
        parsed_command = self.parse_natural_language(command)
        command_lower = parsed_command.lower()
        
        # Check for custom shortcuts FIRST (unless called from shortcut execution to avoid recursion)
        if not from_shortcut:
            # Check if this is a shortcut execution command
            if command_lower.startswith("run ") or command_lower.startswith("execute "):
                shortcut_name = command_lower.replace("run ", "").replace("execute ", "").strip()
                result = self.execute_shortcut(shortcut_name)
                if result:
                    print(result)
                    self.speak(result)
                    return
            
            # Direct shortcut name (e.g., just "work" or "gaming")
            if command_lower in self.custom_shortcuts:
                result = self.execute_shortcut(command_lower)
                if result:
                    print(result)
                    self.speak(result)
                    return
        
        # Shortcut management commands
        if command_lower.startswith("create shortcut ") or command_lower.startswith("add shortcut "):
            # Usage: "create shortcut work: open chrome, open spotify"
            parts = command_lower.replace("create shortcut ", "").replace("add shortcut ", "").split(":", 1)
            if len(parts) == 2:
                name = parts[0].strip()
                actions = [action.strip() for action in parts[1].split(",")]
                result = self.add_shortcut(name, actions)
                print(result)
                self.speak(result)
                return
            else:
                msg = "Usage: create shortcut [name]: [action1, action2, ...]"
                print(f"{self.name}: {msg}")
                self.speak(msg)
                return
        
        if command_lower.startswith("remove shortcut ") or command_lower.startswith("delete shortcut "):
            name = command_lower.replace("remove shortcut ", "").replace("delete shortcut ", "").strip()
            result = self.remove_shortcut(name)
            print(result)
            self.speak(result)
            return
        
        if command_lower in ["list shortcuts", "show shortcuts", "my shortcuts"]:
            result = self.list_shortcuts()
            print(result)
            self.speak(f"You have {len(self.custom_shortcuts)} custom shortcut(s).")
            return
        
        # Only check wake word if it's NOT a file search/read command or an explicit
        # logo request (to avoid a filename, or "freesia" in the phrase, triggering
        # the wake word instead of the intended action)
        is_logo_request = "logo" in command_lower
        if (not command_lower.startswith(("find ", "readfile ", "generateimage ", "editlast ", "editfile "))
                and not is_logo_request and self.check_wake_word(command)):
            self.respond_to_wake_word()
            self.wake_word_triggered = True
            return
        
        # TTS control - Updated with separate on/off commands
        if command_lower in ["tts on", "speech on", "enable tts", "turn on tts"]:
            self.enable_tts()
            return
        
        if command_lower in ["tts off", "speech off", "disable tts", "turn off tts"]:
            self.disable_tts()
            return
        
        if command_lower == "toggle tts":
            self.toggle_tts()
            return
        
        # Mic control - PRIORITIZE to avoid confusion with other commands
        if command_lower in ["mic on", "microphone on", "start listening"]:
            self.start_listening_background()
            return
        
        if command_lower in ["mic off", "microphone off", "stop listening"]:
            self.stop_listening()
            return

        # Push-to-talk key binding
        if command_lower.startswith(("set ptt key ", "set push to talk key ", "bind ptt key ", "bind mic key ")):
            for prefix in ("set ptt key ", "set push to talk key ", "bind ptt key ", "bind mic key "):
                if command_lower.startswith(prefix):
                    key_name = command_lower[len(prefix):].strip()
                    break
            self.set_ptt_key(key_name)
            return

        if command_lower in ["ptt key", "push to talk key", "what is my ptt key", "current ptt key"]:
            message = f"Push-to-talk is bound to [{self.ptt_key_name}]."
            print(f"{self.name}: {message}")
            self.speak(message)
            return

        # WiFi/Bluetooth/Control Panel - NEW
        if command_lower == "wifi":
            self.toggle_wifi()
            return
        
        if command_lower == "bluetooth":
            self.toggle_bluetooth()
            return
        
        if command_lower == "control panel":
            self.open_control_panel()
            return
        
        # Media controls - NEW
        if command_lower == "media play pause":
            self.media_play_pause()
            return
        
        if command_lower == "media next":
            self.media_next()
            return
        
        if command_lower == "media previous":
            self.media_previous()
            return
        
        if command_lower == "media stop":
            self.media_stop()
            return
        
        # Show logo (only when explicitly requested, not on every launch)
        if "logo" in command_lower:
            display_logo_image()
            return

        # Full rescan of installed apps (deliberate, on-demand only - never automatic)
        if command_lower in ["rescan apps", "refresh apps", "rescan applications", "update app list"]:
            self.rescan_apps()
            return

        # List apps
        if "list apps" in command_lower or "show apps" in command_lower:
            print(f"\n{self.name}: Detected Applications ({len(self.installed_apps)}):")
            for i, app in enumerate(sorted(self.installed_apps.keys()), 1):
                print(f"  {i}. {app}")
            print()
            return
        
        # Category help
        category_keywords = ["voice", "system", "file", "files", "web", "app", "apps",
                            "media", "productivity", "clipboard", "security", "privacy", "ai", "conversation", "other"]
        if (not command_lower.startswith(("find ", "readfile ", "open ", "generateimage ", "editlast ", "editfile "))
                and any(k in command_lower for k in category_keywords)
                and len(command_lower.split()) <= 2):
            print(self.get_category_help(command_lower))
            return
        
        # Skip spell-correction for free-text content commands - fuzzy-matching each
        # word against the command vocabulary was silently rewriting ordinary words
        # in note/todo text into unrelated keywords (e.g. "not" -> "note", or worse,
        # mangling text enough to accidentally match a completely different command)
        if (parsed_command.lower().startswith(("add note ", "add todo ", "generateimage ", "editlast ", "editfile "))
                or parsed_command.lower() in ("show notes", "show todo")):
            corrected_command = parsed_command
        else:
            corrected_command = self.correct_command(parsed_command)
        command_lower = corrected_command.lower()

        # Permissions
        if "show permissions" in command_lower:
            self.show_permissions()
        elif "revoke permissions" in command_lower:
            self.revoke_permissions()
        # AI Control Commands
        elif "clear ai history" in command_lower or "clear conversation" in command_lower:
            self.clear_ai_history()
        elif "reload personality" in command_lower:
            self.reload_personality()
        elif command_lower.startswith("change model ") or command_lower.startswith("switch model "):
            model_name = command_lower.replace("change model ", "").replace("switch model ", "").strip()
            if model_name:
                self.change_ai_model(model_name)
        # Volume - PRIORITIZE over shutdown to avoid confusion
        elif "volume" in command_lower:
            self.adjust_volume(command_lower)
        # Brightness - PRIORITIZE
        elif "brightness" in command_lower:
            self.adjust_brightness(command_lower)
        # Close app - NEW (before open to prioritize)
        elif "close" in command_lower:
            words = corrected_command.lower().split()
            if "close" in words:
                app_name = " ".join(words[words.index("close") + 1:])
                if app_name:
                    self.close_application(app_name)
        # System
        elif "battery" in command_lower:
            # Smart detection: check if they want settings or status
            if "open" in command_lower or "settings" in command_lower:
                subprocess.run(["start", "ms-settings:batterysaver"], shell=True)
                print(f"{self.name}: Opening battery settings")
            else:
                self.get_battery_status()
        elif "system info" in command_lower:
            # Smart detection: check if they want settings or info
            if "open" in command_lower or "settings" in command_lower:
                subprocess.run(["start", "ms-settings:"], shell=True)
                print(f"{self.name}: Opening Windows Settings")
            else:
                self.get_system_info()
        elif "screenshot" in command_lower:
            # Smart detection: check if they want to open folder or take screenshot
            if "open" in command_lower or "folder" in command_lower or "view" in command_lower:
                screenshots_dir = Path.home() / "Pictures" / "Screenshots"
                if screenshots_dir.exists():
                    os.startfile(screenshots_dir)
                    print(f"{self.name}: Opening screenshots folder")
                else:
                    print(f"{self.name}: Screenshots folder not found")
            else:
                self.take_screenshot()
        elif "lock" in command_lower and "computer" in command_lower:
            self.lock_computer()
        elif "sleep" in command_lower:
            self.sleep_computer()
        elif "restart" in command_lower:
            self.shutdown_computer(restart=True)
        elif "shutdown" in command_lower:
            self.shutdown_computer(restart=False)
        # Notes
        elif command_lower.startswith("add note "):
            note_text = corrected_command[len("add note "):].strip()
            if note_text:
                self.notes.append({
                    'text': note_text,
                    'timestamp': datetime.datetime.now().isoformat()
                })
                self.save_data()
                message = f"Noted: {note_text}"
                print(f"{self.name}: {message}")
                self.speak("Got it, noted.")
                return message
        elif command_lower == "show notes":
            if self.notes:
                print(f"\n{self.name}: Your notes ({len(self.notes)}):")
                for i, note in enumerate(self.notes, 1):
                    print(f"  {i}. {note['text']}")
                self.speak(f"You have {len(self.notes)} note(s).")
            else:
                message = "No notes yet."
                print(f"{self.name}: {message}")
                self.speak(message)
        # To-do list
        elif command_lower.startswith("add todo "):
            task_text = corrected_command[len("add todo "):].strip()
            if task_text:
                self.todo_list.append({
                    'task': task_text,
                    'done': False,
                    'timestamp': datetime.datetime.now().isoformat()
                })
                self.save_data()
                message = f"Added to your to-do list: {task_text}"
                print(f"{self.name}: {message}")
                self.speak("Added to your to-do list.")
                return message
        elif command_lower == "show todo":
            if self.todo_list:
                print(f"\n{self.name}: Your to-do list ({len(self.todo_list)}):")
                for i, item in enumerate(self.todo_list, 1):
                    status = "✓" if item.get('done') else " "
                    print(f"  {i}. [{status}] {item['task']}")
                self.speak(f"You have {len(self.todo_list)} task(s).")
            else:
                message = "Your to-do list is empty."
                print(f"{self.name}: {message}")
                self.speak(message)
        # Files
        elif "recent files" in command_lower:
            self.get_recent_files()
        elif "create folder" in command_lower:
            folder_name = command_lower.split("create folder")[1].strip()
            if folder_name:
                self.create_folder(folder_name)
        # Web
        elif "open website" in command_lower or any(site in command_lower for site in ["youtube", "gmail", "google"]):
            self.open_website(command_lower)
        # Weather - smart detection
        elif "weather" in command_lower:
            # If they want to OPEN weather website, do that instead
            if "open" in command_lower or "website" in command_lower:
                webbrowser.open("https://weather.com")
                print(f"{self.name}: Opening weather.com")
            else:
                # Otherwise get real weather data
                self.get_weather()
        elif "what time" in command_lower:
            return self.get_time()  # Return the time message
        elif "what date" in command_lower:
            return self.get_date()  # Return the date message
        # File search
        elif "find" in command_lower or "search" in command_lower:
            words = corrected_command.split()
            idx = next((i for i, w in enumerate(words) if w.lower() in ["find", "search"]), -1)
            filename = " ".join(words[idx+1:]).replace("for", "").strip() if idx != -1 else ""
            if filename:
                results = self.search_file(filename)
                if results:
                    print(f"\n{self.name}: Found {len(results)} file(s):")
                    for i, file in enumerate(results, 1):
                        print(f"  {i}. {file}")
                    top_match = results[0]
                    if self.open_file(top_match):
                        message = f"Found it. Opening {top_match.name}."
                        if len(results) > 1:
                            message += f" ({len(results) - 1} other match(es) also found.)"
                    else:
                        message = f"Found {top_match.name}, but couldn't open it."
                    self.speak(message)
                    return message
                else:
                    message = f"{filename}? Can't find it."
                    print(f"{self.name}: {message}")
                    self.speak(message)
                    return message
        # Read/summarize file contents
        elif command_lower.startswith("readfile "):
            filename = corrected_command[len("readfile "):].strip()
            if filename:
                results = self.search_file(filename)
                if not results:
                    message = f"Can't find a file matching '{filename}'."
                    print(f"{self.name}: {message}")
                    self.speak(message)
                    return message
                target = results[0]
                content = self.extract_file_text(target)
                if content is None:
                    message = f"Found {target.name}, but I can't read that file type yet."
                    print(f"{self.name}: {message}")
                    self.speak(message)
                    return message
                if not content:
                    message = f"Found {target.name}, but it looks empty."
                    print(f"{self.name}: {message}")
                    self.speak(message)
                    return message
                print(f"{self.name}: Reading {target.name}...")
                response = self.read_file_and_respond(target, content)
                print(f"{self.name}: {response}")
                self.speak(response)
                return response
        # Image generation (console path - synchronous; the GUI wraps
        # generate_image() in its own background thread for inline display)
        elif command_lower.startswith("generateimage "):
            prompt = corrected_command[len("generateimage "):].strip()
            if prompt:
                return self._run_generate_image_command(prompt)
        # Image editing (console path - synchronous; the GUI wraps edit_image()
        # in its own background thread)
        elif command_lower.startswith("editlast "):
            prompt = corrected_command[len("editlast "):].strip()
            if prompt:
                return self._run_edit_last_image_command(prompt)
        elif command_lower.startswith("editfile "):
            rest = corrected_command[len("editfile "):]
            if "::" in rest:
                filename, edit_prompt = rest.split("::", 1)
                filename = filename.strip()
                edit_prompt = edit_prompt.strip()
                results = self.search_file(filename) if filename else []
                if not results:
                    message = f"Can't find a file matching '{filename}'."
                    print(f"{self.name}: {message}")
                    self.speak(message)
                    return message
                target = results[0]
                message = f"Editing {target.name}: '{edit_prompt}'... this may take a moment."
                print(f"{self.name}: {message}")
                self.speak("Editing that now.")
                result = self.edit_image(edit_prompt, target)
                if result["success"]:
                    self.open_file(result["path"])
                    message = f"Done. Opened the edited image ({result['path'].name})."
                    print(f"{self.name}: {message}")
                    self.speak("Done.")
                    return message
                else:
                    message = f"Couldn't edit that: {result['error']}"
                    print(f"{self.name}: {message}")
                    self.speak("Image editing failed.")
                    return message
        # Open app
        elif "open" in command_lower:
            words = corrected_command.lower().split()
            if "open" in words:
                app_name = " ".join(words[words.index("open") + 1:])
                app_name = self._clean_target_name(app_name)
                if app_name:
                    folder_result = self.open_system_folder(app_name)
                    if folder_result is not None:
                        return folder_result
                    result = self.open_application(app_name)
                    return result if result else f"Opening {app_name}."
        # Help - also triggers on bare "command"/"commands" ("command list",
        # "show commands") without the word "help", since those are common
        # phrasings on their own and previously fell all the way through to
        # the generic "Done." acknowledgment instead of showing anything.
        elif "help" in command_lower or "command" in command_lower:
            # Check if they're asking for specific help or command list
            if any(word in command_lower for word in ["command", "list", "all", "show", "what can", "available"]):
                # Show full command list
                help_text = self.get_full_command_list()
                print(help_text)
                self.speak("I've displayed all available commands in the chat.")
                return help_text  # Return for GUI display
            elif any(word in command_lower for word in ["voice", "mic", "speech", "tts"]):
                help_text = self.get_category_help("voice")
                print(help_text)
                return help_text
            elif "system" in command_lower:
                help_text = self.get_category_help("system")
                print(help_text)
                return help_text
            elif "file" in command_lower:
                help_text = self.get_category_help("files")
                print(help_text)
                return help_text
            elif "web" in command_lower:
                help_text = self.get_category_help("web")
                print(help_text)
                return help_text
            elif "app" in command_lower:
                help_text = self.get_category_help("apps")
                print(help_text)
                return help_text
            elif "media" in command_lower:
                help_text = self.get_category_help("media")
                print(help_text)
                return help_text
            elif "ai" in command_lower or "conversation" in command_lower:
                help_text = self.get_category_help("ai")
                print(help_text)
                return help_text
            elif "security" in command_lower or "privacy" in command_lower:
                help_text = self.get_category_help("security")
                print(help_text)
                return help_text
            elif "shortcut" in command_lower:
                help_text = self.get_category_help("shortcuts")
                print(help_text)
                return help_text
            else:
                # Generic help - ask what they need
                help_text = self.show_help()
                print(help_text)
                self.speak("What kind of help do you need?")
                return help_text
        else:
            # Before falling to general chat: if an image exists in context,
            # check whether this message is actually a natural-language image
            # request/edit ("gimme a pic of a dog", "make the apple more red")
            # that didn't match one of the explicit trigger phrases above.
            if self._image_context_is_fresh():
                intent = self.classify_image_intent(command)
                if intent and intent["action"] == "generate":
                    return self._run_generate_image_command(intent["prompt"])
                elif intent and intent["action"] == "edit":
                    return self._run_edit_last_image_command(intent["change"])

            # If no specific command matched, use AI for conversation
            response = self.chat_with_ai(command)
            print(f"{self.name}: {response}")
            # Speak the response if TTS is enabled
            self.speak(response)
    
    def show_help(self):
        """Display available help options"""
        return """What kind of help do you need? I can show you:

📋 **Command List** - Type "show commands" or "command list"
🎙️ **Voice Control** - Voice commands and settings
💻 **System** - System control and monitoring
📁 **Files** - File management commands
🌐 **Web** - Web browsing and online services
📱 **Apps** - Application control
🎵 **Media** - Media playback controls
⚡ **Shortcuts** - Your custom shortcuts
🖼️ **Images** - Generate/edit images in chat
🤖 **AI Chat** - Conversation, memory, and personality settings
🔒 **Security** - Privacy and security settings

Just ask me naturally, like:
• "Show me all commands"
• "Help with voice control"
• "What system commands are there?"

Or just chat with me - I'm here to help! 💬"""
    
    def get_full_command_list(self):
        """Get complete categorized command list"""
        return """# FreesIA Command Reference

## 🎙️ Voice Control
• **FreesIA** - Wake word to activate
• **mic on / mic off** - Start/stop continuous listening
• **tts on / tts off** - Enable/disable voice responses

## 💻 System Commands
• **battery** - Check battery status
• **system info** - View CPU, RAM, and disk usage
• **screenshot** - Capture screen
• **volume up / down / mute** - Adjust volume
• **brightness up / down** - Adjust screen brightness
• **wifi** - Open WiFi settings
• **bluetooth** - Open Bluetooth settings
• **control panel** - Open Control Panel
• **lock / sleep / shutdown / restart** - Power options
• **weather** - Get current weather

## 📁 File & Folder Management
• **find [filename]** - Search for files
• **recent files** - Show recently accessed files
• **create folder [name]** - Create new folder
• **open [filename]** - Open a file
• **open the downloads / documents / desktop / pictures / music / videos folder** - Open a system folder
• **open [folder name]** - Open a folder found by Rescan Folders (Settings → General), e.g. any named folder on your Desktop

## 🌐 Web & Communication
• **open youtube / gmail / google** - Quick website access
• **what time** - Current time
• **what date** - Today's date
• **open [website]** - Open any website

## 📱 Application Control
• **open [app name]** - Launch application (handles Electron/Squirrel apps like Discord/Claude correctly, and MSIX/Store apps too)
• **close [app name]** - Close application
• **list apps** - Show installed apps
• **rescan apps** - Refresh the installed-app list (Settings → General has a button too)

## 🎵 Media Controls
• **play / pause** - Toggle playback
• **next / skip** - Next track
• **previous / back** - Previous track
• **stop** - Stop playback

## ⚡ Custom Shortcuts
• **[shortcut name]** - Run your custom shortcut
• **list shortcuts** - View all shortcuts
• **create shortcut [name]: [action1, action2]** - Create new
• **delete shortcut [name]** - Remove shortcut

## 🖼️ Image Generation (GUI)
• **generate/draw a picture of [X]** - Create an image inline in chat
• Just describe a change ("make the sky red") to edit the last generated or uploaded image - no separate edit command needed
• Say how many you want ("3 pictures of...") or a size word (landscape/portrait/square) right in the prompt
• Each generated image has its own download / regenerate / delete buttons and a size picker (1:1, 16:9 H, 16:9 V) in the chat
• **Delete Generated Images** (Settings → General) - bulk-clear everything at once

## 💬 Chat Features (GUI)
• Click the pencil on your own message to edit it and regenerate what followed
• Click ⟳ under any AI reply to regenerate it - previous versions stay reachable with ‹ › arrows
• 👎 under a reply asks for a more decisive answer without you having to type a correction
• Chats get an automatic short title after the first exchange, like ChatGPT/Claude
• **Export Current Chat** (Settings → General) - save a chat to a text file
• FreesIA remembers durable facts you mention (name, preferences, ongoing things) across ALL chats, not just the current one - see Memory in Settings → General

## 🤖 AI Conversation
• Just chat naturally - I understand context!
• **clear ai history** - Reset conversation
• **reload personality** - Reload personality from file
• **change model [name]** - Switch AI model
• **Enable personality** (Settings → General) - toggle the custom persona on/off, on by default

## 🎨 Appearance
• **Dark mode** (Settings → General) - with a Restart Now button so it applies immediately

## 🔒 Security & Settings
• **settings** - Open settings dialog
• **show permissions** - View current permissions
• **revoke permissions** - Reset all permissions

## ⚙️ Other
• **help** - Show this guide
• **command list / show commands** - Show this reference
• **quit / exit** - Close FreesIA

---
💡 **Tip:** You don't need exact commands - just ask naturally!
Example: "Can you find my resume?" or "Open Spotify please"
"""
    
    def get_category_help(self, category: str):
        """Get help for specific category"""
        cat = category.lower()
        
        if "voice" in cat or "mic" in cat or "speech" in cat or "tts" in cat:
            return """# 🎙️ Voice Control Commands

**Activation:**
• **FreesIA** - Wake word (say this to activate listening)

**Microphone Control:**
• **mic on** / **start listening** - Start continuous voice mode
• **mic off** / **stop listening** - Stop voice mode

**Speech Output:**
• **tts on** / **speech on** - Enable voice responses
• **tts off** / **speech off** - Disable voice responses
• **toggle tts** - Switch TTS on/off

**Tips:**
• Voice recognition works offline with Vosk
• Say "FreesIA" to wake me up in continuous mode
• I'll respond with voice when TTS is enabled"""
        
        elif "system" in cat:
            return """# 💻 System Commands

**Monitoring:**
• **battery** - Check battery level and status
• **system info** - View CPU, RAM, disk usage

**Screen & Display:**
• **screenshot** - Capture entire screen
• **brightness up / brighten** - Increase brightness
• **brightness down / dim** - Decrease brightness

**Audio:**
• **volume up / increase volume** - Raise volume
• **volume down / decrease volume** - Lower volume  
• **mute / unmute** - Toggle mute

**Settings:**
• **wifi** - Open WiFi settings
• **bluetooth** - Open Bluetooth settings
• **control panel** - Open Windows Control Panel

**Power:**
• **lock** - Lock computer
• **sleep** - Put computer to sleep
• **shutdown** - Shut down computer
• **restart** - Restart computer

**Information:**
• **weather** - Get current weather for your location
• **what time** - Current time
• **what date** - Today's date"""
        
        elif "file" in cat:
            return """# 📁 File Management Commands

**Search:**
• **find [filename]** - Search for files on your computer
• **search [filename]** - Alternative search command

**Recent Files:**
• **recent files** - Show recently opened/modified files

**Create:**
• **create folder [name]** - Create new folder

**Open:**
• **open [filename]** - Open a specific file

**Tips:**
• File search looks in Desktop, Documents, and Downloads
• You can use partial names: "find resume" finds any file with "resume"""
        
        elif "web" in cat:
            return """# 🌐 Web & Communication Commands

**Quick Access:**
• **open youtube** - Open YouTube
• **open gmail** - Open Gmail
• **open google** - Open Google Search

**General:**
• **open [website name]** - Open any website

**Time & Date:**
• **what time** - Get current time
• **what date** - Get today's date

**Examples:**
• "Open Reddit"
• "Go to Twitter"
• "Open Wikipedia"""
        
        elif "app" in cat:
            return """# 📱 Application Control Commands

**Launch Apps:**
• **open [app name]** - Launch any installed application
  Examples:
  - "Open Chrome"
  - "Open Spotify"
  - "Open VS Code"

**Close Apps:**
• **close [app name]** - Close running application

**View Apps:**
• **list apps** - Show all installed applications

**Tips:**
• I automatically scan for installed apps at startup
• Fuzzy matching helps - "chrome" finds "Google Chrome"
• Apps are displayed in Settings → Apps page"""
        
        elif "media" in cat:
            return """# 🎵 Media Control Commands

**Playback:**
• **play** / **pause** - Toggle play/pause
• **stop** - Stop playback

**Navigation:**
• **next** / **skip** - Skip to next track
• **previous** / **back** - Go to previous track

**Tips:**
• Works with any media player (Spotify, YouTube, etc.)
• Uses system media controls
• Works even when app is in background"""
        
        elif "shortcut" in cat:
            return f"""# ⚡ Custom Shortcuts

**Your Shortcuts:** {len(self.custom_shortcuts) if hasattr(self, 'custom_shortcuts') else 0} defined

**Run Shortcut:**
• **[shortcut name]** - Execute shortcut
• **run [shortcut name]** - Alternative

**Manage Shortcuts:**
• **list shortcuts** - View all your shortcuts
• **create shortcut [name]: [action1, action2, ...]** - Create new
• **delete shortcut [name]** - Remove shortcut

**Example:**
• "create shortcut work: open chrome, open vscode, open spotify"
• Then just say "work" to run it!

**Tips:**
• Manage shortcuts in Settings → Shortcuts
• Each shortcut can have multiple actions
• Actions are executed in order with small delays"""
        
        elif "ai" in cat or "conversation" in cat:
            return f"""# 🤖 AI Conversation Features

**Natural Chat:**
• Just talk to me naturally - I understand context!
• Ask questions, request explanations, have conversations

**Examples:**
• "What is machine learning?"
• "Explain how WiFi works"
• "Tell me about Python programming"
• "What's the weather like?"

**AI Management:**
• **clear ai history** - Reset conversation memory
• **reload personality** - Reload personality from Personality.txt
• **change model [name]** - Switch Ollama model

**Current Setup:**
• Model: {self.ollama_model if hasattr(self, 'ollama_model') else 'Not loaded'}
• Status: {'Online' if hasattr(self, 'ollama_enabled') and self.ollama_enabled else 'Offline'}
• Streaming: Enabled (real-time responses)

**Tips:**
• I work completely offline with Ollama
• Edit Personality.txt to customize my personality
• I remember context within the conversation"""
        
        elif "security" in cat or "privacy" in cat:
            return """# 🔒 Security & Privacy Commands

**Settings:**
• **settings** - Open settings dialog

**Permissions:**
• **show permissions** - View current permission status
• **revoke permissions** - Reset all permissions to default

**Privacy Controls** (in Settings → Security):
• PIN Protection - Secure app with PIN
• Command Logging - View/export/clear command history
• Chat History - Manage saved conversations
• AI Memory - Clear conversation history
• Data Export - Backup all your data
• Factory Reset - Delete all data and settings

**Tips:**
• All data stored locally on your device
• No cloud sync or external data collection
• Voice recognition works offline
• AI conversations stay on your computer"""
        
        else:
            return self.show_help()
    
    def get_time(self):
        """Get current time"""
        try:
            from datetime import datetime
            current_time = datetime.now().strftime("%I:%M:%S %p")
            msg = f"Current time: {current_time}"
            print(f"{self.name}: {msg}")
            self.speak(msg)
            return msg  # Return the message for GUI display
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"{self.name}: {error_msg}")
            return error_msg
    
    def get_date(self):
        """Get current date"""
        try:
            from datetime import datetime
            current_date = datetime.now().strftime("%B %d, %Y")
            msg = f"Today's date: {current_date}"
            print(f"{self.name}: {msg}")
            self.speak(msg)
            return msg  # Return the message for GUI display
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"{self.name}: {error_msg}")
            return error_msg
    
    # ==================== LOCATION & WEATHER SERVICES ====================
    
    def get_location(self):
        """Get device location using Windows Location Services"""
        try:
            import asyncio
            from winsdk.windows.devices.geolocation import Geolocator, GeolocationAccessStatus
            
            async def get_coords():
                # Request location permission
                access_status = await Geolocator.request_access_async()
                
                if access_status != GeolocationAccessStatus.ALLOWED:
                    print(f"{self.name}: Location access denied. Please enable location in Windows Settings.")
                    return None
                
                # Get location
                locator = Geolocator()
                position = await locator.get_geoposition_async()
                
                return {
                    'latitude': position.coordinate.latitude,
                    'longitude': position.coordinate.longitude
                }
            
            # Run async function
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            location = loop.run_until_complete(get_coords())
            loop.close()
            
            return location
            
        except ImportError:
            print(f"{self.name}: Installing Windows SDK for location services...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "winsdk"])
                print(f"{self.name}: Please restart FreesIA to use location services.")
            except:
                print(f"{self.name}: Could not install Windows SDK. Weather may not work.")
            return None
        except Exception as e:
            print(f"{self.name}: Could not get location: {e}")
            return None
    
    def get_weather(self):
        """Get current weather using Windows location and OpenWeatherMap API"""
        try:
            print(f"{self.name}: Getting your location...")
            
            # Get location from Windows
            location = self.get_location()
            
            if not location:
                # Fallback: open weather.com
                print(f"{self.name}: Opening weather.com instead...")
                webbrowser.open("https://weather.com")
                return
            
            lat = location['latitude']
            lon = location['longitude']
            
            # Free OpenWeatherMap API (no key required for basic use)
            # Note: For production, get a free API key from openweathermap.org
            url = f"https://wttr.in/?format=j1"
            
            print(f"{self.name}: Fetching weather data...")
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                # Parse weather data
                current = data['current_condition'][0]
                temp_c = current['temp_C']
                temp_f = current['temp_F']
                description = current['weatherDesc'][0]['value']
                humidity = current['humidity']
                feels_like_c = current['FeelsLikeC']
                feels_like_f = current['FeelsLikeF']
                
                # Get location name
                location_name = data['nearest_area'][0]['areaName'][0]['value']
                
                # Format message
                msg = f"Weather in {location_name}: {description}, {temp_f}°F ({temp_c}°C). Feels like {feels_like_f}°F. Humidity: {humidity}%."
                
                print(f"\n{self.name}: {msg}\n")
                self.speak(f"{description}, {temp_f} degrees")
                
            else:
                print(f"{self.name}: Could not fetch weather data. Opening weather.com...")
                webbrowser.open("https://weather.com")
                
        except requests.exceptions.Timeout:
            print(f"{self.name}: Weather service timed out. Opening weather.com...")
            webbrowser.open("https://weather.com")
        except Exception as e:
            print(f"{self.name}: Weather error: {e}. Opening weather.com...")
            webbrowser.open("https://weather.com")

# ==================== MAIN PROGRAM ====================

def display_logo_image():
    """Display FreesIA logo image from project folder"""
    try:
        # Path to logo in project folder
        logo_path = Path(__file__).parent / "FreesIA Logo white.png"
        
        if logo_path.exists():
            # Open and display the image
            img = Image.open(logo_path)
            img.show()
            print("FreesIA Logo displayed!")
        else:
            print(f"Logo not found at: {logo_path}")
    except Exception as e:
        print(f"Could not display logo: {e}")

def display_logo():
    """Display FreesIA ASCII art logo"""
    logo = """
    ╔════════════════════════════════════════════════════════════════════════════════╗
    ║                                                                                ║
    ║               ███████╗██████╗ ███████╗███████╗███████╗██╗ █████╗               ║
    ║               ██╔════╝██╔══██╗██╔════╝██╔════╝██╔════╝██║██╔══██╗              ║
    ║               █████╗  ██████╔╝█████╗  █████╗  ███████╗██║███████║              ║
    ║               ██╔══╝  ██╔══██╗██╔══╝  ██╔══╝  ╚════██║██║██╔══██║              ║
    ║               ██║     ██║  ██║███████╗███████╗███████║██║██║  ██║              ║
    ║               ╚═╝     ╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝╚═╝╚═╝  ╚═╝              ║
    ║                                                                                ║
    ║ Functional & Responsive Entity for Enhanced System Intelligence Administration ║
    ║                                                                                ║
    ╚════════════════════════════════════════════════════════════════════════════════╝
    """
    try:
        print(logo)
    except UnicodeEncodeError:
        # Console codepage (e.g. cp1252) can't render the box-drawing characters
        print("\n    FreesIA - Functional & Responsive Entity for Enhanced System Intelligence Administration\n")

def main():
    """Main entry point for FreesIA assistant"""
    # Initialize assistant first (shows startup message)
    assistant = FreesIA()

    # Display ASCII art logo
    display_logo()
    
    print("\n" + "=" * 80)
    print("Welcome to FreesIA")
    print("Functional & Responsive Entity for Enhanced System Intelligence Administration")
    print("=" * 80)
    print("I can help you find files, adjust settings, and open apps.")
    print("=" * 80 + "\n")
    
    # Show help menu
    assistant.show_help()
    
    waiting_for_command = False
    response_history = []  # Store last few responses to prevent them from disappearing
    
    # Main interaction loop
    while True:
        try:
            # Show last response if available (keeps it visible)
            if response_history and len(response_history) > 0:
                print(f"\n[Last Response] {response_history[-1][:100]}..." if len(response_history[-1]) > 100 else f"\n[Last Response] {response_history[-1]}")
            
            # Change prompt based on state
            if waiting_for_command:
                user_input = input(f"{assistant.name} is listening: ").strip()
                waiting_for_command = False
            else:
                # Show microphone and TTS status in prompt - simplified
                mic_status = "🎤 ON" if assistant.listening_active else "🎤 OFF"
                tts_status = "🔊 ON" if assistant.tts_enabled else "🔊 OFF"
                user_input = input(f"\nYou [Mic: {mic_status}] [Speech: {tts_status}]: ").strip()
            
            # Skip empty inputs
            if not user_input:
                continue
            
            # Check for exit commands
            if user_input.lower() in ['quit', 'exit']:
                assistant.stop_listening()
                print(f"{assistant.name}: Goodbye! Have a great day!")
                break
            
            # Handle voice input mode
            if user_input.lower() == 'voice':
                voice_input = assistant.listen()
                if voice_input:
                    assistant.process_command(voice_input)
            elif user_input.lower() in ['history', 'show history']:
                # Show response history
                if response_history:
                    print(f"\n{assistant.name}: Last {len(response_history)} responses:")
                    for i, resp in enumerate(response_history[-5:], 1):  # Show last 5
                        print(f"  {i}. {resp[:80]}...")
                else:
                    print(f"{assistant.name}: No response history yet.")
            else:
                # Process text command
                result = assistant.process_command(user_input)

                # If that command was just the wake word, switch to the "listening" prompt
                if assistant.wake_word_triggered:
                    assistant.wake_word_triggered = False
                    waiting_for_command = True

                # Store response for history (if one was generated)
                if result:
                    response_history.append(str(result)[:200])  # Store first 200 chars
                
        except KeyboardInterrupt:
            assistant.stop_listening()
            print(f"\n{assistant.name}: Goodbye!")
            break
        except Exception as e:
            print(f"{assistant.name}: Error: {e}")

# Run the assistant when script is executed directly
if __name__ == "__main__":
    main()
