DOMAIN = "sonos_hue_sync"

CONF_SONOS_ENTITY = "sonos_entity"
CONF_LIGHT_GROUP = "light_group"
CONF_LIGHT_ENTITIES = "light_entities"
CONF_COLOR_COUNT = "color_count"
CONF_TRANSITION = "transition"
CONF_FILTER_DULL = "filter_dull"
CONF_CACHE = "cache"

DEFAULT_COLOR_COUNT = 3
DEFAULT_TRANSITION = 2
DEFAULT_FILTER_DULL = True
DEFAULT_CACHE = True

PLATFORMS = ["switch", "sensor"]
SERVICE_ENABLE = "enable"
SERVICE_DISABLE = "disable"
SERVICE_APPLY_LAST_PALETTE = "apply_last_palette"
SERVICE_TEST_COLOR = "test_color"

ATTR_HEX_COLORS = "hex_colors"
ATTR_RGB_COLORS = "rgb_colors"
ATTR_SOURCE_IMAGE = "source_image"
ATTR_RESOLVED_LIGHTS = "resolved_lights"
ATTR_LAST_SERVICE_DATA = "last_service_data"
