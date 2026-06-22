from homeassistant import config_entries

DOMAIN = "media_hue_sync"

class MediaHueSyncConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        return self.async_create_entry(
            title="Media Hue Sync",
            data={}
        )
