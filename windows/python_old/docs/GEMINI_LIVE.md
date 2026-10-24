# Gemini Live implementation notes

This project uses the official `google-genai` Python SDK for the optional pure-voice mode.

- Live API SDK guide: https://ai.google.dev/gemini-api/docs/live-api/get-started-sdk
- Live API capabilities and PCM format: https://ai.google.dev/gemini-api/docs/live-api/capabilities
- Live transcription model and interim/final transcription: https://ai.google.dev/gemini-api/docs/live-api/live-transcribe
- Gemini API pricing and free-tier availability: https://ai.google.dev/gemini-api/docs/pricing

The official SDK guide documents bidirectional WebSocket sessions, raw 16-bit little-endian PCM input at 16 kHz, and native audio response chunks. The implementation keeps the Live model and voice configurable because model names, preview status, free-tier quotas, and account eligibility can change. The default is `gemini-3.8-live`; users can replace it with a currently available Live model in the voice settings.
