# Control Specification — IIoT Smart Sortation Conveyor

**Equipment** Warehouse sortation conveyor feeding a downstream AGV / RGV / AS-RS infeed  
**Document** `PSM-MHS-SPEC-001`, Rev 1  
**Author** Pranav S M  
**Date** 2026-09-19  
**Related documents** `electrical/wiring_diagram.svg`, `electrical/electrical_design.md`, `README.md`

> **Important learning-document notice.** This is a beginner-friendly explanation of an engineering design and PLC simulation. It is **not** a certified instruction for building, wiring, operating, commissioning, or modifying a real electrical or safety system. A real machine needs qualified electrical, controls, and safety engineers; the required risk assessment, calculations, inspections, validation, approvals, and site verification must be completed before use. Explanations of the PLC logic below describe **process control**. They do not replace the separate, hardware-based **people-safety** functions.

This is the functional and control specification: it explains what the machine is meant to do, the order in which it does it, what stops it, and how a user can tell it is working. It is the basis from which the PLC program was written and the reference against which the finished simulated machine would be tested. A **PLC** (Programmable Logic Controller) is an industrial computer designed to run control steps reliably and repeatedly.

**Implementation note.** The machine exists in software only. The control logic is genuine Siemens S7-1200 code running in S7-PLCSIM, and simulated field inputs are made by forcing PLC inputs. No hardware is installed. The electrical design package describes the panel and field wiring as it would be built; it is not permission or certification to build it.

---

## Contents

1. Scope and system description
2. Lifecycle position of this document
3. Architecture
4. I/O summary
5. Shared data block DB1
6. Operating modes
7. Sequence of operation
8. Production counting and KPIs
9. Alarm list
10. Interlocks
11. Safety
12. Acceptance criteria
13. Operation and maintenance
14. Limitations and future work
15. Glossary

---

## 1. Scope and system description

### 1.1 What the machine does

Cartons and totes arrive from an upstream infeed conveyor in a mixed stream. The sortation conveyor identifies each load's destination class, then sends it into one of three outbound lanes. Each lane transfers its load to downstream equipment: an AGV pickup station, an RGV, or an AS/RS infeed conveyor.

Three photo-electric sensors, mounted at different heights, classify each load. A photo-electric sensor uses light to detect an object. A pneumatic diverter on each lane uses compressed air to push the load off the belt. An inverter controls belt speed. The PLC counts production, calculates live KPIs, raises alarms, and performs a handshake with downstream equipment before releasing a load.

This is a **process-control** description: it manages material flow and equipment behaviour. It is not a people-safety design instruction. People safety is handled by the hardware emergency-stop chain described in section 11 and still requires qualified-engineer verification for any real installation.

### 1.2 Where it fits in material handling

Sortation changes one mixed flow of loads into several sorted flows. It can sit between receiving and storage, or between picking and dispatch. Its purpose is to keep downstream machines supplied with the right loads. This is a simple three-lane member of that equipment family. Industrial cross-belt sorters provide the same basic function at a much higher rate and with many more destinations. The downstream equipment named here—stacker cranes, AGVs, RGVs, and AS/RS—is the same type of equipment referenced by this project.

### 1.3 Design intent

- **Control logic lives in the PLC.** The gateway and dashboard are monitoring layers. If both are switched off, the simulated machine logic still runs and still counts correctly. This separation is chosen so monitoring failure does not take over basic control.
- **Safety lives in hardware.** The emergency stop removes motion through a safety relay and drive STO, not through the program. This is intentional: a normal PLC program is not the safety function.
- **One data contract.** Everything shared between layers passes through one 32-byte data block at fixed byte offsets. It is documented once and must match everywhere, preventing different layers from interpreting data differently.
- **No load is released blind.** The sorter asks downstream equipment for permission before diverting. This protects equipment and product flow; it is a process interlock, not a substitute for people safety.

## 2. Lifecycle position of this document

The project follows the order used by a real engineering job, with this specification at the front. Writing it first settles decisions—such as where safety belongs, what stops the belt, and how an interlock behaves—before those decisions become PLC code or wiring.

| Phase | What was produced | Where it is |
|:--|:--|:--|
| **Detailed design** | I/O list, wiring diagram, terminal schedule, device list, safety architecture, this specification | `electrical/`, this document |
| **Implementation** | S7-1200 program (LAD + SCL), gateway, dashboard | `code/` |
| **Testing** | Acceptance criteria, exercised by forcing inputs in PLCSIM | section 12 |
| **Maintenance / operation support** | Start-up and shutdown procedure, alarm response, troubleshooting, maintenance schedule | section 13 |

This order does not certify a physical system. For real work, qualified engineers must verify the design, installation, testing, standards compliance, and site conditions.

## 3. Architecture

```
   Control layer        S7-1200 program (LAD + SCL) running in S7-PLCSIM
                        All control logic and all KPI maths. Writes DB1.
                                 |
                                 |  S7 protocol, TCP 102
                                 v
   Edge layer           iot_gateway.py  (python-snap7)
                        Reads 32 bytes from DB1 every 2 s, builds JSON,
                        publishes over MQTT. Writes command bits back.
                                 |
                                 |  MQTT  (Wi-Fi in a real deployment)
                                 v
   Monitoring layer     MQTT broker  ->  dashboard.html in a browser
                        Live figures, alarms, 2D digital twin, commands.
```

The three layers are arranged like a typical plant system: deterministic control at the bottom, an edge device that speaks both communication protocols in the middle, and supervisory monitoring on top. **Deterministic** here means the PLC performs the same control task predictably each scan.

**Digital twin / CPS framing.** The dashboard displays a live 2D model of the sortation line and downstream AGV. Each display element is driven by the PLC's data, so the model follows the simulated machine. Together they form a small **cyber-physical system (CPS)**: PLC and I/O are the physical side, the screen model is the cyber side, and MQTT keeps them in step. In a plant installation, this connection would run wirelessly over Wi-Fi from the panel to the plant network, avoiding a new cable run. This communication is for monitoring and commands, not a certified safety channel.

## 4. I/O summary

Full device-tag, terminal, and wire-number detail is in `electrical/electrical_design.md`. **I/O** means the input and output signals by which the PLC reads the machine and commands it.

| Address | Tag | Type | Description |
|:--|:--|:--|:--|
| I0.0 | `Start_Button` | DI | Start pushbutton |
| I0.1 | `Stop_Button` | DI | Stop pushbutton (process stop) |
| I0.2 | `E_Stop` | DI | Safety circuit healthy monitor. 1 = healthy |
| I0.3 | `Sensor_Entry` | DI | Load entering the sorter |
| I0.4 | `Sensor_Class1` | DI | Destination class 1 (small) |
| I0.5 | `Sensor_Class2` | DI | Destination class 2 (medium) |
| I0.6 | `Sensor_Class3` | DI | Destination class 3 (large) |
| I0.7 | `Jam_Sensor` | DI | Photo-eye at the divert junction |
| I1.0 | `VFD_Fault` | DI | Inverter fault. 1 = drive tripped |
| I1.1 | `Downstream_Ready` | DI | Handshake from the downstream transport. 1 = ready |
| Q0.0 | `Conveyor_Motor` | DQ | Internal belt-run state; run lamp and line permissive |
| Q0.1 | `Diverter_Lane1` | DQ | Diverter, lane 1 |
| Q0.2 | `Diverter_Lane2` | DQ | Diverter, lane 2 |
| Q0.3 | `Diverter_Lane3` | DQ | Diverter, lane 3 |
| Q0.4 | `Alarm_Beacon` | DQ | Beacon, flashes at 1 Hz on alarm |
| Q0.5 | `Alarm_Horn` | DQ | Horn, steady on alarm |
| Q0.6 | `VFD_Run` | DQ | Run command to the inverter |
| IW64 | `Speed_Setpoint` | AI | Speed potentiometer, 0–27648 = 0–10 V |
| QW80 | `VFD_Speed_Ref` | AQ | Inverter speed reference, 0–27648 = 0–10 V |
| M0.0 | `Mode_Auto` | M | AUTO mode bit |
| M0.1 | `Mode_Manual` | M | MANUAL mode bit |
| M0.2 | `Mode_Fault` | M | FAULT mode bit |
| M10.5 | `Clock_1Hz` | M | 1 Hz clock from clock memory byte MB10 |

DI/DQ mean digital input/output: an on-or-off signal. AI/AQ mean analogue input/output: a value across a range. `M` is internal PLC memory.

### 4.1 Program blocks

| Block | Language | Role |
|:--|:--|:--|
| OB1 Main | LAD | Calls FB1, FB2, FB3, FB4 every scan |
| FB1 `ConveyorControl` | LAD | Belt latch, mode selection, speed reference, VFD run, beacon and horn |
| FB2 `SortingLogic` | LAD | Object-present bit, downstream interlock, three 2 s diverter pulses |
| FB3 `ProductionCounter` | SCL | Counts, rejects, throughput, OEE, uptime, speed %, mode integer |
| FB4 `AlarmHandler` | SCL | E-Stop, jam, sensor conflict, inverter fault, alarm code |
| DB1 `ConveyorData` | data | Shared data block, non-optimized, 32 bytes |

**LAD** (Ladder) is a graphical PLC language shaped like relay circuits, making on/off interlocks easy for an electrician to follow. **SCL** (Structured Control Language, a Structured Text form) is better for arithmetic, counting, and KPI mathematics. This division is made for readability and maintenance, not as a safety function.

## 5. Shared data block DB1

DB1 `ConveyorData` is **32 bytes** and must use **non-optimized (standard) block access**. The gateway reads fixed byte offsets, so only the classic predictable layout works. The variable order is fixed and is the shared data contract.

| Offset | Name | Type | Written by | Description |
|:--|:--|:--|:--|:--|
| 0 | `Total_Count` | Int | PLC | All sorted loads |
| 2 | `Lane1_Count` | Int | PLC | Class 1 → lane 1 |
| 4 | `Lane2_Count` | Int | PLC | Class 2 → lane 2 |
| 6 | `Lane3_Count` | Int | PLC | Class 3 → lane 3 |
| 8 | `Reject_Count` | Int | PLC | Entered but never sorted |
| 10 | `OEE` | Real | PLC | Overall equipment effectiveness, % |
| 14 | `Throughput` | Real | PLC | Loads per minute |
| 18 | `Uptime_Seconds` | DInt | PLC | Seconds the belt has run |
| 22 | `Speed_Actual` | Int | PLC | Belt speed, 0–100 % |
| 24 | `Mode` | Int | PLC | 0 STOP, 1 AUTO, 2 MANUAL, 3 FAULT |
| 26.0 | `Motor_Running` | Bool | PLC | Belt running |
| 26.1 | `Alarm_Active` | Bool | PLC | Master alarm flag |
| 26.2 | `Jam_Detected` | Bool | PLC | Jam timer elapsed |
| 26.3 | `System_Running` | Bool | PLC | System running |
| 26.4 | `Sorting_Small` | Bool | PLC | Diverter 1 active |
| 26.5 | `Sorting_Medium` | Bool | PLC | Diverter 2 active |
| 26.6 | `Sorting_Large` | Bool | PLC | Diverter 3 active |
| 26.7 | `EStop_Active` | Bool | PLC | Emergency stop active |
| 27.0 | `Object_Present` | Bool | PLC | Load at the entry sensor |
| 27.1 | `VFD_Fault` | Bool | PLC | Inverter fault active |
| 27.2 | `Interlock_Hold` | Bool | PLC | Load ready to divert, downstream not ready |
| 27.3 | `Downstream_Ready` | Bool | PLC | Mirror of the ready handshake, for display |
| 28 | `Active_Alarm_Code` | Int | PLC | 0 none, 1 E-Stop, 2 jam, 3 sensor fault, 4 VFD fault |
| 30.0 | `Cmd_Start` | Bool | gateway | Remote start |
| 30.1 | `Cmd_Stop` | Bool | gateway | Remote stop |
| 30.2 | `Cmd_Reset` | Bool | gateway | Reset counters |
| 30.3 | `Cmd_Mode_Auto` | Bool | gateway | Select AUTO |
| 30.4 | `Cmd_Mode_Manual` | Bool | gateway | Select MANUAL |
| 30.5 | `Cmd_Downstream_Ready` | Bool | gateway | Simulated downstream ready, for demonstration |

Bits 27.4–27.7 and 30.6–30.7 are spare, as is byte 31. Total size remains 32 bytes. `Int`, `DInt`, `Real`, and `Bool` are PLC data types: integer, double integer, floating-point number, and true/false respectively.

## 6. Operating modes

The machine is always in exactly one mode; `Mode` in DB1 carries its number.

| Mode | Value | Entered when | Behaviour |
|:--|:--|:--|:--|
| STOP | 0 | Power-up, or stop pressed, or no mode selected | Belt stopped, no diverting, no alarms |
| AUTO | 1 | `Cmd_Mode_Auto` while healthy | Belt runs, sorting runs automatically on the class sensors, interlock enforced |
| MANUAL | 2 | `Cmd_Mode_Manual` while healthy | Belt runs, intended for commissioning and clearing loads. Selecting MANUAL clears AUTO |
| FAULT | 3 | Any alarm active | Overrides every other mode. Belt command dropped, diverting stopped, beacon flashing |

FAULT overrides AUTO and MANUAL, preventing a contradictory running-and-faulted state. Selecting AUTO clears MANUAL and selecting MANUAL clears AUTO, so only one is active. Manual mode is described for commissioning/clearing loads in the simulation; it is not approval for a person to work near a real moving machine.

## 7. Sequence of operation

### 7.1 Start-up

| Step | Condition | Action |
|:--|:--|:--|
| 1 | Safety circuit healthy (`I0.2` = 1), no alarm active | Machine may be started |
| 2 | `Start_Button` (`I0.0`) or `Cmd_Start` pulsed | Belt latches on. `Q0.0` and `Q0.6` go true |
| 3 | Start released | Belt stays running through its own seal-in contact |
| 4 | Belt running | `QW80` follows `IW64`, so the drive follows the speed potentiometer |
| 5 | Belt stopped | `QW80` forced to 0, so the drive cannot creep |

A latch (also called a seal-in) uses the belt's own contact to keep a momentary start request active. It has a parallel start branch—start button OR seal-in OR remote start—then four normally closed stop conditions in series: stop button, safety monitor, master alarm, and remote stop. Any stop condition opens the rung. The belt output turns off, its seal-in opens, and it stays off. This is process-control behaviour; the hardware safety chain independently removes hazardous motion.

### 7.2 Sorting one load — the core sequence

| Step | Condition | Action | Notes |
|:--|:--|:--|:--|
| 1 | Load breaks `Sensor_Entry` (`I0.3`) | `Object_Present` (27.0) set | Also starts the 3 s reject watchdog |
| 2 | Load breaks one class sensor (`I0.4` / `I0.5` / `I0.6`) | Destination class identified | Belt must be running; diverters are inhibited when it is not |
| 3 | Downstream ready? `I1.1` **or** `Cmd_Downstream_Ready` true | Permission granted, go to step 4 | This is the equipment interlock |
| 3a | Downstream **not** ready | `Interlock_Hold` (27.2) set. No diverter pulse. Load held on the belt | Published to the HMI and dashboard so the operator sees why |
| 3b | Downstream becomes ready | `Interlock_Hold` cleared, go to step 4 | Held load is then diverted |
| 4 | Permission granted | Matching diverter pulses for **2 s** (pulse timer) | A fixed pulse, because the sensor only sees the load for an instant |
| 5 | Diverter pulse rises | Lane counter +1, `Total_Count` recalculated | Counted on the rising edge, so exactly one per load |
| 6 | Diverter pulse ends | Diverter retracts, ready for the next load | — |

A rising edge is the single instant a signal changes from off to on. Counting at that instant prevents a two-second output pulse from creating many counts. The equipment interlock protects flow and equipment; it is not a people-protection device.

### 7.3 Reject handling

If a load trips `Sensor_Entry` but no diverter fires within **3 seconds**, `Reject_Count` increments. This covers a load that no class sensor recognised, making the missed classification visible rather than silently losing it. A reject is a count, not an alarm, so the machine keeps running.

### 7.4 Shutdown

| Step | Condition | Action |
|:--|:--|:--|
| 1 | `Stop_Button` (`I0.1`) or `Cmd_Stop` pulsed | Belt latch breaks, `Q0.0` and `Q0.6` drop, `QW80` forced to 0 |
| 2 | Belt stopped | Diverting inhibited. Counters and KPIs retained |
| 3 | Emergency stop pressed | Hardware chain acts: STO removed, diverter power dropped. PLC raises alarm code 1 |

### 7.5 Alarm behaviour

Any alarm sets the master alarm flag. Its normally closed contact in the belt rung stops the belt. The beacon uses the 1 Hz clock bit and **flashes**; the horn has no clock contact and stays **steady**. `Mode` becomes 3 (FAULT). Alarms are self-clearing when their physical condition goes away. `Cmd_Reset` resets production counters, not live alarms.

## 8. Production counting and KPIs

FB3 calculates these values in the PLC, so numbers remain available even if the monitoring layer is not running. A KPI is a **key performance indicator**, a measurement used to understand production performance.

| Value | How it is calculated | Notes |
|:--|:--|:--|
| Lane counts | Rising edge of each diverter pulse, +1 | One count per load, even though the pulse lasts 2 s |
| `Total_Count` | Sum of the three lane counts | — |
| `Reject_Count` | Rising edge of the 3 s reject timer | Entered but never sorted |
| `Uptime_Seconds` | +1 per second while the belt runs | Driven by the 1 Hz clock bit |
| `Speed_Actual` | `Speed_Setpoint` × 100 / 27648 | Raw analogue count to 0–100 % |
| `Throughput` | `Total_Count` / run seconds × 60 | Loads per minute, guarded against divide-by-zero |
| `OEE` | Availability × Performance × Quality × 100 | See below |

**OEE** (Overall Equipment Effectiveness) combines three kinds of production loss into one percentage.

| Factor | Formula here | What loss it exposes |
|:--|:--|:--|
| Availability | run seconds / enabled seconds | Downtime |
| Performance | (loads / run seconds) ÷ 0.5, clamped to 1.0 | Running slower than the ideal rate. 0.5 loads/s = one every 2 s = 30 per minute |
| Quality | total / (total + rejects) | Loads that were not handled correctly |

Every division is guarded: a zero denominator gives 0.0, except quality gives 1.0 before any load has been handled. These deliberately simple formulas are further limited in section 14.

## 9. Alarm list

| Code | Alarm | Trigger | Delay | Effect | Reset |
|:--|:--|:--|:--|:--|:--|
| 0 | No alarm | — | — | — | — |
| 1 | Emergency stop | Safety monitor `I0.2` goes low (button pressed, wire broken, or relay dropped) | None | Hardware removes motion; PLC drops the belt command, beacon flashes | Release `-S1`, press the monitored reset. Alarm self-clears when the circuit is healthy |
| 2 | Conveyor jam | `Jam_Sensor` `I0.7` blocked continuously | **5 s** | Belt command drops, sorting stops, beacon flashes | Clear the blockage; self-clears |
| 3 | Sensor fault | Two or more class sensors on at once — impossible for one load | None | Belt command drops, sorting stops, beacon flashes | Correct the sensor; self-clears |
| 4 | Inverter fault | `VFD_Fault` `I1.0` goes high | None | Belt command drops, sorting stops, beacon flashes | Clear the drive trip; self-clears when `I1.0` goes low |

The priority order is 1, 2, 3, 4. Emergency stop wins because an operator needs to see that condition named first. `Active_Alarm_Code` carries the highest-priority active condition, while `Alarm_Active` is the OR of all alarm conditions.

The 5 s jam delay prevents false alarms: a normal passing load blocks the photo-eye briefly every cycle, whereas a jam remains in front of it. Alarm code 1 reports safety-chain status to the PLC; the physical hardware is what provides the actual safety stop.

## 10. Interlocks

An **interlock** is a required condition before an action is allowed. This machine uses four:

| # | Interlock | Rule | Why |
|:--|:--|:--|:--|
| 1 | **Downstream equipment** | A diverter may not pulse unless `Downstream_Ready` (`I1.1`) or `Cmd_Downstream_Ready` (30.5) is true. Otherwise `Interlock_Hold` is set and the load is held | Prevents pushing a load into empty space or into a vehicle that has not arrived or is still moving |
| 2 | **Belt running** | Diverters are inhibited unless the belt-run state is true | Diverting onto a stationary belt jams the lane |
| 3 | **Alarm** | The master alarm flag is a normally-closed contact in the belt rung | One rule for every fault: if anything is wrong, the belt stops |
| 4 | **Mode exclusivity** | Selecting AUTO resets MANUAL and vice versa; FAULT overrides both | Prevents contradictory states |

Interlock 1 is the main demonstration in this project. `electrical/electrical_design.md` section 9.4 explains its hazard and how a larger system would add a four-signal handshake with a timeout.

**Category.** All four are PLC **process interlocks**. They protect equipment and product flow. They sit beside, and never replace, the hardware people-safety chain in section 11. A real installation needs a qualified safety engineer to determine which transfer hazards must use safety-rated systems.

## 11. Safety

> **Safety boundary.** This learning/design document does not certify a safety function and must not be used alone to build or commission real machinery. Process stop, jam logic, sensor logic, and dashboard commands are not people-safety functions. Any physical system needs an appropriate risk assessment, safety calculations, validation, formal testing, and sign-off by competent qualified engineers.

Full analysis, including the stop-category matrix and standards framing, is in `electrical/electrical_design.md` section 9. The design summary is:

- **`-S1` emergency stop is wired normally closed.** A pressed button, cut wire, or loose terminal all produce a stop. The failure direction is therefore safe.
- **Two NC positive-opening contacts** feed two independent, cross-monitored channels into safety relay **`-K0`**.
- **`-K0` removes drive STO** (Safe Torque Off), so the motor can produce no torque in hardware. It also **drops contactor `-K9`**, whose poles are in series with all three diverter solenoids, so nothing can push.
- **Reset is monitored and manual.** Releasing the emergency stop does not restart the machine.
- **The PLC is not part of the safety function.** It reads `-K0` auxiliary contact `I0.2` for indication, alarm, and belt-command behaviour. That is process behaviour, not safety.
- **Framed to IEC 60204-1** (stop functions, stop categories, isolator, emergency stop) **and ISO 13849-1** (architecture intended to satisfy Category 3).
- **Stated limitation:** quantified performance level has not been calculated or verified. A competent safety engineer must complete that work before any real build.

Stop categories used are **category 0** for the emergency stop (immediate removal of power to motion) and **category 2** controlled stop for jams, sensor faults, inverter faults, and the process stop. These descriptions explain the design intent only; they are not instructions to install, alter, validate, or bypass safety circuits.

## 12. Acceptance criteria

Each test runs with the program downloaded to PLCSIM and the CPU in RUN. Field devices are simulated by forcing inputs in a TIA Portal watch table. Every test can be observed in the watch table, gateway console, and dashboard. These are simulation acceptance tests, not a substitute for real-machine electrical, functional, or safety validation.

| # | Test | Method | Pass criteria |
|:--|:--|:--|:--|
| 1 | Safety monitor blocks start | Force `I0.2` = 0 | Belt cannot start. `EStop_Active` true, `Alarm_Active` true, `Mode` = 3, alarm code 1 |
| 2 | Belt latch | `I0.2` = 1, pulse `I0.0` on then off | `Q0.0` and `Q0.6` go true and **stay** true after the button is released |
| 3 | Speed reference | Set `IW64` = 13824 | `Speed_Actual` ≈ 50. `QW80` follows `IW64` while running |
| 4 | Speed forced to zero | Stop the belt | `QW80` = 0 |
| 5 | Sort class 1 | Belt running, downstream ready, pulse `I0.4` | `Q0.1` pulses for ≈ 2 s. `Lane1_Count` +1, `Total_Count` +1 |
| 6 | Sort class 2 and 3 | Repeat with `I0.5`, `I0.6` | `Q0.2` / `Q0.3` pulse. `Lane2_Count` / `Lane3_Count` +1 |
| 7 | **Interlock holds a load** | Set `I1.1` = 0 and `Cmd_Downstream_Ready` = 0. Pulse `I0.4` | **No diverter pulse.** `Interlock_Hold` (27.2) true. `Lane1_Count` unchanged |
| 8 | **Interlock releases** | With the hold set, set `I1.1` = 1 | Diverter pulses, `Interlock_Hold` clears, `Lane1_Count` +1 |
| 9 | Interlock from the dashboard | With `I1.1` = 0, press **Downstream Ready** on the dashboard | `Cmd_Downstream_Ready` (30.5) set, `Downstream_Ready` (27.3) true, the held load diverts |
| 10 | Reject count | Set `I0.3` = 1 and hold > 3 s with no class sensor | `Reject_Count` +1 |
| 11 | Jam alarm | Set `I0.7` = 1 and hold > 5 s | `Jam_Detected` true, `Alarm_Active` true, `Mode` = 3, alarm code 2, beacon flashing, belt stopped. Clears when `I0.7` = 0 |
| 12 | Sensor conflict alarm | Set `I0.4` and `I0.5` = 1 together | `Alarm_Active` true, alarm code 3 |
| 13 | **Inverter fault alarm** | Set `I1.0` = 1 | `VFD_Fault` (27.1) true, `Alarm_Active` true, `Mode` = 3, **alarm code 4**, belt command drops. Clears when `I1.0` = 0 |
| 14 | Beacon flashes, horn steady | During any alarm, watch `Q0.4` and `Q0.5` | `Q0.4` toggles once per second; `Q0.5` steady on |
| 15 | Remote commands | Press Start, Stop, Reset, AUTO, MANUAL on the dashboard | The matching bit in byte 30 pulses; the PLC acts; the gateway logs each command |
| 16 | Counter reset | Press Reset with counts non-zero | All counts and time accumulators return to 0. Live alarms are unaffected |
| 17 | Telemetry integrity | Compare the dashboard against the watch table | Every value matches: counts, mode, speed, OEE, throughput, uptime, alarm code, VFD fault, interlock state |
| 18 | Digital twin follows the machine | Sort loads while watching the animation | Loads appear, travel, and are diverted into the correct lane; the AGV shows ready or busy; the fault and hold states are drawn |
| 19 | Gateway resilience | Stop PLCSIM while the gateway runs, then restart it | The gateway reports the lost connection, retries, and resumes publishing without being restarted |
| 20 | Mode exclusivity | Select AUTO then MANUAL | Only one mode bit is true at a time. `Mode` reads 1 then 2 |

Tests 7, 8, 9, and 13 were added for this machine version: the equipment interlock and inverter fault. In a real project, tests involving safeguarding or electrical power require controlled procedures and qualified people; do not use forced simulated inputs as real safety validation.

## 13. Operation and maintenance

This section is written for the person who operates or maintains the machine, not for its original builder. It remains a learning/design description only. Real operation, maintenance, isolation, emergency recovery, and safety testing must use employer-approved procedures and competent authorized personnel.

### 13.1 Start-up procedure

1. Check the machine is clear of loads, tools, and people. Close all guards.
2. Turn the main isolator `-Q0` to ON.
3. Check emergency stop `-S1` is released (pulled out).
4. Press safety reset `-S4`. The safety relay picks up; the emergency-stop alarm clears.
5. Check the beacon is off and the panel shows no alarm.
6. Set belt speed on `-R1`.
7. Confirm the downstream transport is available and signalling ready.
8. Select AUTO.
9. Press Start `-S2`. Run lamp `-H3` lights and the belt runs.
10. Release one load through the sorter and confirm it enters the expected lane and is counted.

For a real machine, this is explanatory sequence guidance, not an approved commissioning procedure. A competent engineer must verify guards, safety functions, site rules, and authorization first.

### 13.2 Normal operation

- The machine sorts automatically. The operator watches lane counts, alarm state, and downstream lanes.
- If a lane backs up, downstream ready drops and the sorter **holds** loads instead of pushing them. The dashboard shows `Interlock_Hold`. This correct process behaviour is not a fault.
- Rejects are counted but do not stop the machine. A rising reject count commonly means a class sensor needs cleaning or realignment.
- Reset counters at the start of each shift so throughput and OEE represent that shift.

### 13.3 Normal shutdown

1. Let the belt run clear of loads.
2. Press Stop `-S3`.
3. For a longer stop, turn `-Q0` to OFF and lock it if anyone will work on the machine.

On real equipment, use the applicable isolation/lockout procedure; this document does not authorize anyone to enter a guarded area or work on energized electrical systems.

### 13.4 Emergency stop and recovery

1. Press `-S1`. All motion stops immediately and diverters lose power.
2. Make the machine safe and address the cause.
3. Clear a partly diverted load by hand only with the isolator locked off if reaching inside is necessary.
4. Release `-S1`.
5. Press `-S4` reset. **The machine does not restart on its own**—this is deliberate.
6. Press Start to resume.

This sequence states intended design behaviour. Emergency intervention and recovery on a real system must be carried out by trained, authorized people under the required safety and lockout rules.

### 13.5 Alarm response

| Alarm | Code | What to check | Action |
|:--|:--|:--|:--|
| Emergency stop | 1 | Is `-S1` pressed? Is a wire broken or terminal loose? Has the safety relay dropped? | Follow 13.4. If no button is pressed and the alarm persists, the safety loop has an electrical fault—do not bypass it; call maintenance |
| Conveyor jam | 2 | Load stuck at the divert junction. Is junction photo-eye `-B5` dirty or misaligned? | Isolate, clear the blockage, clean the sensor lens. The alarm clears itself |
| Sensor fault | 3 | Two class sensors on together. Usually a dirty lens, misaligned reflector, or load out of shape | Clean and realign class sensors `-B2` to `-B4`. Check load presentation upstream |
| Inverter fault | 4 | Read the drive display for its fault code. Common causes: overload, overcurrent, overtemperature, motor cable fault | Clear the cause, reset the drive. Recurring trips suggest a mechanical problem or wrongly sized ramp—do not repeatedly reset |
| Not an alarm: interlock hold | — | Downstream transport is not ready | Check the AGV / RGV / AS-RS. The sorter resumes when ready returns |
| Not an alarm: rising rejects | — | Loads enter but are not classified | Clean class sensors; check load spacing and orientation upstream |

Never bypass safety devices or electrical protection. In a real installation, only qualified personnel should isolate, diagnose, repair, reset, or verify electrical/safety functions.

### 13.6 Maintenance schedule

| Interval | Task |
|:--|:--|
| Daily | Wipe sensor lenses and reflectors. Check beacon and horn work. Confirm reject count is normal for the shift |
| Weekly | Function-test emergency stop and confirm no restart without reset. Check diverters move freely and fully. Check air pressure and drain filter bowl |
| Monthly | Check terminal tightness at `-X1`, especially safety terminals 24 to 29. Check belt tension and tracking. Look for heat damage or discolouration in the panel |
| Annually | Confirm motor protection setting against motor nameplate. Verify drive parameters against commissioning record. Review safety function against current drawings |
| After any change | Re-run acceptance tests in section 12 that cover the change, and update drawing revision |

Real maintenance intervals, torque checks, safety-function proof tests, and authorization requirements must be set and verified by qualified personnel for the actual machine.

### 13.7 Operation support and troubleshooting

| Symptom | Likely cause | Fix |
|:--|:--|:--|
| Belt will not start | Safety monitor low, or an alarm is active | `I0.2` must read 1 and no alarm may be active. Check reset has been pressed |
| Belt runs but nothing is sorted | Class sensors not triggering, or downstream interlock is holding | Check `I0.4` to `I0.6` react to a load; check `Interlock_Hold` and downstream-ready signal |
| A diverter never fires | Diverting is inhibited while belt is off, the interlock is holding, or solenoid / relay failed | Start belt first. Check `Interlock_Hold`. Check relay coil and `-K9` |
| Diverters dead, everything else fine | `-K9` has dropped, so solenoid power is off | Check safety circuit and reset. `-K9` follows safety relay |
| Counts do not increase | Counting uses rising edge of diverter output, so no pulse means no count | Confirm diverter outputs pulse |
| Dashboard shows zeros or nonsense | DB1 is still set to optimized access | Turn off “Optimized block access” on DB1, recompile, download again. This is the most common mistake |
| Gateway cannot connect | PLCSIM not in RUN, or wrong address | Use `127.0.0.1`, rack 0, slot 1, CPU in RUN |
| Dashboard will not connect | Session id does not match gateway, or broker unreachable | Match session id and check browser can reach broker on WebSocket port |
| Uptime and OEE never move | Clock memory byte not enabled on CPU | Enable clock memory MB10 in CPU properties, recompile, download |

These troubleshooting notes are for the simulation/design context. Actual electrical fault finding must not be attempted by unqualified people and must follow approved safety controls.

## 14. Limitations and future work

These limits are stated openly because a design document should identify its gaps.

- **Simulation only.** No physical panel has been built and no commissioning has been done. The program is real and runs, but field devices are simulated by forcing inputs.
- **Safety not formally verified.** Architecture is designed to Category 3 intent under ISO 13849-1. Quantified performance level has not been calculated, and competent safety-engineer review is required before any build.
- **Servo is design-level only.** Inverter control is implemented and tested. The servo transfer unit is specified and drawn but not programmed.
- **KPI formulas are simplified.** A production OEE calculation separates planned from unplanned downtime, handles shift patterns and product-specific ideal rates, and takes ideal rate from a recipe rather than a constant.
- **Counters are 16-bit and volatile.** They roll over at 32767 and reset on a power cycle. A production machine would use 32-bit counters with retentive memory.
- **No history.** Only live data is available. There is no database and no trend beyond the dashboard’s last 30 samples.
- **Communication is not secure.** The demonstration uses a public MQTT broker with no authentication or encryption. A plant installation needs a private broker with TLS and accounts, on the plant network behind a firewall.
- **Single-signal handshake.** The interlock uses one “ready to receive” signal. A full installation adds load-ready, transfer-complete, and timeout with an alarm.

Reasonable next steps, in order: replace the raw S7 link with OPC UA; add a database for history and shift reporting; extend the handshake to the full four-signal sequence with timeout; program the servo transfer unit; route by barcode rather than size. All future real-world changes must be designed, risk assessed, verified, and approved by qualified engineers.

## 15. Glossary

Plain-English definitions of terms used in this document set.

| Term | Meaning |
|:--|:--|
| **AGV** | Automated Guided Vehicle. A driverless vehicle that follows a floor route to move loads |
| **AS/RS** | Automated Storage and Retrieval System: racking, a crane, and the control system that decides each load location |
| **Actuator** | Anything converting a signal into movement: motor, cylinder, solenoid valve |
| **Analogue signal** | A value across a range, such as 0 to 10 volts, instead of only on/off |
| **CE marking** | Manufacturer’s declaration that a product meets applicable European directives and standards |
| **CPS** | Cyber-Physical System: physical machine plus software model kept in step |
| **Contactor** | Heavy-duty electrically operated switch designed to switch motor power |
| **DB / Data block** | PLC memory holding data rather than logic; a global DB can be shared by blocks, HMI, and gateway |
| **Determinism** | Producing the same result in the same time under the same conditions; why PLCs are used instead of ordinary PCs |
| **Digital signal** | Signal that is only on or off |
| **Digital twin** | Screen model of a machine that follows it live |
| **Diverter** | Device pushing a load off a conveyor into a lane; here an air cylinder driven by solenoid valve |
| **E-Stop** | Emergency stop: latching red mushroom button intended to remove power to motion immediately |
| **EPLAN Electric P8** | Electrical-schematic CAD software that generates drawings and reports described in `electrical_design.md` |
| **FB / Function block** | Reusable PLC block with its own memory, allowing timers and counts to persist between scans |
| **FC / Function** | Reusable PLC block with no memory; calculates from inputs then forgets |
| **Fail-safe** | Designed so failure produces the safe result; an NC emergency stop is fail-safe because a broken wire also stops |
| **HMI** | Human-Machine Interface: operator screen on a machine |
| **IEC 60204-1** | International standard for electrical equipment of machines |
| **IEC 61131-3** | International standard defining PLC languages, including Ladder and Structured Text |
| **IEC 81346** | International standard for device reference designations such as `-B1`, `-K1`, `-Q1` |
| **Interlock** | Condition that must be satisfied before an action is allowed |
| **Interposing relay** | Small relay between PLC output and real load so the PLC does not carry load current |
| **ISO 13849-1** | International standard for safety-related machine-control parts; defines categories and performance levels |
| **Inverter / VFD** | Variable Frequency Drive: controls AC motor speed by changing supplied-power frequency |
| **Ladder / LAD** | Graphical PLC language made to resemble relay wiring |
| **Latching** | Making a momentary button press persist by using an output’s contact to hold the circuit; also seal-in |
| **MCB** | Miniature Circuit Breaker: trips on overload or short circuit to protect cable |
| **MQTT** | Lightweight publish/subscribe messaging protocol widely used in industrial IoT |
| **Material handling** | Moving, storing, and controlling goods in a factory or warehouse |
| **OB / Organisation block** | PLC block called directly by CPU; OB1 runs every scan |
| **OEE** | Overall Equipment Effectiveness: Availability × Performance × Quality as one percentage |
| **OPC UA** | Vendor-neutral industrial communication standard carrying data meaning as well as value |
| **PE** | Protective Earth: conductor making a fault operate protection rather than leave frame live |
| **PLC** | Programmable Logic Controller: industrial computer designed to control machines predictably |
| **PNP sensor** | Sensor switching the positive side and sending 24 V to PLC input; NPN switches negative side and is more common in Japanese equipment |
| **Photo-electric sensor** | Sensor using a light beam and switching when an object breaks or reflects it |
| **Proximity sensor** | Sensor detecting a nearby object without contact |
| **RGV** | Rail Guided Vehicle: AGV-like vehicle on a fixed rail, usually faster and more accurate |
| **Rising edge** | Instant a signal changes off-to-on, used so one event gives one count |
| **SCADA** | Supervisory Control and Data Acquisition: system supervising many machines, history, and trends |
| **SCL / Structured Text** | Text-based PLC language like Pascal, suited to mathematics, loops, and data handling |
| **STO** | Safe Torque Off: drive input that removes the internal motor torque-producing power path |
| **Safety relay** | Safety-rated relay designed to monitor itself and require deliberate reset for safety functions |
| **Scan cycle** | PLC’s repeating loop: read inputs, run program, write outputs, housekeeping |
| **Sensor** | Device detecting something physical and giving PLC a signal |
| **Servo** | Motor with position feedback and controller, used where exact stopping position is required |
| **Solenoid valve** | Electrically operated valve; energizing it directs compressed air to move a cylinder |
| **Sortation** | Separating a mixed flow of goods into destination-sorted flows |
| **Stacker crane** | Tall warehouse-aisle machine placing loads into racking and removing them |
| **Stop category** | How a machine stops: 0 immediate power removal; 1 ramp down then remove power; 2 controlled stop with power on |
| **Terminal strip** | Numbered panel terminals where wiring is terminated |
| **Throughput** | Number of loads handled per unit time |
| **TON** | On-delay timer whose output switches on after input stays on for preset time |
| **TP** | Pulse timer giving a fixed output pulse regardless of how briefly the input was on |
| **Tag** | PLC-address name shared by program, drawing, and schedules |
| **UL 508A** | North American standard for building industrial control panels |
| **Watch table** | TIA Portal window for monitoring and forcing PLC values; used here to simulate field devices |

## 16. Document control

| Rev | Date | Change | By |
|:--|:--|:--|:--|
| 0 | 2026-08-30 | First issue | PSM |
| 1 | 2026-09-19 | Reframed as material-handling sortation equipment. Added the downstream equipment interlock, inverter run and fault handling, alarm code 4, new DB1 bits at 27.1, 27.2, 27.3 and 30.5, digital-twin framing, lifecycle note, operation and maintenance section, glossary | PSM |

> This retained document-control record describes the source design revision. This rewritten file is an educational aid, not a revised, approved, or certified engineering document.
