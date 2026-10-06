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
- Persona system: built-in presets, custom character text, or a plain neutral assistant.
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

Initial public preview.
