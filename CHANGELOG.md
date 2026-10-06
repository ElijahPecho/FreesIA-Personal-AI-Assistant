# Changelog

All notable changes to FreesIA are documented in this file.

## [Alpha 1.0]

A major update over Pre-Alpha. The codebase roughly doubled in size, with a rebuilt interface and a large set of new features.

### Interface
- Complete UI overhaul with a new visual design across the application.
- Light and dark themes, resizable sidebar, toggle switches and themed dialogs.
- Command palette for quick access to actions.
- Redesigned settings, organised into pages with built-in search.
- Pinned messages with jump-to-message.

### Chat
- Customizable assistant: give it any name, and set its personality with built-in presets, your own character text, or a plain neutral mode.
- Long-term memory: the assistant can remember facts about the user, which can be reviewed and cleared.
- Automatic chat titles.
- Separate Ollama model slots for complex and fast replies, with automatic readiness checks and retry.
- Attach files and ask questions about their contents.

### Chat Reader
- Import chat exports, including Character.AI, into a searchable library.
- Resume reading where you left off.
- Live search, timeline slider and bookmarks.
- Large chats load in chunks to stay responsive.

### Proactive check-ins
- Optional messages from the assistant at a chosen frequency.
- Configurable quiet hours.
- Automatically paused while a fullscreen application is running.

### Voice
- Local text-to-speech voice using Piper, with downloadable voices.
- System voice fallback.
- Push-to-talk, with automatic microphone pause during calls.

### Image generation
- Image generation through FastSD CPU, with a gallery, image viewer, starring and cleanup tools.
- Edit the most recent image, with an optional high-detail second pass.
- Speed options and a built-in benchmark.
- Image safety checker toggle and configurable image model.

### System
- Option to launch with Windows.
- Improved application and folder scanning.
- Built-in diagnostics.

### Project
- Reorganised repository layout: files at the top level, documentation in `docs/`.
- Added README, MIT license, `requirements.txt` and an example persona file.
- Personal data (chat history, persona text) is excluded from version control.

### Known limitations
- This is an alpha release and may contain bugs.
- Voice features and some Windows-specific behaviour have had limited testing.

## [Pre-Alpha]

Initial public preview, showing the core direction of the project. Many features were experimental or incomplete.

### Chat
- Local AI chat through Ollama, with a persona loaded from `Personality.txt`.
- Replies stream in as they are generated.
- Messages are routed by complexity: a larger model (`llama3.1:8b`) for complex questions and a faster one (`mistral`) for simple and medium ones.
- Awareness of the active window, and a clearable AI conversation history.
- Switch the AI model and reload the persona without restarting.
- Chat history sidebar with rename and delete.

### Voice
- Speech recognition with offline Vosk and an online fallback.
- Wake words and continuous background listening.
- Spoken replies with a text-to-speech toggle.
- Fuzzy matching that corrects misheard commands.

### Desktop control
- Natural-language commands for apps, files and the system.
- Open and close applications. Installed apps are found through the registry and Start Menu, and cached.
- Open websites, with a web search fallback.
- Search for files, open them, list recent files, create folders and delete files.
- Volume and brightness control, Wi-Fi and Bluetooth toggles.
- Media controls: play/pause, next, previous and stop.
- Battery status and system information.
- Screenshots.
- Lock, sleep, shutdown and restart, with confirmation prompts.
- Open the Control Panel.
- Time, date, location and weather.
- Custom shortcuts: add, list, run and remove your own commands.
- Built-in help with the full command list and categories.

### Interface
- Chat window with message bubbles and a loading indicator.
- Splash screen shown while the app loads.
- Collapsible sidebar and a list of detected applications.
- Settings window with a language selector.

### Privacy and security
- Permission toggles for file access, system settings and power control.
- Optional PIN protection, stored as a hash.
- Command audit log, with export and clear.
- Data management: export all data or delete it.

### Other
- Relationship system that tracks interactions with the assistant over time.
- Missing Python packages are installed automatically on first run.
- Known limitation: many features were experimental, untested or incomplete.
