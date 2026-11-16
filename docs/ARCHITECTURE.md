# Architecture notes / 技术实现说明

AEGIS Focus HUD is a **single-machine Windows application**. No backend, cloud database, user account or model API is required.

## Rendering pipeline

1. The controller in `app.py` manages task and display state.
2. `hud_renderer.py` draws Pillow RGBA frames. Static surfaces and decorative instruments are cached where practical; animated parts are updated separately.
3. The center of the rendered composition is kept transparent (alpha = 0). `layered_window.py` uses Win32 styles for a layered, click-through, non-activating overlay. Click-through behavior must be checked on Windows, and is not guaranteed for exclusive-fullscreen apps.
4. `reticles.py`, `signal_bus.py`, and `terrain_scanner.py` implement respectively selectable crosshairs, synthetic telemetry and a synthetic moving route map. They use pseudo-random/procedural data—not data from the user's screen or sensors.

## Focus state

`core.py` contains the monotonic timer, pause/resume logic, scoring, story parsing and JSON persistence helpers. `app.py` owns the UI flow and saves preferences, session history and unfinished work to `data/profile.json`. This file must remain outside the Git repository.

## Internationalization and extensibility

`localization.py` / `english_ui.py` handle controller language and story choices. Local stories are loaded from `storylines/` and `storylines/en/` as Markdown or JSON. Stories are an **optional extension**; a free focus session remains available without them. Soundscapes are optional user-provided WAV files in `audio/`.

## Platform and known constraints

- Python + Pillow for imaging, Windows APIs for compositing and hotkeys, `winsound` for optional sound; no Linux/macOS GUI support.
- Primary monitor only; monitor migration and exclusive fullscreen not supported.
- Rendering-time measurements do not include the desktop window upload/composition step.
- No cloud sync, network tracking, EEG, eye tracking or automatic translation.
