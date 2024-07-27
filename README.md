[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

# Format-BLE-Tracker

Custom integration for tracking BLE devices (bluetooth tags, smartwatches, phones with Home Assistant Companion app) in Home Assistant
Requires ESPHome and ESP32 tracking nodes installation: see https://github.com/formatBCE/ESP32_BLE_presense.

# Prerequisites:

1. Make sure you have MQTT server, working with your Home Assistant installation, and you can connect to it.
2. Make sure you have 2.4 GHz WiFi network available in all places, where you plan to place your tracking nodes.
3. Prepare and place ESP32 device(s) according to instructions at https://github.com/formatBCE/ESP32_BLE_presense.
4. Write down MAC addresses or Proximity UUIDs for all devices that you want to track:
   - for dumb beacons (e.g. Tile) you can find MAC address in official app, or use any Bluetooth tracker app on your phone to scrap one;
   - for smart beacons (e.g. Android phone with Home Assistant Companion application and BLE tracker enabled), you will need to copy Proximity UUID, because device MAC address is not exposed to public.

# Installation:

  1. HACS: 
  [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=formatBCE&repository=Format-BLE-Tracker&category=Integration)
  Add this repository to HACS in Integrations -> (menu) -> Custom repositories (Repository: URL of this repository, Category: Integration)
  
  2. Manual: 
  Copy the format_ble_tracker folder and all of its contents into your Home Assistant's custom_components folder. This is often located inside of your /config folder. If you are running Hass.io, use SAMBA to copy the folder over. If you are running Home Assistant Supervised, the custom_components folder might be located at /usr/share/hassio/homeassistant. It is possible that your custom_components folder does not exist. If that is the case, create the folder in the proper location, and then copy the format_ble_tracker folder and all of its contents inside the newly created custom_components folder. 
  After it's done, restart HomeAssistant and reload browser page forcefully (Ctrl+F5).
  
# Configuration:

In Home Assistant, go to "Devices and Services" -> "Add Integration". Search for "Format BLE Tracker" and click on it.
## Adding new beacon device
In the configuration dialog, insert MAC address or UUID of tag, and (optionally) enter friendly name for this device.
## Creating combined tracker
Will be useful, if you need to customize behavior of device trackers working together. 
E.g. i have tags on my key chain and in my wallet - and i want Home Assistant to show myself away, if either of this device trackers is not_home.
Currently it's impossible without relying on custom sensors (which are NOT device_tracker) or MQTT device_tracker with help of NodeRED or automation. Combined tracker will use your logic to show itself home/not_home accordingly.

Choose name for new virtual tracker, logic (all home or either home) and pick trackers, that will be combined in new entity.

# Usage:

All communication between tracker nodes and created device are automatic.

Integration will create device with three entities for beacon:
1. Device Tracker entity for device. Will show Home status for this tag, if tag is visible for at least one of tracking nodes, or Away status.
2. Sensor with current closest node name for this device (basically, current room name).
3. Input slider for tuning data expiration period (from 1 minute to 10 minutes). This will affect the time from last visibility event till setting up Away mode. Use greater values, if you experience often changes Home to Away and back. By default set to 2 minutes.

For combined tracker, new Device Tracker entity will be created.

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/formatbce)
  
