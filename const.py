"""Constants for the Format BLE Tracker integration."""

DOMAIN = "format_ble_tracker"

MAC = "mac"
NAME = "name"
SIXTEENTH_REGEX = "[0-9A-F]"
MAC_REGEX = "^([0-9A-F]{2}[:]){5}([0-9A-F]{2})$"
UUID_REGEX = "^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$"

ROOM = "room"
ROOT_TOPIC = "format_ble_tracker"
ALIVE_NODES_TOPIC = ROOT_TOPIC + "/alive"
RSSI = "rssi"
