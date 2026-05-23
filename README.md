## v1.2.20 UI Consolidation and Conservative Auto

This release simplifies the visible color-tuning controls while preserving the underlying palette functionality added across the v1.2.x series. Auto remains conservative by default, and stronger looks are now selected through fewer, clearer choices.

- **Artwork Style** is now focused around Auto, Album Accurate, Ambient, Vivid, High Contrast, and Monochrome / Neutral.
- **Auto Style Behavior** is now **Auto Intensity**: Subtle, Balanced, or Expressive. Subtle is the default and stays closest to the cover.
- **Neutral Tone Handling** is simplified to Natural, Reduce Whites, Warm Neutral, and Preserve Contrast.
- Legacy values such as Photography, Cinematic, Prefer Vivid, Prefer Ambient, Graphic / Poster, and Allow Pure White remain accepted internally for compatibility, but the main UI no longer presents them as separate broad choices.
- Palette Coherence remains unchanged because it provides distinct useful outcomes: Natural, Balanced, Dominant Colors Only, and Dominant + Vivid Accent.

## v1.2.19 Palette Coherence Accent Options

This release upgrades **Palette Coherence** into clearer outcome-based options so users can choose either a cohesive dominant-family look or preserve strong accent colors from the cover. It fixes cases where cyan/blue album art with real magenta accents lost those accents under strict coherence filtering.

- **Natural** preserves the extracted palette with minimal hue-family filtering.
- **Balanced** softens weak outliers while keeping natural color variation.
- **Dominant Colors Only** keeps the cohesive dominant hue-family look and intentionally removes accent/outlier colors.
- **Dominant + Vivid Accent** keeps the dominant color family while restoring 1–2 strong vivid accents, such as magenta on cyan artwork.

Diagnostics now report preserved accent colors in Palette Coherence diagnostics, and palette regression tests include cyan + magenta accent preservation plus the dominant-only look.

## v1.2.18 Palette Guardrails and Regression Testing

This release keeps the v1.2.17 Gradient Neutral Suppression feature and adds upstream palette guardrails so Auto and Warm Ambient do not overpower the album art. Low-confidence Auto detection now uses Album Accurate handling, successful artwork fetches explicitly prevent fallback tinting, and release packaging now includes deterministic album-cover palette regression tests.


This release adds **Gradient Neutral Suppression** for native Hue gradient lights. When an album cover has strong non-neutral colors, supported gradient lights can now replace gray, black, or white-like gradient anchors with colorized palette anchors so Hue does not render neutral points as unwanted white. The default **Auto** mode only intervenes when better colorized anchors exist; **Strong** avoids neutral gradient points more aggressively; **Keep Whites Only When Present** preserves intentional artwork whites while blocking pseudo-white behavior from neutral anchors.

Diagnostics now show the original gradient points, final gradient points, replacements, selected suppression mode, and suppression reason. Standard non-gradient lights are unchanged.

## v1.2.16 Gradient Base Color Fix

This release fixes a gradient-light edge case where Hue/HA could expose or retain a near-white representative color on Signe gradient lights even when the active album-art palette contained no white. Native Hue gradient payloads now include a representative/base color selected from the final gradient palette, and diagnostics report the selected representative color.

It also tightens ordered-gradient diagnostics so Dark to Light and Light to Dark continue to use explicit luminance-ordered palette colors after option changes.

## v1.2.15 Auto Behavior and Ordered Gradient Fix

This release makes **Auto Style Behavior** visibly affect the final palette after Auto Artwork Style detection. It also fixes explicit **Dark to Light** and **Light to Dark** gradient ordering so style changes cannot make ordered gradients appear reversed or inconsistently anchored.

- Prefer Ambient now softens high-contrast Auto palettes instead of only changing detection scoring.
- Prefer Vivid now more strongly boosts usable color energy while preserving guardrails.
- Prefer Accuracy now reduces stylization and keeps the palette closer to extracted artwork tones.
- Ordered gradients now choose anchors from the full final palette and apply luminance ordering after all style processing.
- Diagnostics include before/after Auto Style Behavior palettes and ordered-gradient selection details.

## v1.2.14 Neutral White Visibility Fix

This release strengthens Neutral Tone Handling for monochrome and near-monochrome album art. v1.2.13 prevented red/pink/brown drift, but Hue devices could still render different grayscale palettes as visually similar white. v1.2.14 makes neutral modes visibly distinct by shaping both neutral palette brightness and color temperature where Home Assistant/Hue supports it.

- Reduce Whites now caps bright neutral stops more aggressively.
- Warm Ambient now produces a visible warm neutral wash without red/brown drift.
- Preserve Contrast, Graphic / Poster, Natural, and Allow Pure White keep separate neutral behavior under monochrome guardrails.
- Diagnostics now report that monochrome guardrail output uses visible white shaping.

## v1.2.13 Neutral Tone Handling Fix

This release keeps the monochrome guardrail from v1.2.12, but lets **Neutral Tone Handling** change black-and-white and grayscale album art again.

- **Natural** keeps balanced grayscale tones.
- **Reduce Whites** suppresses bright whites while preserving grayscale.
- **Preserve Contrast** expands dark and light separation.
- **Warm Ambient** adds only a very subtle warm-gray tint and avoids red/pink/brown drift.
- **Graphic / Poster** uses stronger black/white separation.
- **Allow Pure White** permits brighter whites.

Diagnostics now show the active monochrome guardrail palette mode so neutral handling behavior is easier to verify.

## v1.2.12 Monochrome Guardrails
This release tightens Auto Artwork Style for black-and-white and grayscale artwork. When Auto detects a high-neutral, near-zero-vivid cover, it preserves grayscale tones even if Auto Style Behavior is set to Prefer Vivid or Neutral Tone Handling is warm. This prevents monochrome covers from becoming red, pink, or brown.


- Explicit **Dark to Light** and **Light to Dark** gradient patterns are now locked layout choices.
- **Artwork Style → Auto** can still change which colors are extracted, but it no longer changes how ordered gradient ramps flow across gradient lights.
- Ordered gradients now keep the selected palette anchors stable, sort only by perceptual luminance as the final layout step, and continue to suppress rotation.
- Diagnostics now show `gradient_order_lock`, `gradient_order_lock_reason`, and `locked_palette_order` for ordered gradient patterns.

## v1.2.10 Auto Artwork Style

- **Auto** Artwork Style analyzes each album cover locally and selects the most appropriate style for mixed playlists.
- **Auto Style Behavior** can bias Auto toward Balanced, Prefer Accuracy, Prefer Vivid, or Prefer Ambient.
- **Monochrome Accent** improves black-and-white and grayscale covers without inventing unrelated rainbow colors.
- **Advanced / Custom** was removed from visible Artwork Style and Neutral Tone Handling menus because it was not a distinct visual result. Legacy values are still handled internally for compatibility.
- Help and diagnostics now explain selected style, detected style, confidence, and detection reasons.

### Artwork Style guide

- **Auto**: best default for playlists; chooses a style per track from local image statistics.
- **Album Accurate**: preserves intended cover tones, including muted colors.
- **Natural**: balanced everyday room lighting.
- **Graphic / Poster**: best for typography, pop-art, high contrast, and flat-color covers.
- **Photography**: best for portraits and realistic photographic artwork.
- **Cinematic**: deeper, moodier colors with smoother transitions.
- **Soft Ambient**: subtle, less saturated background lighting.
- **Bold / High Contrast**: vivid, energetic color separation.
- **Monochrome Accent**: black-and-white or grayscale covers with restrained accents. Auto uses monochrome guardrails to preserve grayscale when no real vivid color is present.

# Sonos Hue Sync

Sonos Hue Sync is a Home Assistant custom integration that extracts colors from the currently playing Sonos album art and applies them to Philips Hue lights, rooms, zones, and supported gradient lights.

The integration is designed for Home Assistant installations running in container mode and is installable through HACS as a custom repository.


## v1.2.9 Restore Reliability

This release restores the previous Hue light state more reliably after playback stops or Sync is turned off. Turning **Enable Sync** off now forces an immediate restore from the captured snapshot instead of waiting for Restore Delay. Normal playback stop/pause still honors Restore Delay, but the delayed restore is only cancelled when playback actually resumes and a new palette apply begins. Diagnostics now show whether restore is pending, completed, cancelled, failed, or unavailable because no snapshot exists.

## v1.2.7 Rotation UI Clarification

This release makes **Color Rotation** the single authoritative rotation control. The previous separate Auto Rotate Colors control has been removed from the active UI surface to avoid unclear dependency behavior. Existing stored values are preserved for compatibility, but **Color Rotation** now determines whether rotation is Off, On Track Change, Continuous, or Track Change and Continuous.

## v1.2.8 color model updates

This release simplifies the main color controls while preserving the older advanced tuning behavior.

### Main color controls

- **Artwork Style** controls the overall interpretation of album art colors.
  - **Graphic / Poster** is designed for high-contrast typography, pop-art, and flat-color covers. It preserves large red/black/white graphic blocks and suppresses tiny compression or anti-aliasing artifacts that previously could appear as unrelated purple, peach, or pastel colors.
  - **Bold / High Contrast** favors strong saturated accents and contrast.
  - **Album Accurate**, **Photography**, **Cinematic**, **Soft Ambient**, and **Natural** remain available for different album-art types.
- **Neutral Tone Handling** combines the earlier white and black/white behavior into one outcome-based control.

No color-processing capability was removed. The older mechanism-level controls remain available in the options flow as advanced overrides.


## Features

- Extracts color palettes from Sonos album artwork.
- Applies album-inspired colors to Philips Hue lights.
- Supports individual Hue lights, Hue rooms, Hue zones, and expanded group members.
- Supports Hue gradient devices with model-based fallback detection when Home Assistant capability metadata is incomplete.
- Restores the previous lighting scene when playback stops or sync is turned off.
- Includes AirPlay/Sonos artwork fallback handling to reduce flicker and bad palette overwrites.
- Provides Home Assistant controls, diagnostics, health checks, and target previews.
- **Update Lights Now** manually applies the effective current settings without enabling continuous sync.
- **Color Rotation** can shift color assignments on each track change, continuously while music plays, both, or disable rotation entirely.
- Palette ordering can prioritize either vivid visual variety or the most dominant album-art colors first.

## Requirements

- Home Assistant, current release recommended.
- Home Assistant running in container mode is supported.
- HACS installed.
- Home Assistant Sonos integration configured.
- Home Assistant Philips Hue integration configured.
- At least one Sonos `media_player` entity.
- At least one Hue light, room, or zone.

## Installation with HACS

1. Open **HACS**.
2. Go to **Integrations**.
3. Open the menu in the upper-right corner.
4. Select **Custom repositories**.
5. Add this repository URL:

   ```text
   https://github.com/byrdchris/hass-sonos-hue-colorsync
   ```

6. Set the category to **Integration**.
7. Install **Sonos Hue Sync**.
8. Restart Home Assistant.
9. Go to **Settings → Devices & services → Add integration**.
10. Search for **Sonos Hue Sync** and complete setup.

## Configuration

Configuration is handled through the Home Assistant UI. YAML is not required.

During setup and in options, you can configure:

- **Sonos Entity**: the Sonos speaker to monitor.
- **Light Targets**: Hue lights, rooms, or zones to control.
- **Additional Hue Groups**: optional extra Hue groups to expand.
- **Additional Member Lights**: optional direct lights to include.
- **Excluded Lights**: lights that should never be controlled, even if included through a selected room or zone.
- **Color Purity Preset**
- **White Suppression**
- **Number of Colors**: palette size from 1 to 10.
- **Palette Ordering**: choose whether the extracted palette favors vivid, visually distinct colors or keeps the most dominant album-art colors first.
- **Color Accuracy Mode**: choose Natural, Vivid, or Album Accurate extraction. Natural is the default balanced mode, Vivid favors saturated accents, and Album Accurate preserves more muted artwork tones.
- **Color Purity Preset**: chooses named behavior for album fidelity versus saturated emphasis. Presets preserve the previous underlying color-purity behavior without requiring a numeric slider.
- **White Suppression**: controls white/light-neutral suppression separately from Color Purity Preset. 0 preserves whites; 100 suppresses whites strongly.
- **Transition Time**: fade time for light changes.
- **Minimum Brightness**: lower brightness limit for standard lights.
- **Maximum Brightness**: upper brightness limit for standard lights.
- **Gradient Brightness**: upper brightness limit for supported gradient lights.
- **Restore Delay**: wait time before restoring the previous scene after playback stops.
- **Black & White Handling**: controls how monochrome artwork is translated into light colors.
- **Artwork Fallback**: controls what happens when Sonos artwork is missing or unavailable.
- **Color Distribution Mode**: controls how the extracted palette is assigned across multiple lights. Use **Sequential** if you want lights to follow the selected Palette Ordering directly.
- **Enable True Gradient**: uses multi-color Hue gradient behavior for capable lights while standard lights in the same group continue using normal color updates.
- **Color Rotation**: controls whether color assignments are Off, On Track Change, Continuous, or Track Change and Continuous.
- **Auto Rotation Interval**: total cycle time between continuous rotation starts, adjustable from 1 to 60 seconds. Transition Time is treated as the fade portion of the cycle, with an internal safety buffer to avoid overlapping Hue updates.
- **Gradient Detail Level**: controls the number of gradient points.
- **Gradient Pattern**: controls gradient ordering across lights.
- **Cache Album Colors**: stores album palettes for faster repeat playback.
- **Distribute Across Group Lights**: expands supported Hue groups to their member lights.
- **AirPlay Poll Interval**: fallback polling interval for metadata/artwork cases that do not emit reliable events.

UI labels are intentionally friendly. Internal configuration names are not shown in the Home Assistant interface.

## Home Assistant Controls

### Control model

Sonos Hue Sync uses a single advanced control surface. Basic / Advanced mode has been removed because Home Assistant device controls do not support that behavior cleanly.

Color tuning is split into independent controls:

- **Color Purity Preset**: named presets for album fidelity versus saturated emphasis. Older saved numeric values are preserved as Custom / Existing until a preset is selected.
- **White Suppression**: 0 preserves white and light neutral tones; 100 suppresses whites strongly.

**White Handling** remains separate from Color Purity Preset so album-color fidelity and white/light-neutral behavior can be tuned independently.

### Switches

- **Sync Active**: primary on/off control.
- **Cache Album Colors**
- **Distribute Across Group Lights**
- **Enable True Gradient**

### Selects

- **Color Accuracy Mode**
- **Color Rotation**
- **White Handling**
- **Palette Ordering**
- **Color Distribution Mode**
- **Black & White Handling**
- **Artwork Fallback**
- **Gradient Pattern**

### Numbers

- **Color Purity Preset**
- **White Suppression**
- **Number of Colors**
- **Transition Time**
- **Minimum Brightness**
- **Maximum Brightness**
- **Gradient Brightness**
- **Gradient Detail Level**
- **Restore Delay**
- **Auto Rotation Interval**

### Buttons

- **Update Lights Now**: manually runs the current apply pipeline, even if Sync Active is off.
- **Refresh Colors**: extracts and applies the current track palette.
- **Rotate Colors**: rotates the current palette across selected lights.
- **Test Lighting**: applies a test palette.
- **Health Check**: runs a connectivity and configuration check.
- **Help & Guide**: opens a persistent notification with usage guidance.

### Sensors

- **Status / Palette**: palette, media, apply, restore, and runtime diagnostics.
- **Target Preview**: resolved light targets and group-expansion diagnostics.

## Behavior

When the selected Sonos entity starts playing, the integration snapshots the current selected Hue lighting state, extracts a palette from the current album art, and applies the palette to the configured Hue targets.

When playback stops, pauses, or the primary sync control is turned off, the integration restores the previous lighting scene. If **Restore Delay** is set and playback resumes before the delay expires, the pending restore is cancelled.

Excluded lights are removed after group expansion. This means a light can be part of a selected Hue room or zone and still be protected from control.

When continuous rotation is enabled by **Color Rotation**, the integration periodically reuses the same internal path as **Rotate Colors**. It does not recompute the palette. The current **Transition Time** value controls the fade. **Auto Rotation Interval** is treated as the total cycle time between rotation starts; the fade time and a conservative internal safety buffer are reserved inside that cycle. If the interval is shorter than the fade plus buffer, the integration waits long enough to avoid overlapping Hue updates. Interval and transition changes take effect while auto-rotation is already running.


## Palette Ordering vs. Distribution

**Palette Ordering** controls the order of colors produced by album-art extraction before any lights are updated.

- **Dominant Colors First** is the default. It keeps the most common usable album-art colors first. With this mode, **Number of Colors** behaves as “top N dominant colors.” For example, choosing 3 keeps the top 3 dominant usable colors; choosing 6 adds the next most dominant usable colors.
- **Vivid Colors First** preserves the previous behavior and favors saturated, visually distinct colors that usually look better on lights, even if those colors are not the most common colors in the artwork.

**Color Distribution Mode** is separate. It controls how the selected palette is assigned to lights. **Sequential** preserves Palette Ordering most directly. Balanced, Alternating, and Brightness modes may rearrange colors for visual spread.

**Gradient Pattern** is also separate. It controls how supported gradient lights arrange the selected palette across gradient points.

## Gradient Lights

Gradient support uses both Home Assistant/Hue capability metadata and a model-based fallback for known Hue gradient devices such as Signe lamps, Play gradient lightstrips, and Play gradient tubes. In mixed groups, capable gradient lights receive multi-point gradient updates while standard Hue lights receive normal single-color updates from the same palette. If a gradient update is rejected by the Hue API, only that light falls back to standard color control; the rest of the group continues normally.

### Mixed groups

A selected Hue room or zone can contain both gradient-capable lights and regular color lights. Sonos Hue Sync applies the same album palette through two clean paths:

- gradient-capable lights receive multi-point gradient updates when **Enable True Gradient** is on;
- standard lights receive normal single-color updates from the same palette and distribution mode.

This avoids downgrading an entire room to single-color just because some lights are not gradient-capable.

## Troubleshooting

### HACS shows stale information

HACS and GitHub can cache repository metadata. Refresh HACS, restart Home Assistant, and confirm the installed version under the integration details.

### Lights do not restore

Check that the selected lights were available before playback started and review the **Status / Palette** sensor attributes for `restore_last_result` and `restore_snapshot_count`.

### A room or zone misses lights

Some Hue group entities expose member lights differently. Enable **Distribute Across Group Lights** and review the **Target Preview** sensor to see how targets were resolved.

### AirPlay artwork is inconsistent

AirPlay-to-Sonos artwork can be unreliable. Use **Artwork Fallback** and **Cache Album Colors** to reduce flicker and avoid bad palette overwrites.

### Gradient behavior is inconsistent

Confirm **Enable True Gradient** is on. Review diagnostics for `gradient_capability`, `gradient_detection_source`, and per-light fallback information. Known Hue gradient models are detected even when Home Assistant exposes incomplete gradient capability metadata.

## Release workflow

This repository includes a GitHub Actions release workflow. Pushing a version tag such as `v1.2.6` creates a GitHub release and attaches a clean archive.

```bash
git tag v1.2.4
git push origin v1.2.4
```

## License

MIT License. See `LICENSE`.


## Behavior notes

### Color Rotation

**On Track Change** is the default. On each new track, the integration shifts the palette assignment by one slot before applying the new album colors. This prevents the same physical lamps from repeatedly receiving the same palette position when different albums have similar dominant color structure.

Modes:
- **Off**: keep deterministic palette-to-light assignment and disable continuous rotation.
- **On Track Change**: shift assignments only when the track changes.
- **Continuous**: use timed palette rotation while music is playing.
- **Track Change and Continuous**: shift on each track and keep timed rotation active.

Dark to Light and Light to Dark gradient patterns suppress rotation internally so the selected brightness direction remains intact.

### Color Accuracy Mode
- **Color Purity Preset**: chooses named behavior for album fidelity versus saturated emphasis. Presets preserve the previous underlying color-purity behavior without requiring a numeric slider.
- **White Suppression**: controls white/light-neutral suppression separately from Color Purity Preset. 0 preserves whites; 100 suppresses whites strongly.

**Natural** is the default and balances album accuracy with usable Hue output. It applies perceptual extraction, dull-color filtering, contextual white suppression, and balanced neutral handling.

Modes:
- **Natural**: balanced default for most album art.
- **Vivid**: favors saturated subject and accent colors, with stronger neutral and white suppression.
- **Album Accurate**: preserves more muted background and neutral tones for artwork where the overall album mood matters more than high saturation.

Color Purity Preset controls general album fidelity while White Handling and White Suppression remain separate because white and light-neutral tones need different treatment from saturation filtering.
- **Color Purity Preset**: chooses named behavior for album fidelity versus saturated emphasis. Presets preserve the previous underlying color-purity behavior without requiring a numeric slider.
- **White Suppression**: controls white/light-neutral suppression separately from Color Purity Preset. 0 preserves whites; 100 suppresses whites strongly.

## Restore and icon reliability

v1.1.16 improves restore behavior by capturing the selected light state as soon as **Enable Sync** is turned on, before any album colors are applied. When sync is turned off, the integration restores that captured state, including lights that were originally off.

The release also includes refreshed `icon.png` and `logo.png` assets in the integration package and repository root to improve Home Assistant/HACS icon display behavior. Home Assistant may still require a browser/app cache refresh before the icon appears.

### Gradient color ordering

Gradient-capable Hue lights can now arrange palette colors as Same Order, Offset, Random Order, Dark to Light, or Light to Dark. Dark/Light ordering uses perceived brightness so gradient ramps match how the colors appear to the eye rather than a simple RGB average.

### Palette Coherence

Palette Coherence controls how strongly the palette stays within the dominant hue family after album-art extraction. It is universal and does not target any specific hue family.

- **Natural** preserves extracted colors with minimal hue-family filtering.
- **Balanced** softens weak outliers while keeping natural color variation.
- **Dominant Colors Only** keeps a cohesive dominant-family look and intentionally removes accent/outlier colors.
- **Dominant + Vivid Accent** keeps the dominant family while preserving 1–2 strong intentional accent colors such as magenta, red, yellow, green, or cyan.

Diagnostics report the selected coherence mode, dominant hue family, cluster score, removed colors, and preserved vivid accent colors.


## v1.2.15 behavior update

Auto Style Behavior is now a visible post-detection preference. Auto still detects the artwork type, but the selected behavior now shapes the final palette: Prefer Ambient softens contrast, Prefer Vivid increases color energy, and Prefer Accuracy reduces stylization. Explicit Dark to Light and Light to Dark gradient patterns remain authoritative after Artwork Style changes.

## Palette regression testing

Release builds now include `tests/test_palette_regression.py`, a deterministic album-cover palette test suite. It generates representative synthetic album covers, including vivid graphic art, monochrome photography-style art, dark cool artwork, and 50 randomized hue-family covers. The test verifies that palette extraction preserves the expected color family, avoids red/pink drift on monochrome art, and prevents Warm Ambient from overpowering non-neutral artwork.

Run before packaging a release:

```bash
python3 tests/test_palette_regression.py
```

