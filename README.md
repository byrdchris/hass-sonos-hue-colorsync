![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)

# Sonos Hue Sync

Home Assistant custom integration that extracts colors from Sonos album art and applies them to Hue lights, rooms, zones, or groups.

## Core behavior

- Watches a selected Sonos media player.
- Fetches the current album art from Home Assistant.
- Extracts a color palette.
- Applies colors to selected Hue/Home Assistant light targets.
- Restores the prior lighting scene when playback stops or the integration is disabled.
- Provides controls for enable/disable, extract now, apply last palette, test rainbow, assignment strategy, and target preview.

## Recommended setup

Start simple:

1. Select the Sonos speaker that shows the active track metadata.
2. In **Hue lights / groups**, select the main Hue room or group you want controlled.
3. Enable **Distribute colors across group members**.
4. Press **Extract Now**.
5. Check the **Target Preview** sensor and the **Palette** sensor.

If some lights are missing, do not keep adding helper zones blindly. Use the target fields as described below.

## Target settings

### Sonos speaker

The Sonos media player to follow.

For grouped Sonos speakers, choose the room that shows the active track title, artist, album, and album art.

### Hue lights / groups

Main targets to control.

Use this for the normal Hue room, group, or individual lights you want synced.

Examples:

```yaml
light.living_room
light.kitchen
light.hue_color_lamp_1
```

If the selected entity exposes member lights, the integration can distribute colors across those members.

### Additional Hue groups to expand

Optional additive workaround.

Use this when the main selection does not expose all of its member lights. This field is added to **Hue lights / groups**; it does not replace it.

Use real Hue room, zone, or group entities here.

Good examples:

```yaml
light.living_room
light.kitchen
light.bedroom
```

Avoid putting helper zones here unless you want that helper zone treated as a target. For example, a helper like `light.living_room_ambient` may be controlled as one combined light if it does not expose members.

### Additional member lights

Optional additive direct override.

Use this for specific individual lights that should always be controlled directly, especially if group expansion misses them.

Good examples:

```yaml
light.game_hue_play_1
light.game_hue_play_2
light.hue_play_1_3
```

Do not put room/group helper entities here.

### Distribute colors across group members

When enabled, colors are applied to individual member lights inside groups when Home Assistant exposes those members.

Disable only if you want a single color applied to the selected group entity itself.

## Palette settings

### Color count

Number of colors to extract from album art.

If there are more target lights than extracted colors, the colors repeat.

### Filter dull colors

Removes black, gray, muddy, or very dark colors while keeping useful color tones.

Recommended: enabled.

### Filter bright whites

Removes harsh pure or cool whites while keeping warmer cream and soft white tones.

Recommended: enabled.

### Black-and-white album handling

Controls what happens when album art is mostly black, white, or grayscale.

Options:

- **Warm neutral**: cream and warm gray palette. Recommended default.
- **Preserve grayscale**: soft grayscale palette.
- **Muted accent**: restrained accent colors.
- **Disabled**: use normal extraction behavior.

This prevents black-and-white artwork from producing random saturated colors from compression or palette noise.

### Handle low-color album art

When artwork has only subtle color, the integration uses a restrained muted palette instead of letting tiny color noise become overly saturated.

Recommended: enabled.

### Cache album colors

Reuses extracted colors for album art that has already been processed.

Recommended: enabled for normal use. Disable while tuning palette behavior if you want every extraction recalculated.

## Light behavior settings

### Transition time

Fade time in seconds for each light change.

Higher values are smoother but slower. Lower values respond faster.

### Light assignment strategy

Controls how extracted colors are assigned to resolved target lights.

Options:

- **Balanced**: usually best for color variety. Recommended default.
- **Sequential**: follows palette order directly.
- **Alternating bright / dim**: alternates lighter and darker tones.
- **Brightness order**: sorts colors from bright to dark. This can make similar hues dominate if the album art has many related tones.

If a room looks too much like one color even though the palette contains several colors, try **Balanced** first.

## Controls

The integration creates these controls:

- **Enabled** switch
- **Extract Now** button
- **Apply Last Palette** button
- **Test Rainbow** button
- **Assignment Strategy** select

## Sensors

### Palette

Shows the latest extracted colors and application diagnostics.

Useful attributes include:

```yaml
hex_colors:
rgb_colors:
palette_preview:
resolved_lights:
last_service_data:
last_error:
resolver_source:
skipped_lights:
```

### Target Preview

Shows what the integration would currently target before applying a palette.

Use this to troubleshoot target selection without waiting for a track change.

Useful attributes include:

```yaml
preview_targets:
preview_target_count:
preview_resolver_source:
preview_skipped_lights:
expansion_entities:
light_targets:
additional_hue_groups:
additional_member_lights:
selected_entity_members:
```

## Practical target examples

### One Hue room works normally

```yaml
Hue lights / groups:
  - light.living_room

Additional Hue groups to expand:
  []

Additional member lights:
  []
```

### Main room misses a few Hue Play lights

```yaml
Hue lights / groups:
  - light.living_room

Additional Hue groups to expand:
  []

Additional member lights:
  - light.game_hue_play_1
  - light.game_hue_play_2
  - light.hue_play_1_3
```

### Multiple rooms

```yaml
Hue lights / groups:
  - light.living_room
  - light.kitchen

Additional Hue groups to expand:
  []

Additional member lights:
  []
```

### Helper zone should also be included as one target

```yaml
Hue lights / groups:
  - light.living_room

Additional Hue groups to expand:
  - light.living_room_ambient

Additional member lights:
  []
```

Only use this if you want the helper zone treated as one target.

## Troubleshooting

### The lights are all one color

Check:

```yaml
assignment_strategy:
palette_preview:
resolved_lights:
```

Try **Balanced** assignment strategy.

### Some lights are missing

Check the **Target Preview** sensor:

```yaml
preview_targets:
preview_resolver_source:
selected_entity_members:
```

If a group does not expose all members, add missing lights to **Additional member lights**.

### Colors look too white or harsh

Enable:

```yaml
Filter bright whites
```

Use:

```yaml
Black-and-white album handling: Warm neutral
```

### Black-and-white artwork creates random colors

Use:

```yaml
Black-and-white album handling: Warm neutral
Handle low-color album art: enabled
```

### Album art changes but lights flicker

Use a transition of 1–3 seconds. The integration sends one Home Assistant `light.turn_on` call per resolved light and relies on Hue/Home Assistant transitions.

## HACS

This integration is intended to be HACS-installable.

Repository structure:

```text
custom_components/sonos_hue_sync/
hacs.json
README.md
```

The HACS/Home Assistant icon is included at:

```text
custom_components/sonos_hue_sync/icon.png
```

## Version notes

### v1.39.0

- Clarifies all settings labels and descriptions.
- Expands README with complete settings reference and examples.
- Adds stronger guidance for target selection and assignment strategy behavior.

### v1.38.0

- Adds low-color album-art handling.

### v1.37.0

- Adds black-and-white album-art handling.

### v1.36.0

- Adds Target Preview sensor.
- Normalizes UI labels/descriptions.

### v1.35.0

- Adds Filter bright whites.
- Improves member-light UI labels.

### v1.34.0

- Makes target sources additive.
- Adds icon.


### v1.40.0

Adds device-page controls for common tuning options:

- Color Count
- Transition Time
- Filter Dull Colors
- Filter Bright Whites
- Black-and-White Album Handling
- Handle Low-Color Album Art
- Cache Album Colors
- Distribute Colors Across Group Members

The options dialog remains the full configuration surface. Device controls are runtime overrides and reapply the last palette when possible.


## v2.0.0

### Stabilization architecture

v2.0.0 keeps the v1.40 feature set and adds the first v2 stabilization pass.

#### Resolver freeze per track

Targets are resolved once per track and then frozen for that track. This prevents target membership from changing mid-song if Home Assistant briefly changes group attributes.

#### Target source map

The Palette and Target Preview diagnostics now expose a source map so each resolved target can be traced back to the input that produced it.

Example:

```yaml
resolver_source_map:
  light.hue_color_lamp_1: light.living_room:direct_entity_id_members
  light.game_hue_play_1: light.game_hue_play_1:selected_entity
```

#### State diffing

The light applier now skips lights whose target color/brightness/transition are effectively unchanged. This reduces unnecessary Home Assistant service calls and helps avoid visible flicker.

Skipped unchanged lights appear in diagnostics:

```yaml
skipped_lights:
  - entity_id: light.example
    reason: unchanged
```

#### Capability-aware application

The apply layer now centralizes light capability handling and avoids unsupported service keys such as `color_temp`.

#### Module split

The previous large light controller has been split into focused modules:

```text
resolver.py
assignment.py
applier.py
hue_controller.py
```

This reduces regression risk and makes future development easier.


## v2.0.1

### Runtime control force-refresh fix

- Changing palette-affecting controls now forces a fresh album-art extraction:
  - Color Count
  - Filter Dull Colors
  - Filter Bright Whites
  - Black-and-White Album Handling
  - Handle Low-Color Album Art
- **Extract Now** now bypasses the palette cache.
- **Extract Now**, test buttons, and palette-affecting changes force a light apply even when state diffing would otherwise skip unchanged lights.


## v2.0.2

### Help and control descriptions

Adds a **Show Help** button and `sonos_hue_sync.show_help` service.

Pressing **Show Help** creates a Home Assistant persistent notification with a concise guide covering:

- target selection
- palette controls
- assignment strategy
- troubleshooting

Entity descriptions were also expanded where Home Assistant supports them. The standard Home Assistant hover tooltip still shows entity names only; the help button is the supported way to provide richer inline guidance.


## v2.0.3

### Gradient assignment fix

Gradient-aware lights such as Signe lamps now follow the selected assignment strategy.

Previous behavior:
- Gradient-aware lights were assigned from a fixed accent palette.
- Changing assignment strategy could make regular lights change while gradient lights stayed visually similar.

New behavior:
- Gradient-aware lights still receive assignment priority.
- Their colors now come from the selected strategy's palette ordering.


## v2.1.0

### Experimental True Gradient Mode

Adds optional true multi-color gradients for Hue gradient-capable lights.

New controls:

- **True Gradient Mode**
- **Gradient Color Points**

Behavior:

- When disabled, gradient lights use the existing HA-native single-color behavior.
- When enabled, gradient-aware lights attempt direct Hue V2/aiohue gradient control through Home Assistant's existing Hue bridge connection.
- If direct gradient control fails for a light, that light falls back to the normal Home Assistant `light.turn_on` method.

Diagnostics:

- `gradient_requested`
- `gradient_applied`
- `gradient_colors`
- `gradient_points`
- `gradient_error`


## v2.1.1

### Gradient diagnostics and label cleanup

- Fixes remaining raw **gradient_color_points** label leakage in translations.
- Improves True Gradient Mode diagnostics.
- Attempts direct Hue gradient update even when Home Assistant/aiohue exposes gradient metadata as an invalid/empty parsed object.
- Adds raw dictionary payload fallback after aiohue model payload failure.

Check `last_service_data` for:

```yaml
gradient_requested:
gradient_applied:
gradient_error:
gradient_payload_kind:
hue_resource_id:
hue_resource_name:
gradient_colors:
```


## v2.1.2

### Gradient matching and UI naming cleanup

This release improves True Gradient diagnostics and matching.

If gradient application fails, check the Status entity's `last_service_data` for:

```yaml
gradient_error:
gradient_match_attempts:
hue_resource_id:
hue_resource_name:
```

UI naming has also been standardized:

- Status
- Targets
- Refresh Colors
- Reapply Colors
- Test Lighting
- Help & Guide
- Color Distribution Mode
- Enable True Gradient
- Gradient Detail Level


## v2.1.3

### Hue bridge discovery fix

True Gradient Mode now discovers Hue bridge runtime data through Home Assistant's Hue config entries.

This should fix cases where diagnostics showed:

```yaml
gradient_error: hue_resource_not_found
gradient_match_attempts: []
```

New diagnostic:

```yaml
hue_bridge_count:
```


## v2.1.4

### True Gradient payload fix

Fixes Hue gradient payload construction for Home Assistant/aiohue versions where
`GradientFeatureBase` does not accept a `mode` argument.

This should resolve diagnostics like:

```yaml
gradient_error: GradientFeatureBase.__init__() got an unexpected keyword argument 'mode'
```


## v2.1.5

### Download Diagnostics

Adds native Home Assistant diagnostics support.

Use:

```text
Settings → Devices & services → Sonos Hue Sync → three-dot menu → Download diagnostics
```

Diagnostics include runtime state, target resolution, entity/device registry data, light capabilities, Hue bridge runtime summary, and gradient troubleshooting fields. Tokens and volatile artwork URLs are redacted.


## Troubleshooting and diagnostics

For most issues, start with the **Status** and **Targets** entities.

### Status

The **Status** entity shows the current palette, resolved lights, last service calls, skipped lights, and gradient diagnostics.

Useful fields:

```yaml
last_service_data:
skipped_lights:
last_error:
resolver_source:
resolver_source_map:
runtime_options:
```

For True Gradient Mode, check:

```yaml
gradient_requested:
gradient_applied:
gradient_error:
gradient_payload_kind:
hue_resource_id:
hue_resource_name:
gradient_colors:
```

### Targets

The **Targets** entity shows which lights will be controlled before colors are applied.

Useful fields:

```yaml
preview_targets:
preview_source_map:
preview_skipped_lights:
selected_entity_members:
```

### Download diagnostics

For deeper troubleshooting, use Home Assistant's native diagnostics download:

```text
Settings → Devices & services → Sonos Hue Sync → three-dot menu → Download diagnostics
```

Diagnostics include:

- current configuration and runtime options
- resolved light targets and source mapping
- selected/resolved entity states
- entity and device registry metadata
- light capability attributes
- Hue bridge runtime summary
- gradient troubleshooting fields
- last service data and skipped-light reasons

Tokens and artwork URLs are redacted before export.


## v2.1.6

### Diagnostics help documentation

Adds Download Diagnostics instructions to:

- Help & Guide notification
- README troubleshooting section
- service/entity descriptions where Home Assistant supports them


## v2.1.7

### Gradient Pattern

Adds a new **Gradient Pattern** control for True Gradient Mode.

Options:

- **Same order on every gradient light**: every gradient-capable light uses the same palette order.
- **Offset per light**: each gradient-capable light starts from its assigned color, preserving the previous varied look.
- **Random order**: shuffles the palette per track/light. The shuffle is deterministic for the current track, so it will not flicker during the same song.

Diagnostics include:

```yaml
gradient_order_mode:
```


## v2.1.8

### Config flow fix

Fixes the Options/Config flow crash from v2.1.7 caused by missing Gradient Pattern constants in `config_flow.py`.

## License

MIT License © 2026 Chris Byrd

This project is open source. If you build upon it, please retain attribution.

## v2.2.0

### Diagnostics and stability release

Adds:

- **Health Check** button
- `sonos_hue_sync.health_check` service
- Health Check persistent notification
- Additional Status diagnostics:
  - timings
  - cache result
  - restore result
  - restore snapshot count
  - health report
- Expanded downloaded diagnostics with health and runtime troubleshooting data.

Health Check reviews Hue bridge reachability, Sonos availability, selected targets, resolved lights, gradient success/fallback counts, and recent processing errors.


## v2.2.1

### Accent-preserving low-color artwork

Improves color extraction for mostly dark or neutral album art that contains a real accent color, such as orange stars/logos/text.

Previous behavior:
- Low-color handling could over-mute the cover into warm browns/tans.

New behavior:
- Preserves strong accent colors.
- Keeps a usable dark anchor from the artwork.
- Still avoids harsh bright whites.


## v2.3.0

### Control tuning

Adds:

- **Minimum Brightness**
- **Maximum Brightness**
- **Gradient Brightness**
- **Excluded Lights**
- **Restore Delay**

Behavior:

- Standard light brightness is clamped between Minimum and Maximum Brightness.
- True Gradient lights use Gradient Brightness as their maximum.
- Excluded Lights are removed after group expansion, so they are not controlled even if they belong to a selected room/group.
- Restore Delay waits after playback stops before restoring the previous light state. If playback resumes during the delay, restore is cancelled.


## v2.3.1

### Corrective patch

Fixes v2.3.0 regressions:

- Restores friendly labels/descriptions for new options:
  - Minimum Brightness
  - Maximum Brightness
  - Gradient Brightness
  - Excluded Lights
  - Restore Delay
- Runtime option changes now force a fresh apply.
- Empty palette extraction now falls back to the previous palette when available.
- Adds `last_palette_error` diagnostics.
- Keeps target/gradient behavior unchanged.


## v2.3.2

### Album art fetch fallback

Fixes cases where Home Assistant's Sonos media proxy returns an empty artwork response.

Behavior:

- Tries all available artwork URL candidates.
- If artwork is unavailable but a previous palette exists, reuses the previous palette.
- If artwork is unavailable and no previous palette exists, generates a stable fallback palette from track metadata.
- Adds image fetch diagnostics:
  - `last_image_fetch_status`
  - `last_image_fetch_candidates`

This prevents the integration from aborting with `no_palette_available` when Sonos artwork temporarily fails.


## v2.3.3

### Artwork fallback behavior

Adds a configurable **Artwork fallback behavior** option for cases where Sonos/AirPlay artwork cannot be retrieved.

Options:

- **Reuse last palette**: reuse the previous palette when available; otherwise use track-based colors.
- **Track-based colors**: generate stable colors from track metadata.
- **Warm neutral**: use a soft warm neutral fallback palette.
- **Do nothing**: leave lights unchanged when artwork is unavailable.

Diagnostics added/updated:

```yaml
artwork_fallback_mode:
artwork_fallback_applied:
last_palette_error:
last_image_fetch_status:
last_image_fetch_candidates:
```


## v2.3.4

### AirPlay/Sonos metadata reliability

Adds:

- **Current Artwork** image entity for the integration device/controls page.
- Fallback metadata polling while the selected Sonos entity is playing.
- AirPlay metadata diagnostics in Status and diagnostics download.
- Configurable **AirPlay Metadata Check Interval**.

Why:

AirPlay-to-Sonos can update track metadata and artwork inconsistently through Home Assistant events. This release keeps the event-driven design but adds a lightweight safety check while playback is active.


## v2.3.5

### Reapply Colors rotates assignments

The **Reapply Colors** button now rotates the current palette across the selected lights instead of simply sending the same assignment again.

Behavior:

- Uses the current palette.
- Uses the current resolved light targets.
- Forces a new light update.
- Rotates which light receives which color.
- For supported true-gradient lights, rotates the gradient point order as well.
- Does not re-fetch album art or re-extract the palette.

Diagnostics include:

```yaml
reapply_rotation_offset:
gradient_rotation_offset:
```


## v2.3.6

### Apply performance and queueing

Improves responsiveness when several color changes are triggered close together.

Changes:

- Adds a single-flight apply lock so multiple full apply passes do not stack.
- If a new apply is requested while one is running, only one follow-up pass is queued using the latest palette/options.
- Standard Home Assistant light calls are now sent concurrently after gradient handling.
- This should reduce visible lag for lights near the end of the target list, such as Hue Play lights.

Diagnostics:

```yaml
apply_queue_status:
```


## v2.3.13

### Stable rollback baseline

This release rolls back to the last stable pre-image-entity baseline and removes the Album Art image entity.

Included:

- v2.3.7 behavior as the baseline.
- Reapply Colors standard-light rotation fix.
- True-gradient rotation behavior.
- Artwork fallback suppression from v2.3.12.
- Diagnostics retained for artwork fetch and fallback handling.

Removed:

- `image.py`
- `image` platform setup
- Album Art image entity

Album art can still be viewed from the selected Sonos media player entity or in the existing Sonos media card.


## v2.3.14

### Hue group member resolution fix

Fixes cases where a selected Hue room/group exposed direct `entity_id` members but the integration still used same-area fallback.

Changes:

- Direct Hue group `entity_id` membership is now preferred whenever available.
- Same-area fallback is only used when direct group members are unavailable.
- If a track was frozen using same-area fallback before group attributes populated, the frozen resolver refreshes when direct members become available.
- Adds group expansion diagnostics:

```yaml
group_resolution:
preview_group_resolution:
```

These diagnostics show declared group members, resolved members, and missing/skipped members.
