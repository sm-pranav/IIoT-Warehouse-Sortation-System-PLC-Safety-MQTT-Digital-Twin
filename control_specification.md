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
