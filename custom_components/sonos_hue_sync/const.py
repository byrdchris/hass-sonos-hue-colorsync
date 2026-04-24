DOMAIN = "sonos_hue_sync"

CONF_SONOS_ENTITY = "sonos_entity"
CONF_LIGHT_GROUP = "light_group"
CONF_LIGHT_ENTITIES = "light_entities"
CONF_COLOR_COUNT = "color_count"
CONF_TRANSITION = "transition"
CONF_FILTER_DULL = "filter_dull"
CONF_CACHE = "cache"
CONF_EXPAND_GROUPS = "expand_groups"
CONF_ASSIGNMENT_STRATEGY = "assignment_strategy"

DEFAULT_COLOR_COUNT = 3
DEFAULT_TRANSITION = 2
DEFAULT_FILTER_DULL = True
DEFAULT_CACHE = True
DEFAULT_EXPAND_GROUPS = True
DEFAULT_ASSIGNMENT_STRATEGY = "balanced"

ASSIGNMENT_STRATEGY_SEQUENTIAL = "sequential"
ASSIGNMENT_STRATEGY_BALANCED = "balanced"
ASSIGNMENT_STRATEGY_ALTERNATING = "alternating"
ASSIGNMENT_STRATEGY_BRIGHTNESS = "brightness"

PLATFORMS = ["switch", "sensor", "button"]

SERVICE_ENABLE = "enable"
SERVICE_DISABLE = "disable"
SERVICE_APPLY_LAST_PALETTE = "apply_last_palette"
SERVICE_TEST_COLOR = "test_color"
SERVICE_EXTRACT_NOW = "extract_now"
SERVICE_TEST_RAINBOW = "test_rainbow"

ATTR_HEX_COLORS = "hex_colors"
ATTR_RGB_COLORS = "rgb_colors"
ATTR_SOURCE_IMAGE = "source_image"
ATTR_RESOLVED_LIGHTS = "resolved_lights"
ATTR_LAST_SERVICE_DATA = "last_service_data"
ATTR_PALETTE_PREVIEW = "palette_preview"
ATTR_COLOR_COUNT_ACTUAL = "color_count_actual"
