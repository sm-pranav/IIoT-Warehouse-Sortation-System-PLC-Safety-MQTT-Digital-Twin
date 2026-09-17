# =============================================================
#  IIoT Smart Sortation Conveyor - edge gateway
#
#  Reads DB1 from the S7-1200 (PLCSIM) over the S7 protocol,
#  publishes it as JSON over MQTT, and writes dashboard commands
#  back into the PLC.
#
#  pip install python-snap7 paho-mqtt
# =============================================================

import json
import time
import uuid

import snap7
from snap7.client import Client
from snap7.util import get_int, get_dint, get_real, get_bool, set_bool
import paho.mqtt.client as mqtt

# -------------------------------------------------------------
#  CONFIGURATION
# -------------------------------------------------------------
PLC_IP   = "127.0.0.1"     # PLCSIM on this machine
PLC_RACK = 0
PLC_SLOT = 1
DB_NUMBER = 1              # "ConveyorData"
DB_SIZE   = 32             # bytes - matches the DB1 layout

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT   = 1883
PUBLISH_PERIOD = 2.0       # seconds between publishes

# A short session id keeps our topics private on the public broker.
# The dashboard must use the SAME id.
SESSION_ID = "demo01"
TOPIC_TELEMETRY = f"iiot/conveyor/{SESSION_ID}/telemetry"
TOPIC_COMMAND   = f"iiot/conveyor/{SESSION_ID}/cmd"

MODE_TEXT  = {0: "STOP", 1: "AUTO", 2: "MANUAL", 3: "FAULT"}
ALARM_TEXT = {
    0: "No active alarms",
    1: "EMERGENCY STOP - safety circuit open",
    2: "JAM at the divert junction",
    3: "SENSOR FAULT - two class sensors active",
    4: "INVERTER FAULT - belt drive tripped",
}

# Command bits, all in byte 30 of DB1.
CMD_BYTE = 30
MOMENTARY_BITS = {         # pressed and released, like a pushbutton
    "start":       0,
    "stop":        1,
    "reset":       2,
    "mode_auto":   3,
    "mode_manual": 4,
}
LATCHED_BITS = {           # stays where you put it, like a selector switch
    "downstream_ready": 5,
}


# -------------------------------------------------------------
