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

