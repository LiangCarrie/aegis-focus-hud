# Testing / 测试与复现

## Windows verification

From the repository root, with Python 3.10+ and dependencies installed:

```powershell
py -m pip install -r requirements.txt
py -m unittest discover -s tests -v
py app.py
```

In addition to automated tests, perform manual GUI checks on a Windows 10/11 desktop:

1. Confirm the work area is clear and mouse clicks reach the underlying application.
2. Switch all four palettes, display densities, deep/light modes, and eight crosshair styles.
3. Check pause/resume, interruption recovery, manual completion and scoring.
4. Test global keyboard shortcut fallback when a key combination is already in use.
5. Verify a Chinese/English story file pair and progress migration.
6. Test an optional local WAV and expected no-audio behavior.
7. Exercise renderer performance and layout at the monitor resolutions you intend to support.

## Reviewed snapshot (Linux container)

- `python -m compileall` syntax validation succeeded.
- Platform-independent tests: 10 passed.
- Full discovery: 16 tests discovered, 10 passed, one Windows overlay test skipped, five errors because Windows system fonts are unavailable and `winsound` is Windows-only.
- GUI-specific conclusions therefore remain **not verified in this review**. None of the above substitutes for reproducing Windows behavior on an actual machine.

## Data safety

Real preferences, focus history and goals are written to `data/profile.json`. Never include this file in screenshots, build artifacts or commits. The preview gallery was generated from sample content.
