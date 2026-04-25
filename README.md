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
