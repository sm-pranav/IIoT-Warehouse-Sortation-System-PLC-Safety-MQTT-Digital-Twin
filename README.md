# IIoT Smart Sortation Conveyor

A warehouse sortation conveyor simulation using Siemens S7-1200 PLC, Python IoT gateway, and live browser dashboard with digital twin.

## What the machine does

Mixed cartons and totes arrive from an upstream infeed. An **infeed** is where loads enter a machine. Three photo-electric sensors, also called **photo-eyes**, identify the destination class of each load. A pneumatic diverter then pushes that load into one of three outbound lanes.

Each lane passes its load to downstream equipment. That equipment can be an **AGV** (Automated Guided Vehicle), an **RGV** (Rail Guided Vehicle), or an **AS/RS** infeed conveyor. An AS/RS is an Automated Storage and Retrieval System: an automated warehouse that stores and retrieves loads.

The important rule is that the sorter asks for permission before releasing a load. The downstream machine sends a `Downstream_Ready` signal. If it is not ready, the diverter does not fire. The PLC remembers that a load is waiting, sets a hold flag, and releases the load only after readiness returns. This agreement between machines is a **process interlock**. It lets one machine work safely with the rest of the system instead of operating alone.

This is a small example of a common material-handling job. A cross-belt sorter performs the same job at a higher rate and with many more destinations. The downstream equipment—stacker cranes, AGVs, RGVs, and AS/RS equipment—is the same family of equipment used here.

## What it does, in detail

- The belt uses a latching start/stop circuit. A **latch** keeps the belt running after a momentary Start pushbutton press. The safety monitor input is normally closed, so pressing an emergency stop or breaking a wire removes the belt-run condition.
- The belt uses an inverter rather than a contactor. The PLC sends its run command on `Q0.6`, sends an analogue speed reference on `QW80`, and receives the drive fault contact on `I1.0`.
- Three lanes receive sorted loads. Each diverter gets a fixed two-second pulse from a pulse timer. The pulse lasts long enough to move a load even though the class sensor sees it only briefly.
- A load waits when the downstream vehicle is unavailable. The `Interlock_Hold` status is also sent to the dashboard so an operator can see that the machine is waiting rather than broken.
- The PLC keeps a count for every lane and for all loads. It also records a reject if the entry sensor sees a load but no diverter fires within three seconds.
- The PLC calculates live **KPIs** (Key Performance Indicators) in a shared data block: OEE, loads per minute, belt speed percentage, and motor uptime.
- It handles four alarm conditions: emergency stop, jam, sensor conflict, and inverter fault. Any active alarm stops the belt. The beacon flashes at 1 Hz.
- A browser dashboard displays numbers, alarms, interlock state, and a live two-dimensional model of the conveyor and downstream vehicle.


## How it is put together


```text
   TIA Portal (laptop)
     PLC program (Ladder + SCL)  -->  PLCSIM            control logic runs here
     WinCC HMI (optional)                                optional operator screen
                    |  S7 protocol (TCP 102)
            iot_gateway.py (python-snap7)               reads DB1 and creates JSON
                    |  MQTT  (Wi-Fi in a real plant)
            broker.hivemq.com                            public MQTT broker
                    |  MQTT over WebSocket (wss 8884)
            dashboard.html (browser)                    live dashboard + digital twin
```

**Telemetry** is data travelling upward for monitoring. Here, the PLC writes data into DB1. The Python gateway reads DB1 by byte offset every two seconds, converts the values to JSON, and publishes them.

**Control** travels downward. Dashboard buttons publish a small JSON command. The gateway writes the correct bit in DB1. Ladder logic then responds to that bit.

The dashboard is a small **digital twin**. A digital twin is a software model that follows a machine using live machine data. The screen draws the belt, loads, three lanes, and vehicle from PLC data rather than from a pre-recorded animation. For example, force a sensor in PLCSIM and a load appears in the dashboard model. Force a drive fault and the belt becomes red. This close link between control logic and model is a small example of a **cyber-physical system**.

In a real plant, the MQTT connection would normally use Wi-Fi or plant networking between the panel and a monitoring network. This project does not implement a production network design.

The PLC program deliberately uses two languages:

- **Ladder (LAD)** is a graphical, relay-style PLC language. It is used for on/off control: the belt latch, diverters, and interlock. Electricians can read this style easily on a live machine.
- **Structured Text (ST)** is called **SCL** by Siemens. It is a text PLC language that is better for arithmetic, counters, OEE, throughput, and alarm evaluation.

### An honest design decision

Safety is intentionally not implemented by the standard PLC program. It might look easy in simulation to read an emergency-stop input and switch PLC outputs off. That is not sufficient safety design. A standard PLC and a program written by one person are not certified safety devices and must not be the only means that removes dangerous motion.

In the design, the emergency stop uses normally closed wiring through a **safety relay**. The safety relay performs the safety function: it removes the drive's **STO** (Safe Torque Off) input, so the motor loses torque through hardware. It also drops a contactor with poles in series with all three diverter solenoids. The PLC only reads the safety relay auxiliary contact at `I0.2`. It uses that signal to report the alarm, stop counters, and show the operator what happened.

The design is framed around **IEC 60204-1** and **ISO 13849-1**. The emergency stop is a category 0 stop. Process faults are controlled category 2 stops. Read `electrical/electrical_design.md` for the safety reasoning, equipment interlock, and stop-category matrix.


## Simulation only, and what that means for the drawings

The S7-1200 control logic is real code and it runs in S7-PLCSIM. The field side is simulated: sensors and actuators are represented by values you force in a PLC watch table. You do not need to buy, wire, or connect equipment.

The `electrical/` folder contains **design deliverables**, not construction steps. The wiring diagram, I/O list, terminal schedule, and device list are computer-based engineering documents. They can be reviewed without any physical parts. They show field devices on paper. They are comparable to documents that EPLAN Electric P8 or AutoCAD Electrical can create.

Do not treat these learning documents as authorization to construct or alter a real machine. Real safety and electrical work needs qualified professionals, formal risk assessment, and validated site-specific design.



| Component | Detail |
|:--|:--|
| PLC | Siemens S7-1200, CPU 1214C DC/DC/DC (`6ES7 214-1AG40-0XB0`) |
| Analog output | SB 1232 AQ signal board (`6ES7 232-4HA30-0XB0`), provides `QW80` |
| Engineering software | TIA Portal V18 (STEP 7 Professional, optional WinCC Basic) |
| Simulator | S7-PLCSIM V18 |
| PLC languages | Ladder (LAD) and Structured Text (SCL), IEC 61131-3 |
| Gateway | Python 3.10+, `python-snap7`, `paho-mqtt` |
| Messaging | MQTT via `broker.hivemq.com` (TCP 1883 for Python, WSS 8884 for the browser) |
| Dashboard | One HTML file using plain HTML/CSS/JavaScript and CDN-hosted `mqtt.js` |
| Electrical design | Hand-authored SVG schematic plus I/O, terminal, and device tables. Intended CAD tools: EPLAN Electric P8 / AutoCAD Electrical |
| Standards referenced | IEC 60204-1, ISO 13849-1, IEC 81346-2, IEC 60617, IEC 61131-3. UL 508A and CE are noted for export |



### I/O and memory

See `electrical/electrical_design.md` for device tags and terminal numbers for every point.

| Address | Tag | Meaning |
|:--|:--|:--|
| I0.0 | Start_Button | Start pushbutton |
| I0.1 | Stop_Button | Stop pushbutton (process stop) |
| I0.2 | E_Stop | Healthy safety-circuit monitor from the safety relay. `1` = healthy |
| I0.3 | Sensor_Entry | Load entering the sorter |
| I0.4 | Sensor_Class1 | Destination class 1 (small) |
| I0.5 | Sensor_Class2 | Destination class 2 (medium) |
| I0.6 | Sensor_Class3 | Destination class 3 (large) |
| I0.7 | Jam_Sensor | Photo-eye at the divert junction |
| I1.0 | VFD_Fault | Inverter fault. `1` = drive tripped |
| I1.1 | Downstream_Ready | Handshake from AGV / RGV / AS-RS infeed. `1` = ready |
| Q0.0 | Conveyor_Motor | Internal belt-run state; run lamp and line permissive |
| Q0.1 | Diverter_Lane1 | Diverter, lane 1 |
| Q0.2 | Diverter_Lane2 | Diverter, lane 2 |
| Q0.3 | Diverter_Lane3 | Diverter, lane 3 |
| Q0.4 | Alarm_Beacon | Fault beacon; flashes |
| Q0.5 | Alarm_Horn | Fault horn |
| Q0.6 | VFD_Run | Run command to the inverter |
| IW64 | Speed_Setpoint | Speed potentiometer, `0-27648 = 0-10 V` |
| QW80 | VFD_Speed_Ref | Inverter reference, `0-27648 = 0-10 V` |
| M0.0 | Mode_Auto | AUTO mode bit |
| M0.1 | Mode_Manual | MANUAL mode bit |
| M0.2 | Mode_Fault | FAULT mode bit |
| M10.5 | Clock_1Hz | 1 Hz clock from clock memory byte MB10 |

`Q0.0` and `Q0.6` come from the same belt-run condition but have different purposes. `Q0.0` is the internal machine state. It drives the run lamp and a permissive contact for a neighbouring conveyor. `Q0.6` is the physical run command that goes to the drive. Keeping them separate makes the drive connection clear in both software and documentation.

### Blocks

| Block | Language | Role |
|:--|:--|:--|
| OB1 (Main) | LAD | Calls FB1, FB2, FB3, and FB4 every PLC scan |
| FB1 ConveyorControl | LAD | Belt latch, modes, speed reference, VFD run, alarm outputs |
| FB2 SortingLogic | LAD | Object present, downstream interlock, three two-second diverter pulses |
| FB3 ProductionCounter | SCL | Counts, rejects, OEE, throughput, speed percentage, uptime, mode integer |
| FB4 AlarmHandler | SCL | Emergency stop, jam, sensor conflict, inverter fault, alarm code |
| DB1 ConveyorData | data | Shared non-optimized 32-byte data block |

FB3 and FB4 are in `code/conveyor_plc_structured_text.st`. Build the short Ladder blocks as follows.

**FB1 ConveyorControl**

Network 1 is the motor latch. `Conveyor_Motor` turns on when `Start_Button`, `Cmd_Start`, or the `Conveyor_Motor` seal-in contact is true. It can stay on only while `Stop_Button`, `E_Stop`, `Alarm_Active`, and `Cmd_Stop` are all clear. Those four conditions are normally-closed contacts in series.

```text
   Start_Button      Stop_Button  E_Stop  Alarm_Active  Cmd_Stop   Conveyor_Motor
 +----| |----+----------|/|--------|/|-------|/|----------|/|---------( )--
 |           |
 +--| |------+   Conveyor_Motor (seal-in)
 +--| |------+   Cmd_Start (remote)
```

Network 2 handles modes. `Cmd_Mode_Auto` sets `Mode_Auto` and resets `Mode_Manual`. `Cmd_Mode_Manual` does the opposite. `Alarm_Active` drives `Mode_Fault`.

Network 3 handles speed. When `Conveyor_Motor` is on, MOVE `Speed_Setpoint` to `VFD_Speed_Ref`. When it is off, MOVE `0` to `VFD_Speed_Ref`. This prevents the drive from creeping when the belt is stopped.

Network 4 drives alarm outputs. `Alarm_Beacon = Alarm_Active AND Clock_1Hz`, so the beacon flashes once per second. `Alarm_Horn = Alarm_Active`, so the horn stays on while the alarm is active.

Network 5 connects the internal run state to the drive command: `Conveyor_Motor` drives `VFD_Run` (`Q0.6`).

**FB2 SortingLogic**

Use static variables `Ready`, `Req_Lane1`, `Req_Lane2`, and `Req_Lane3`, plus three TP timer instances.

Network 1 copies `Sensor_Entry` into `Object_Present` at DB1 bit `27.0`.

Network 2 creates the handshake. `Downstream_Ready` (`I1.1`) is in parallel with `ConveyorData.Cmd_Downstream_Ready` (`30.5`). Either signal drives the static `Ready` bit and `ConveyorData.Downstream_Ready` (`27.3`) for display. The dashboard can therefore demonstrate the interlock without forcing the physical input.

Networks 3, 5, and 7 are request latches, one for each class. `Sensor_Class1 AND Conveyor_Motor` sets `Req_Lane1`; use the same pattern for classes 2 and 3. The request must latch because a photo-eye sees a load only briefly. The latch keeps the request alive until permission arrives.

Networks 4, 6, and 8 perform the divert action. For lane 1, `Req_Lane1 AND Ready AND Conveyor_Motor` starts a TP timer with `PT := T#2s`. The timer output drives `Diverter_Lane1` and resets `Req_Lane1`.

```text
  Req_Lane1   Ready   Conveyor_Motor       TP_Class1
 ----| |------| |---------| |----------[ IN      Q ]-----( )-----
                                       [ PT=T#2s   ]  Diverter_Lane1
                                                        ( R ) Req_Lane1
```

A **TP** timer produces one clean, fixed-duration pulse when its input becomes true. It is appropriate for a diverter because the diverter needs a full two-second kick even when the sensor signal is short. Resetting the request on this rung is safe: after the TP starts, it holds its output for the complete preset time.

Network 9 creates the hold flag. Any `Req_Lane1`, `Req_Lane2`, or `Req_Lane3` in series with a normally-closed `Ready` contact drives `ConveyorData.Interlock_Hold` (`27.2`). In plain words: a load is waiting and downstream permission is absent.

**OB1** calls all four blocks during every scan. FB1 and FB2 read tags and DB1 directly, so they need no parameters. Wire FB3 and FB4 as follows:

- FB3: `Enable`=`TRUE`, `Reset`=`ConveyorData.Cmd_Reset`, `Divert1/2/3`=`Q0.1/Q0.2/Q0.3`, `Entry_Sensor`=`I0.3`, `Motor_On`=`Q0.0`, `Speed_Raw`=`IW64`, `OneSec_Clock`=`M10.5`, `Auto_Mode`=`M0.0`, `Manual_Mode`=`M0.1`, `Alarm`=`ConveyorData.Alarm_Active`.
- FB4: `EStop_NC`=`I0.2`, `Jam_Sensor`=`I0.7`, `Class1_Sensor`=`I0.4`, `Class2_Sensor`=`I0.5`, `Class3_Sensor`=`I0.6`, `Drive_Fault`=`I1.0`.

### DB1 data layout — the data contract

DB1 is exactly **32 bytes** and must be non-optimized. The gateway reads these offsets exactly, so do not change the variable order. Lane 1 corresponds to class 1, lane 2 to class 2, and lane 3 to class 3.

| Offset | Name | Type | Offset | Name | Type |
|:--|:--|:--|:--|:--|:--|
| 0 | Total_Count | Int | 26.0 | Motor_Running | Bool |
| 2 | Lane1_Count | Int | 26.1 | Alarm_Active | Bool |
| 4 | Lane2_Count | Int | 26.2 | Jam_Detected | Bool |
| 6 | Lane3_Count | Int | 26.3 | System_Running | Bool |
| 8 | Reject_Count | Int | 26.4 | Sorting_Small | Bool |
| 10 | OEE | Real | 26.5 | Sorting_Medium | Bool |
| 14 | Throughput | Real | 26.6 | Sorting_Large | Bool |
| 18 | Uptime_Seconds | DInt | 26.7 | EStop_Active | Bool |
| 22 | Speed_Actual | Int | 27.0 | Object_Present | Bool |
| 24 | Mode | Int | 27.1 | VFD_Fault | Bool |
| 28 | Active_Alarm_Code | Int | 27.2 | Interlock_Hold | Bool |
| 30.0 | Cmd_Start | Bool | 27.3 | Downstream_Ready | Bool |
| 30.1 | Cmd_Stop | Bool | 30.3 | Cmd_Mode_Auto | Bool |
| 30.2 | Cmd_Reset | Bool | 30.4 | Cmd_Mode_Manual | Bool |
| 30.5 | Cmd_Downstream_Ready | Bool | | | |

`Mode` values are `0 STOP`, `1 AUTO`, `2 MANUAL`, and `3 FAULT`. `Active_Alarm_Code` values are `0 none`, `1 E-Stop`, `2 jam`, `3 sensor fault`, and `4 inverter fault`. Bits `27.4-27.7`, `30.6-30.7`, and byte `31` are spare.

Only `27.1`, `27.2`, `27.3`, and `30.5` were added in this version. Existing offsets remain unchanged, and DB1 is still 32 bytes. Therefore, the gateway still performs one 32-byte read.



```text
IIoT-Smart-Sortation-Conveyor-S7-1200/
├── README.md
├── control_specification.md                # specification, lifecycle, operation, maintenance, glossary
├── code/
│   ├── conveyor_plc_structured_text.st     # DB1 + FB3 (counters/KPIs) + FB4 (alarms)
│   ├── iot_gateway.py                      # reads DB1 over S7 and bridges it to MQTT
│   └── dashboard.html                      # dashboard + digital twin (open directly)
└── electrical/
    ├── wiring_diagram.svg                  # control schematic; opens in a browser
    └── electrical_design.md                # I/O list, terminal schedule, device list,
                                            # Mitsubishi map, safety and interlocks
```

The SCL file contains DB1 and the two Structured Text blocks. Build the two Ladder blocks, FB1 and FB2, the OB1 calls, and the tag table manually in TIA Portal. The required details are listed below.

`control_specification.md` is the functional specification used to create the program. It includes the sequence of operation, alarms, interlocks, acceptance tests, operation guidance, maintenance information, and a glossary. `electrical/electrical_design.md` contains the tables behind the schematic.



- TIA Portal V18 with STEP 7 Professional and S7-PLCSIM. WinCC Basic is optional because the browser dashboard does not need WinCC.
- Python 3.10 or later.

```powershell
pip install python-snap7 paho-mqtt
```

On Windows, `python-snap7` needs the native `snap7.dll` library. Recent Python packages normally include it. If you see `snap7 library not found`, download snap7 from sourceforge. Take the 64-bit `snap7.dll` from `release\Windows\Win64\` and place it next to `iot_gateway.py` or in `C:\Windows\System32`. The DLL bitness must match the Python installation bitness.



### 1. Build the PLC program in TIA Portal

1. Create a project and add the CPU 1214C DC/DC/DC (`6ES7 214-1AG40-0XB0`).
2. Add the SB 1232 AQ signal board. It provides analogue output `QW80`.
3. In CPU properties, enable the clock memory byte and leave it as MB10. This makes `M10.5` available as a 1 Hz bit.
4. Create a tag table with every tag in the I/O table, including `I1.0`, `I1.1`, and `Q0.6`.
5. Create global DB1 named `ConveyorData`. Add variables in the DB1 table order. In its properties, turn off **Optimized block access**. This is required for the Python gateway.
6. Create SCL blocks FB3 (`ProductionCounter`) and FB4 (`AlarmHandler`). Paste their code from `code/conveyor_plc_structured_text.st`.
7. Create Ladder blocks FB1 (`ConveyorControl`) and FB2 (`SortingLogic`) and build the networks described above.
8. In OB1, call FB1, FB2, FB3, and FB4. Accept an instance DB for each block and wire FB3 and FB4 inputs as listed.
9. Compile the complete program. A successful compile is your first checkpoint before simulation.

### 2. Start the simulation

Start S7-PLCSIM, download the program, and set the simulated CPU to RUN. The expected checkpoint is a green RUN state in PLCSIM.

### 3. Run the gateway

```powershell
pip install python-snap7 paho-mqtt
python code/iot_gateway.py
```

The gateway connects to PLCSIM at `127.0.0.1`, rack `0`, slot `1`. It reads 32 bytes from DB1 and publishes JSON every two seconds to `iiot/conveyor/demo01/telemetry`. It also subscribes to `iiot/conveyor/demo01/cmd`.

A session ID helps separate this demo from other users of the shared broker. Change `SESSION_ID` near the top of the Python file if you need a different one.

### 4. Open the dashboard

Double-click `code/dashboard.html` to open it in a browser. Enter the same session ID used by the gateway and select **Connect**. The status dot should turn green when the dashboard reaches the broker.



With PLCSIM in RUN, create a watch table containing the tags below. Modify simulated inputs and observe the outputs and DB values. The gateway console and dashboard should show the same state. For the complete test list and pass criteria, see `control_specification.md`.

1. **Enable the safety input.** Set `E_Stop` to `1`. Because this is normally closed monitoring, `1` means the safety circuit is healthy. Checkpoint: the belt cannot start while it is `0`.
2. **Start the belt.** Set `Start_Button` to `1`, then return it to `0`. Checkpoint: `Conveyor_Motor` and `VFD_Run` become true and remain true. This proves the latch.
3. **Set the speed.** Set `Speed_Setpoint` to `13824`. Checkpoint: `Speed_Actual` is approximately `50`, and `VFD_Speed_Ref` follows the setpoint while the belt runs.
4. **Sort a load.** With `Downstream_Ready` at `1`, set `Sensor_Class1` to `1` and then `0`. Checkpoint: `Diverter_Lane1` is true for approximately two seconds; `Lane1_Count` and `Total_Count` both increase by one. Repeat for `Sensor_Class2` and `Sensor_Class3`.
5. **Hold a load on the interlock.** Set `Downstream_Ready` to `0` and keep `Cmd_Downstream_Ready` clear. Pulse `Sensor_Class1`. Checkpoint: no diverter fires, `Interlock_Hold` becomes true, and no count changes. Set `Downstream_Ready` to `1`. Checkpoint: the diverter pulses, the count rises, and the hold clears.
6. **Repeat from the dashboard.** With `Downstream_Ready` at `0`, press **Downstream Ready** on the dashboard. Checkpoint: `Cmd_Downstream_Ready` is set, the held load diverts, and the twin vehicle becomes green.
7. **Make a reject.** Set `Sensor_Entry` to `1` and keep it true for more than three seconds without a class sensor. Checkpoint: `Reject_Count` increases by one.
8. **Trip the inverter.** Set `VFD_Fault` to `1`. Checkpoint: `ConveyorData.VFD_Fault` is true, `Active_Alarm_Code` is `4`, `Mode` is `3`, the beacon flashes, and the belt stops. Return it to `0`; the alarm should clear.
9. **Trigger a jam.** Set `Jam_Sensor` to `1` for more than five seconds. Checkpoint: `Jam_Detected` and `Alarm_Active` become true and alarm code `2` appears. Return it to `0`; the alarm should clear.
10. **Test the emergency-stop reporting path.** Set `E_Stop` to `0`. Checkpoint: the belt stops, `EStop_Active` becomes true, and alarm code `1` appears. On a real machine, the safety relay would already have removed motion through hardware; the PLC only reports this status.

On the dashboard, lane cards and total count should increase as you sort. The digital twin should show loads moving and entering the right lane. The vehicle shows ready or not ready, the interlock tile shows HOLD when a load waits, and the alarm panel shows the active alarm name and code.



| Symptom | Cause and fix |
|:--|:--|
| Dashboard and gateway show only zeros or incorrect values | DB1 is still optimized. Turn off **Optimized block access** on DB1, compile, and download again. |
| Gateway cannot connect or reports an unreachable peer | PLCSIM is not in RUN, or the communication address is wrong. Use `127.0.0.1`, rack `0`, slot `1`. |
| Gateway raises `snap7 library not found` on Windows | Put 64-bit `snap7.dll` beside `iot_gateway.py` or in `C:\Windows\System32`. It must match Python bitness. |
| A diverter never fires | Check three conditions: belt running, downstream handshake high, and request latch set. Check `Interlock_Hold`. |
| Belt will not start | `E_Stop` must be `1` and no alarm may be active. |
| Loads count but the twin shows nothing | The twin spawns a load from count changes, so it needs telemetry. Confirm matching session IDs and a green dashboard status dot. |
| Dashboard status dot stays red | The dashboard session ID must match the gateway session ID. The browser also needs access to `broker.hivemq.com` through WebSocket port `8884`. |
| Uptime and OEE never move | Clock memory is disabled. Enable MB10, compile, and download again. |

## Portability to Mitsubishi

Japanese plants commonly use Mitsubishi equipment alongside Siemens equipment. `electrical/electrical_design.md` includes a Siemens-to-Mitsubishi address map: Siemens `I` inputs map to `X`, `Q` outputs to `Y`, data blocks to `D` registers, `TON_TIME` to an equivalent timer instruction, and `R_TRIG` to a rising-edge contact.

The logic can be ported conceptually to GX Works because it is standard sequence control. A latching start/stop rung, a timed diverter pulse, edge-counted total, and interlock contact follow the same engineering idea. However, addressing, data organization, and development tools change. Mitsubishi has no direct equivalent of the Siemens TP timer, so rebuild the pulse logic and test it again.

This project provides the Siemens implementation and a studied mapping. It does **not** claim that a Mitsubishi project has been built or tested on real hardware.



The complete project runs in PLCSIM. Inputs are forced to simulate sensors. It demonstrates control logic, electrical-design documentation, and a data path. It does not demonstrate physical wiring, field commissioning, or real-machine operation.

**The most important limitation:** the safety architecture is designed to the intent of ISO 13849-1 Category 3. It uses a normally closed dual-channel loop, a certified safety relay, STO, and a solenoid contactor as two actuators. However, its **quantified performance level has not been calculated or verified**. This requires MTTFd, diagnostic coverage, common-cause failure scoring, and review by a competent safety engineer before any build. The reasoning is documented; it is not a certification claim.

Other stated limits are:

- The servo transfer unit is specified and drawn but not programmed. Inverter control is implemented; servo control is design-level only.
- The MQTT connection uses a public broker without authentication or encryption. This is acceptable only for a demo and is unsuitable for a real plant.
- OEE and throughput formulas are simplified.
- Counters are 16-bit and reset on a power cycle.
- There is no historical logging.

Useful next development steps, in order, are: replace the PLC link with OPC UA; add a database for shift history; extend the one ready signal to load-ready / ready-to-receive / transfer-complete with a timeout; program the servo transfer; and use barcode-based routing instead of size classes.



Pranav S M
