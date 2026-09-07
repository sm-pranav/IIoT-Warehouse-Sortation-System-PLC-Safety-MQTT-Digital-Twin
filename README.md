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

