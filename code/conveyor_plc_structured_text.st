// ============================================================
// IIoT Smart Sortation Conveyor  -  material handling system
// Siemens S7-1200 (CPU 1214C DC/DC/DC) - TIA Portal V18
//
// SCL source: DB1 ConveyorData, FB3 ProductionCounter, FB4 AlarmHandler.
// FB1 ConveyorControl and FB2 SortingLogic are Ladder - see guides/.
//
// DB1 must be non-optimized. The Python gateway reads it by byte offset.
// ============================================================


// ============================================================
// DB1  "ConveyorData"   global DB, STANDARD (non-optimized) access
// ------------------------------------------------------------
// Shared memory for the HMI and the gateway. Do not reorder.
// Lane 1 = class 1 (small), lane 2 = class 2 (medium), lane 3 = class 3 (large).
//
//  OFFSET  NAME                   TYPE
//  ------  ---------------------  -----
//    0.0   Total_Count            Int    all sorted loads
//    2.0   Lane1_Count            Int
//    4.0   Lane2_Count            Int
//    6.0   Lane3_Count            Int
//    8.0   Reject_Count           Int    entered but never sorted
//   10.0   OEE                    Real   %
//   14.0   Throughput             Real   loads per minute
//   18.0   Uptime_Seconds         DInt
//   22.0   Speed_Actual           Int    0..100 %
//   24.0   Mode                   Int    0=STOP 1=AUTO 2=MANUAL 3=FAULT
//   26.0   Motor_Running          Bool
//   26.1   Alarm_Active           Bool
//   26.2   Jam_Detected           Bool
//   26.3   System_Running         Bool
//   26.4   Sorting_Small          Bool   diverter 1 active
//   26.5   Sorting_Medium         Bool   diverter 2 active
//   26.6   Sorting_Large          Bool   diverter 3 active
//   26.7   EStop_Active           Bool
//   27.0   Object_Present         Bool
//   27.1   VFD_Fault              Bool   inverter tripped
//   27.2   Interlock_Hold         Bool   load waiting for downstream
//   27.3   Downstream_Ready       Bool   handshake mirror, for display
//   28.0   Active_Alarm_Code      Int    0 none 1 EStop 2 jam 3 sensor 4 VFD
//   30.0   Cmd_Start              Bool   \
//   30.1   Cmd_Stop               Bool    |
//   30.2   Cmd_Reset              Bool    |  written by the gateway
//   30.3   Cmd_Mode_Auto          Bool    |
//   30.4   Cmd_Mode_Manual        Bool    |
//   30.5   Cmd_Downstream_Ready   Bool   /   simulated downstream ready
//
//  SIZE = 32 bytes. Bits 27.4-27.7, 30.6-30.7 and byte 31 are spare.
// ------------------------------------------------------------

DATA_BLOCK "ConveyorData"
{ S7_Optimized_Access := 'FALSE' }   // must stay FALSE for snap7
VERSION : 0.2
   VAR
      Total_Count : Int := 0;
      Lane1_Count : Int := 0;
      Lane2_Count : Int := 0;
      Lane3_Count : Int := 0;
      Reject_Count : Int := 0;
      OEE : Real := 0.0;
      Throughput : Real := 0.0;
      Uptime_Seconds : DInt := 0;
      Speed_Actual : Int := 0;
      Mode : Int := 0;
      Motor_Running : Bool := FALSE;
      Alarm_Active : Bool := FALSE;
      Jam_Detected : Bool := FALSE;
      System_Running : Bool := FALSE;
      Sorting_Small : Bool := FALSE;
      Sorting_Medium : Bool := FALSE;
      Sorting_Large : Bool := FALSE;
      EStop_Active : Bool := FALSE;
      Object_Present : Bool := FALSE;
      VFD_Fault : Bool := FALSE;
      Interlock_Hold : Bool := FALSE;
      Downstream_Ready : Bool := FALSE;
      Active_Alarm_Code : Int := 0;
      Cmd_Start : Bool := FALSE;
      Cmd_Stop : Bool := FALSE;
      Cmd_Reset : Bool := FALSE;
      Cmd_Mode_Auto : Bool := FALSE;
      Cmd_Mode_Manual : Bool := FALSE;
      Cmd_Downstream_Ready : Bool := FALSE;
   END_VAR
BEGIN
END_DATA_BLOCK


// ============================================================
// FB3  "ProductionCounter"   (SCL)
// Counts per lane, rejects, and the live KPIs. Call every scan.
// ============================================================

FUNCTION_BLOCK "ProductionCounter"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.2

   VAR_INPUT
      Enable : Bool;                 // normally TRUE
      Reset : Bool;                  // zero the counters
      Divert1 : Bool;                // Q0.1
      Divert2 : Bool;                // Q0.2
      Divert3 : Bool;                // Q0.3
      Entry_Sensor : Bool;           // I0.3
      Motor_On : Bool;               // Q0.0
      Speed_Raw : Int;               // IW64, 0..27648
      OneSec_Clock : Bool;           // M10.5
      Auto_Mode : Bool;              // M0.0
      Manual_Mode : Bool;            // M0.1
      Alarm : Bool;                  // from FB4
   END_VAR

   VAR
      Small_Edge : R_TRIG;
      Medium_Edge : R_TRIG;
      Large_Edge : R_TRIG;
      SecEdge : R_TRIG;
      RejectTimer : TON_TIME;
      RejectEdge : R_TRIG;
      RunSeconds : DInt := 0;
      PlannedSeconds : DInt := 0;
      AnyDivert : Bool;
      Availability : Real;
      Performance : Real;
      Quality : Real;
   END_VAR

BEGIN

   IF #Reset THEN
      "ConveyorData".Total_Count := 0;
      "ConveyorData".Lane1_Count := 0;
      "ConveyorData".Lane2_Count := 0;
      "ConveyorData".Lane3_Count := 0;
      "ConveyorData".Reject_Count := 0;
      #RunSeconds := 0;
      #PlannedSeconds := 0;
   END_IF;

   // One count per load: the diverter pulse lasts 2 s, so count its rising edge.
   #Small_Edge(CLK := #Divert1);
   #Medium_Edge(CLK := #Divert2);
   #Large_Edge(CLK := #Divert3);

   IF #Small_Edge.Q AND NOT #Reset THEN
      "ConveyorData".Lane1_Count := "ConveyorData".Lane1_Count + 1;
   END_IF;
   IF #Medium_Edge.Q AND NOT #Reset THEN
      "ConveyorData".Lane2_Count := "ConveyorData".Lane2_Count + 1;
   END_IF;
   IF #Large_Edge.Q AND NOT #Reset THEN
      "ConveyorData".Lane3_Count := "ConveyorData".Lane3_Count + 1;
   END_IF;

   "ConveyorData".Total_Count := "ConveyorData".Lane1_Count
                               + "ConveyorData".Lane2_Count
                               + "ConveyorData".Lane3_Count;

   // Load entered but nothing diverted within 3 s -> reject.
   #AnyDivert := #Divert1 OR #Divert2 OR #Divert3;
   #RejectTimer(IN := #Entry_Sensor AND NOT #AnyDivert, PT := T#3S);
   #RejectEdge(CLK := #RejectTimer.Q);
   IF #RejectEdge.Q AND NOT #Reset THEN
      "ConveyorData".Reject_Count := "ConveyorData".Reject_Count + 1;
   END_IF;

   // Status mirrors. Object_Present, Interlock_Hold and Downstream_Ready
   // are written by FB2.
   "ConveyorData".Sorting_Small := #Divert1;
