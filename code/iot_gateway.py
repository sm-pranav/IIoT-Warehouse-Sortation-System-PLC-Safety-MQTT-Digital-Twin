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
#  PLC
# -------------------------------------------------------------
def connect_plc():
    """Keep trying until PLCSIM answers."""
    client = Client()
    while True:
        try:
            print(f"[PLC ] Connecting to {PLC_IP} rack {PLC_RACK} slot {PLC_SLOT} ...")
            client.connect(PLC_IP, PLC_RACK, PLC_SLOT)
            if client.get_connected():
                print("[PLC ] Connected.")
                return client
        except Exception as exc:
            print(f"[PLC ] Not ready yet ({exc}). Retrying in 3 s. Is PLCSIM in RUN?")
        time.sleep(3)


def read_plc(client):
    """Read DB1 and unpack it.

    These offsets must match the DB1 layout in
    conveyor_plc_structured_text.st.
    """
    data = client.db_read(DB_NUMBER, 0, DB_SIZE)

    mode_val  = get_int(data, 24)
    alarm_val = get_int(data, 28)

    return {
        "session":          SESSION_ID,
        "total":            get_int(data, 0),
        "lane1":            get_int(data, 2),
        "lane2":            get_int(data, 4),
        "lane3":            get_int(data, 6),
        "reject":           get_int(data, 8),
        "oee":              round(get_real(data, 10), 1),
        "throughput":       round(get_real(data, 14), 1),
        "uptime":           get_dint(data, 18),
        "speed":            get_int(data, 22),
        "mode":             MODE_TEXT.get(mode_val, "?"),
        "motor_running":    get_bool(data, 26, 0),
        "alarm_active":     get_bool(data, 26, 1),
        "jam":              get_bool(data, 26, 2),
        "sorting_small":    get_bool(data, 26, 4),
        "sorting_medium":   get_bool(data, 26, 5),
        "sorting_large":    get_bool(data, 26, 6),
        "estop":            get_bool(data, 26, 7),
        "object_present":   get_bool(data, 27, 0),
        "vfd_fault":        get_bool(data, 27, 1),
        "interlock_hold":   get_bool(data, 27, 2),
        "downstream_ready": get_bool(data, 27, 3),
        "cmd_ds_ready":     get_bool(data, 30, 5),
        "alarm_code":       alarm_val,
        "alarm_text":       ALARM_TEXT.get(alarm_val, "Unknown alarm"),
        "ts":               int(time.time()),
    }


def build_activity(sample):
    """One readable line describing what the machine is doing."""
    if sample["interlock_hold"]:
        return "HELD - waiting for the downstream vehicle"
    if sample["sorting_small"]:
        return "Diverting class 1 -> Lane 1"
    if sample["sorting_medium"]:
        return "Diverting class 2 -> Lane 2"
    if sample["sorting_large"]:
        return "Diverting class 3 -> Lane 3"
    if sample["object_present"]:
        return "Load at the entry sensor"
    if sample["motor_running"]:
        return "Belt running - waiting for loads"
    return "Belt stopped"


def _set_cmd_bit(client, bit, state):
    """Read-modify-write byte 30 so one command never clears another.

    The downstream-ready bit is latched, so a Start press must not
    wipe it out.
    """
    buf = bytearray(client.db_read(DB_NUMBER, CMD_BYTE, 1))
    set_bool(buf, 0, bit, state)
    client.db_write(DB_NUMBER, CMD_BYTE, buf)


def pulse_command(client, name):
    """Momentary command: set the bit, hold it for a few PLC scans, clear it."""
    bit = MOMENTARY_BITS[name]
    _set_cmd_bit(client, bit, True)
    time.sleep(0.3)
    _set_cmd_bit(client, bit, False)
    print(f"[CMD ] Pulsed '{name}'.")


def latch_command(client, name, state):
    """Latched command: leave the bit where the dashboard put it."""
    bit = LATCHED_BITS[name]
    _set_cmd_bit(client, bit, bool(state))
    print(f"[CMD ] Set '{name}' = {bool(state)}.")


def handle_command(client, name, state):
    if name in MOMENTARY_BITS:
        pulse_command(client, name)
    elif name in LATCHED_BITS:
        latch_command(client, name, state)
    else:
        print(f"[CMD ] Ignored unknown command '{name}'")


# -------------------------------------------------------------
#  MQTT
# -------------------------------------------------------------
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Connected to {MQTT_BROKER}. Session id = '{SESSION_ID}'")
        client.subscribe(TOPIC_COMMAND)
        print(f"[MQTT] Listening for commands on: {TOPIC_COMMAND}")
    else:
        print(f"[MQTT] Connect failed with code {rc}")


def on_message(client, userdata, msg):
    """A command arrived from the dashboard."""
    plc_client = userdata["plc"]
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        command = str(payload.get("cmd", "")).lower()
        state = payload.get("state", True)
        handle_command(plc_client, command, state)
    except Exception as exc:
        print(f"[MQTT] Bad command message: {exc}")


# -------------------------------------------------------------
