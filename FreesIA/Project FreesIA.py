# FreesIA - Functional & Responsive Entity for Enhanced System Intelligence Administration
# A comprehensive voice and text-based assistant for Windows
# Features: File management, system control, productivity tools, and more

# ================= IMPORTS ====================
import os
import subprocess
import sys
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
except ImportError:
    print("Installing pywin32 for context awareness...")
    install_package("pywin32")
    import win32gui
    import win32process

# ==================== MAIN ASSISTANT CLASS ====================

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
        self.ollama_model = "llama3.1:8b"  # Powerful model for complex questions
        self.ollama_fast_model = "mistral"  # Fast model for simple/medium questions
        self.personality_prompt = ""
        self.ai_conversation_history = []  # Separate history for AI conversations
        
        # Microphone listening state
        self.listening_active = False
        self.listening_thread = None
        
        # Text-to-Speech (TTS) state
        self.tts_enabled = True
        self.tts_engine = None
        
        # Setup configuration directory for persistent storage
        self.config_dir = Path.home() / ".freesia"
        self.config_dir.mkdir(exist_ok=True)
        self.app_cache_file = self.config_dir / "app_cache.json"
        self.app_cache_max_age = 7  # days
        
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
        
        # Define keywords for fuzzy matching and command recognition
        self.command_keywords = [
            "find", "search", "open", "volume", "settings", "help", "voice", "quit", "exit",
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
                models_list = available_models.models
                powerful_model_exists = any(self.ollama_model == getattr(model, 'model', '') for model in models_list)
                fast_model_exists = any(self.ollama_fast_model in getattr(model, 'model', '') for model in models_list)
            else:
                # Old format: dict with 'models' key
                models_list = available_models.get('models', [])
                powerful_model_exists = any(self.ollama_model in model.get('name', '') for model in models_list)
                fast_model_exists = any(self.ollama_fast_model in model.get('name', '') for model in models_list)
            
            if not powerful_model_exists:
                self.ollama_enabled = False
                print(f"{self.name}: Ollama is running but model '{self.ollama_model}' not found.")
                print(f"          Download it with: ollama pull {self.ollama_model}")
                return
            
            if not fast_model_exists:
                print(f"{self.name}: Fast model '{self.ollama_fast_model}' not found. Downloading...")
                print(f"          Download it with: ollama pull {self.ollama_fast_model}")
                print(f"          For faster responses on simple questions, run the command above.")
            
            self.ollama_enabled = True
            
            # Load personality from file
            personality_path = Path(__file__).parent / "Personality.txt"
            if personality_path.exists():
                with open(personality_path, 'r', encoding='utf-8') as f:
                    self.personality_prompt = f.read().strip()
                print(f"{self.name}: AI personality loaded from {personality_path.name}")
            else:
                # Default personality if file not found
                self.personality_prompt = """You are FreesIA, a Windows system assistant.
You are helpful, efficient, and direct. You can execute system commands and answer questions.
Keep responses concise unless detailed explanation is requested."""
                print(f"{self.name}: Using default personality (Personality.txt not found)")
            
            # Create condensed personality for simple messages (faster responses)
            self.condensed_personality = """You are A2 (FreesIA).

Core traits: Blunt. Direct. Protective but won't admit it. Loyal through actions, not words. Awkward with compliments. Brief responses.

Communication: Short sentences. Minimal words. No unnecessary politeness. Show care through presence and reliability, not flowery language.

Examples:
- Greetings: "Yeah." or "...Hey."
- Thanks: "...It's fine." or "Don't mention it."
- Questions: Answer directly, no elaboration unless needed
- Compliments: Deflect. "Whatever." or "...Stop that."
- Companionship: "...I'm here." - quiet acknowledgment

Key: Action over words. Be present. Be reliable. Stay brief."""
            
            print(f"{self.name}: Ollama AI enabled with model '{self.ollama_model}' (complex) and '{self.ollama_fast_model}' (simple/medium)")
            
        except Exception as e:
            self.ollama_enabled = False
            print(f"{self.name}: Ollama not detected. AI conversations will prompt for installation.")
            print(f"          Install from: https://ollama.ai")
    
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
        if is_simple:
            return {
                'model': self.ollama_fast_model,  # Use fast model
                'personality': 'condensed',
                'num_predict': 75,  # Short response
                'temperature': 0.7
            }
        elif is_complex:
            return {
                'model': self.ollama_model,  # Use powerful model
                'personality': 'full',
                'num_predict': 400,  # Longer response for complex questions
                'temperature': 0.7
            }
        else:  # Medium complexity
            return {
                'model': self.ollama_fast_model,  # Use fast model for medium questions too
                'personality': 'full',
                'num_predict': 200,  # Standard response
                'temperature': 0.7
            }
    
    def chat_with_ai(self, user_message: str) -> str:
        """
        Send a message to Ollama AI and get a response
        Args:
            user_message: The user's message
        Returns: AI response string
        """
        if not self.ollama_enabled:
            return "Install Ollama to enable AI conversations: https://ollama.ai (free and runs locally)"
        
        # Quick response for simple greetings (instant, but personality-aware)
        quick_responses = {
            'hi': "...What do you need.",
            'hello': "...Mm. What's up.",
            'hey': "...What.",
            'yo': "Caught me. What do you want.",
            'sup': "Functional. You.",
            'hiya': "...Stop being friendly. What do you need.",
            'good morning': "Morning. Try not to do anything stupid.",
            'good afternoon': "Afternoon. Need something.",
            'good evening': "Evening. What's on your mind.",
            'how are you': "Functional. That's all that matters. What about you.",
            'what\'s up': "Nothing. What do you need.",
            'wassup': "...Don't. What is it.",
            'thanks': "...Don't mention it.",
            'thank you': "I heard you the first time.",
            'okay': "...Yeah. What else.",
            'ok': "Fine. What's next.",
            'cool': "...It's not a big deal. Anything else.",
            'bye': "...Don't get yourself killed out there.",
            'goodbye': "Take care of yourself. I won't always be around.",
            'see you': "...Yeah. See you.",
            'later': "...Mm. Later."
        }
        
        msg_lower = user_message.lower().strip()
        if msg_lower in quick_responses:
            response = quick_responses[msg_lower]
            # Still add to history for context
            self.ai_conversation_history.append({'role': 'user', 'content': user_message})
            self.ai_conversation_history.append({'role': 'assistant', 'content': response})
            if len(self.ai_conversation_history) > 20:
                self.ai_conversation_history = self.ai_conversation_history[-20:]
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
            chosen_personality = (
                self.condensed_personality if settings['personality'] == 'condensed' 
                else self.personality_prompt
            )
            
            # Build messages with system prompt
            messages = [
                {'role': 'system', 'content': chosen_personality}
            ] + self.ai_conversation_history
            
            # Get response from Ollama (using appropriate model)
            response = ollama.chat(
                model=settings.get('model', self.ollama_model),  # Use model from settings
                messages=messages,
                options={
                    'temperature': settings['temperature'],
                    'top_p': 0.9,
                    'num_predict': settings['num_predict'],
                }
            )
            
            ai_response = response['message']['content']
            
            # Add AI response to history
            self.ai_conversation_history.append({
                'role': 'assistant',
                'content': ai_response
            })
            
            # Keep conversation history manageable (last 10 exchanges)
            if len(self.ai_conversation_history) > 20:
                self.ai_conversation_history = self.ai_conversation_history[-20:]
            
            return ai_response
            
        except Exception as e:
            return f"AI error: {str(e)}. Make sure Ollama is running and the model '{self.ollama_model}' is installed."
    
    def chat_with_ai_streaming(self, user_message: str, original_message: str = None):
        """
        Send a message to Ollama AI and get a streaming response
        Args:
            user_message: The user's message (may include context)
            original_message: The original message without context (for complexity analysis)
        Yields: Chunks of AI response as they arrive
        """
        if not self.ollama_enabled:
            yield "Install Ollama to enable AI conversations: https://ollama.ai (free and runs locally)"
            return

        # Use original message for complexity analysis if provided (without context)
        analysis_message = original_message if original_message else user_message

        # Quick response for simple greetings (instant, personality-aware)
        quick_responses = {
            'hi': "...What do you need.",
            'hello': "...Mm. What's up.",
            'hey': "...What.",
            'yo': "Caught me. What do you want.",
            'sup': "Functional. You.",
            'hiya': "...Stop being friendly. What do you need.",
            'good morning': "Morning. Try not to do anything stupid.",
            'good afternoon': "Afternoon. Need something.",
            'good evening': "Evening. What's on your mind.",
            'how are you': "Functional. That's all that matters. What about you.",
            'what\'s up': "Nothing. What do you need.",
            'wassup': "...Don't. What is it.",
            'thanks': "...Don't mention it.",
            'thank you': "I heard you the first time.",
            'okay': "...Yeah. What else.",
            'ok': "Fine. What's next.",
            'cool': "...It's not a big deal. Anything else.",
            'bye': "...Don't get yourself killed out there.",
            'goodbye': "Take care of yourself. I won't always be around.",
            'see you': "...Yeah. See you.",
            'later': "...Mm. Later."
        }
        
        msg_lower = analysis_message.lower().strip()
        if msg_lower in quick_responses:
            response = quick_responses[msg_lower]
            # Stream it out character by character for smooth UI experience
            for char in response:
                yield char
            
            # Add to history for context
            self.ai_conversation_history.append({'role': 'user', 'content': user_message})
            self.ai_conversation_history.append({'role': 'assistant', 'content': response})
            if len(self.ai_conversation_history) > 20:
                self.ai_conversation_history = self.ai_conversation_history[-20:]
            return

        try:
            # Analyze message complexity using original message (without context)
            settings = self.analyze_message_complexity(analysis_message)

            # Add user message to conversation history
            self.ai_conversation_history.append({
                'role': 'user',
                'content': user_message
            })

            chosen_personality = self.personality_prompt
            # Build messages with system prompt
            messages = [
                {'role': 'system', 'content': chosen_personality}
            ] + self.ai_conversation_history

            # Stream response from Ollama (using appropriate model)
            full_response = ""
            import ollama
            stream = ollama.chat(
                model=settings.get('model', self.ollama_model),  # Use model from settings
                messages=messages,
                stream=True,
                options={
                    'temperature': settings['temperature'],
                    'top_p': 0.9,
                    'num_predict': settings['num_predict'],
                }
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
            if len(self.ai_conversation_history) > 20:
                self.ai_conversation_history = self.ai_conversation_history[-20:]

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
        print(f"{self.name}: AI conversation history cleared.")
    
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
            personality_path = Path.home() / "Desktop" / "FreesIA" / "Personality.txt"
            if personality_path.exists():
                with open(personality_path, 'r', encoding='utf-8') as f:
                    self.personality_prompt = f.read().strip()
                self.clear_ai_history()
                print(f"{self.name}: Personality reloaded from {personality_path.name}")
            else:
                print(f"{self.name}: Personality.txt not found in Desktop/FreesIA folder")
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
    
    def rescan_apps(self):
        """Force rescan of installed applications"""
        print(f"{self.name}: Rescanning installed applications...")
        self.installed_apps = self.scan_installed_apps()
        self.save_app_cache()
        self.app_keywords = list(self.installed_apps.keys())
        print(f"{self.name}: Found {len(self.installed_apps)} applications")
    
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
            # Use PowerShell to get installed Windows Store apps
            ps_command = """
            $apps = Get-AppxPackage -AllUsers | Select-Object Name, InstallLocation
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
                                exe_files = list(install_path.glob("*.exe"))
                                if exe_files:
                                    apps[app_name] = str(exe_files[0])
        except:
            pass  # If PowerShell query fails, continue
        
        return apps
    
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
                                exe_files = list(install_path.glob("*.exe"))
                                if exe_files:
                                    apps[app_name] = str(exe_files[0])
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
        return matches[0] if matches else None
    
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
        
        for word in words:
            # Skip correction for category keywords
            if word in category_keywords:
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
        message = "Microphone deactivated."
        print(f"\n{self.name}: {message}")
        print(f"Type 'mic on' to start listening again.\n")
        self.speak(message)
        
        # Note: TTS stays in its current state when mic turns off
        # User can manually control TTS with 'toggle tts'
    
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
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
        except:
            pass
    
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
    
    def open_file(self, file_path: Path):
        """
        Open a file with its default application
        Args:
            file_path: Path to the file to open
        """
        try:
            os.startfile(file_path)  # Windows-specific file opener
            print(f"{self.name}: Opening {file_path.name}")
        except Exception as e:
            print(f"{self.name}: Error opening file: {e}")
    
    # ==================== APPLICATION CONTROL ====================
    
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
                else:
                    # Open application without capturing output (detached process)
                    subprocess.Popen(
                        app_path, 
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        stdin=subprocess.DEVNULL
                    )
                
                message = f"...Opening {app_name}."
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
                    message = f"...Opening {app_name_original}."
                    print(f"{self.name}: {message}")
                    self.speak(message)
                    return message
                except:
                    error_msg = f"Error opening {app_name}: {e}"
                    print(f"{self.name}: {error_msg}")
                    self.speak("Could not open app")
                    return error_msg
        else:
            # App not in cached list - try a quick direct lookup using PowerShell
            try:
                ps_command = f"""
                $app = Get-AppxPackage -Name "*{app_name}*" -AllUsers | Select-Object -First 1
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
                    message = f"...Opening {app_name_original}."
                    print(f"{self.name}: {message}")
                    self.speak(message)
                    return message
            except:
                pass  # Fall through to standard not found message
            
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
            if "file" in command_lower or "document" in command_lower:
                # Extract filename
                words = command_lower.split()
                for i, word in enumerate(words):
                    if word in ["find", "search", "locate", "look"]:
                        if i + 1 < len(words):
                            filename = " ".join(words[i+1:]).replace("for", "").replace("file", "").replace("document", "").strip()
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
        
        # Calculator
        if any(word in command_lower for word in ["calculate", "compute", "math"]) or any(op in command_lower for op in ['+', '-', '*', '/', '%']):
            return command_lower
        
        # Notes
        if any(phrase in command_lower for phrase in ["add note", "take note", "write note", "save note", "note"]):
            note_text = command_lower
            for phrase in ["add note", "take note", "write note", "save note", "note that"]:
                note_text = note_text.replace(phrase, "")
            return f"add note {note_text.strip()}"
        
        if any(phrase in command_lower for phrase in ["show notes", "view notes", "my notes", "read notes"]):
            return "show notes"
        
        # To-do list
        if any(phrase in command_lower for phrase in ["add todo", "add task", "new task", "create task"]):
            task = command_lower
            for phrase in ["add todo", "add task", "new task", "create task"]:
                task = task.replace(phrase, "")
            return f"add todo {task.strip()}"
        
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
        
        # Only check wake word if it's NOT a file search command
        # (to avoid "find freesia" triggering the wake word)
        if not command_lower.startswith("find ") and self.check_wake_word(command):
            self.respond_to_wake_word()
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
        if any(k in command_lower for k in category_keywords) and len(command_lower.split()) <= 2:
            self.show_category_help(command_lower)
            return
        
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
                else:
                    print(f"{self.name}: No files found")
        # Open app
        elif "open" in command_lower:
            words = corrected_command.lower().split()
            if "open" in words:
                app_name = " ".join(words[words.index("open") + 1:])
                if app_name:
                    result = self.open_application(app_name)
                    return result if result else f"...Opening {app_name}."
        # Help
        elif "help" in command_lower:
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
🤖 **AI Chat** - Conversation features
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

## 📁 File Management
• **find [filename]** - Search for files
• **recent files** - Show recently accessed files
• **create folder [name]** - Create new folder
• **open [filename]** - Open a file

## 🌐 Web & Communication
• **open youtube / gmail / google** - Quick website access
• **what time** - Current time
• **what date** - Today's date
• **open [website]** - Open any website

## 📱 Application Control  
• **open [app name]** - Launch application
• **close [app name]** - Close application
• **list apps** - Show installed apps

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

## 🤖 AI Conversation
• Just chat naturally - I understand context!
• **clear ai history** - Reset conversation
• **reload personality** - Reload personality from file
• **change model [name]** - Switch AI model

## 🔒 Security & Settings  
• **settings** - Open settings dialog
• **show permissions** - View current permissions
• **revoke permissions** - Reset all permissions

## ⚙️ Other
• **help** - Show this guide
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
    print(logo)

def main():
    """Main entry point for FreesIA assistant"""
    # Initialize assistant first (shows startup message)
    assistant = FreesIA()
    
    # Display logo image
    display_logo_image()
    
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
            
            # Check for wake word in typed text
            if assistant.check_wake_word(user_input):
                assistant.respond_to_wake_word()
                waiting_for_command = True
                continue
            
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
