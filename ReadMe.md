# CosTheta — Automated Hub Assembly Inspection System

> A real-time, computer-vision-driven quality control platform for automotive steering knuckle and hub assembly lines, developed by **CosTheta Technologies**.

---

## Table of Contents

- [Overview](#overview)
- [Key Capabilities](#key-capabilities)
- [System Architecture](#system-architecture)
- [Process Architecture — Six Parallel Processes](#process-architecture--six-parallel-processes)
- [Inter-Process Communication — Redis Message Bus](#inter-process-communication--redis-message-bus)
- [Inspection Pipeline & State Machine](#inspection-pipeline--state-machine)
- [Camera Vision Pipeline](#camera-vision-pipeline)
- [AI Model Architecture](#ai-model-architecture)
- [PLC Integration & Tag Protocol](#plc-integration--tag-protocol)
- [Database Schema](#database-schema)
- [Heartbeat & Fault Monitoring](#heartbeat--fault-monitoring)
- [Configuration System](#configuration-system)
- [Logging Architecture](#logging-architecture)
- [Technology Stack](#technology-stack)
- [Deployment](#deployment)
- [Directory Structure](#directory-structure)

---

## Overview

The CosTheta Inspection System automates quality control at each station of a hub-assembly line. A **QR code** on every incoming component uniquely identifies the part (model, LHS/RHS, tonnage); the system then orchestrates a sequence of **camera-based visual inspections**, **PLC-interlocked torque checks**, and **press operations** before generating a pass/fail result that is written back to the PLC and persisted in PostgreSQL.

The platform runs as **six independent OS processes** connected through a **Redis message bus**, with a **PyQt6 GUI frontend** giving operators real-time status, image previews, and audit trails.

---

## Key Capabilities

| Capability | Detail |
|---|---|
| Visual inspection | Knuckle, Hub & Bottom Bearing, Top Bearing, Nut & Plate Washer, Split Pin & Washer, Cap, Bunk presence/absence |
| Component identification | QR code scanning via RS-232 serial scanner |
| PLC interlocking | EtherNet/IP (Allen-Bradley ControlLogix via `pycomm3`) — bidirectional tag read/write |
| AI models | MobileSAMv2 (segmentation) + YOLO (detection), shared singleton across inspection modules to minimise GPU footprint |
| Database | PostgreSQL — inspection records, torque values, machine settings, audit log |
| Alarm system | Audio alarms + configurable alarm thresholds; per-server heartbeat monitoring |
| Deployment | Nuitka-compiled standalone Windows executable; also runs natively on Linux |
| Modes | `PRODUCTION`, `TRIAL` (saves all images), `TEST` (mock PLC) |

---

## System Architecture

```mermaid
graph TB
    subgraph HARDWARE["Hardware Layer"]
        CAM["RTSP IP Camera<br/>(Hikvision)"]
        PLC["Allen-Bradley PLC<br/>(EtherNet/IP)"]
        ADAM["ADAM Module<br/>(I/O)"]
        QR["QR Code Scanner<br/>(RS-232 Serial)"]
    end

    subgraph PROCESSES["Application Processes (Python multiprocessing)"]
        MAIN["MainProgram<br/>(Orchestrator)"]
        CAM_PROC["CameraServer<br/>Process P2"]
        QR_PROC["QRCodeServer<br/>Process P3"]
        IO_PROC["IOServer<br/>Process P4"]
        DB_PROC["DBServer<br/>Process P5"]
        FE_PROC["FrontendServer<br/>Process P6"]
        LOG_PROC["LoggingServer<br/>Process P1"]
        HB_PROC["HeartbeatServer<br/>Process P7"]
    end

    subgraph INFRA["Infrastructure"]
        REDIS["Redis<br/>Message Bus"]
        PG["PostgreSQL<br/>Database"]
        FS["File System<br/>(Image Archive)"]
    end

    CAM -- "RTSP stream" --> CAM_PROC
    QR -- "Serial / USB" --> QR_PROC
    PLC -- "EtherNet/IP tags" --> IO_PROC
    ADAM --> IO_PROC

    MAIN --> LOG_PROC
    MAIN --> CAM_PROC
    MAIN --> QR_PROC
    MAIN --> IO_PROC
    MAIN --> DB_PROC
    MAIN --> FE_PROC
    MAIN --> HB_PROC

    CAM_PROC <--> REDIS
    QR_PROC <--> REDIS
    IO_PROC <--> REDIS
    DB_PROC <--> REDIS
    FE_PROC <--> REDIS
    HB_PROC <--> REDIS
    LOG_PROC <--> REDIS

    IO_PROC --> PG
    DB_PROC --> PG
    CAM_PROC --> FS
```

---

## Process Architecture — Six Parallel Processes

```mermaid
graph LR
    subgraph P1["P1 · LoggingServer"]
        L1["SlaveConsoleLogger"]
        L2["SlaveFileLogger"]
        L3["SlaveFrontendLogger"]
    end

    subgraph P2["P2 · CameraServer"]
        C1["MonitorGetPicQueue<br/>(Thread)"]
        C2["CameraProcessorServer<br/>(Thread)"]
        C3["CheckKnuckle"]
        C4["CheckTopBearing"]
        C5["CheckHubAndBottomBearing"]
        C6["CheckNutAndPlateWasher"]
        C7["CheckBunk / CheckNoBunk"]
        C8["CheckCap / CheckSplitPin"]
    end

    subgraph P3["P3 · QRCodeServer"]
        Q1["MonitorGetQRCodeQueue<br/>(Thread)"]
        Q2["QRCodeProcessor<br/>(Thread)"]
    end

    subgraph P4["P4 · IOServer"]
        I1["ReadLoop Thread"]
        I2["WriteTagsLoop Thread"]
        I3["HeartbeatThread"]
        I4["EmergencyMonitorThread"]
        I5["UpdateTagsToDefaultProcessor"]
    end

    subgraph P5["P5 · DBServer"]
        D1["InspectionRecord Writer"]
        D2["PostgresBackupUtility"]
    end

    subgraph P6["P6 · FrontendServer"]
        F1["AshokLeylandFrontEnd<br/>(PyQt6 GUI)"]
        F2["ImageProcessingGUI"]
        F3["SimplePopups"]
    end

    P2 -- "inspection result" --> P4
    P3 -- "QR code" --> P4
    P4 -- "trigger" --> P2
    P4 -- "record" --> P5
    P4 -- "status" --> P6
    P1 -- "log stream" --> P6
```

---

## Inter-Process Communication — Redis Message Bus

All processes communicate exclusively through named Redis queues (lists). No process calls another process's functions directly.

```mermaid
sequenceDiagram
    participant PLC
    participant IOServer
    participant Redis
    participant CameraServer
    participant QRCodeServer
    participant DBServer
    participant Frontend

    PLC->>IOServer: Tag: PLC_PC_CheckQRCode = TRUE
    IOServer->>Redis: io2qrcodeq → {takePicture: true, state: READ_QR_CODE}
    Redis->>QRCodeServer: dequeue
    QRCodeServer->>Redis: qrcode2ioq → {qrCode: "XYZ-LHS-001"}
    Redis->>IOServer: dequeue
    IOServer->>PLC: Write rotation settings (CW/CCW, RPM)
    IOServer->>PLC: PC_PLC_QRCodeCheckOK = TRUE
    IOServer->>PLC: PC_PLC_QRCodeCheckDone = TRUE

    PLC->>IOServer: Tag: PLC_PC_CheckKnuckle = TRUE
    IOServer->>Redis: io2cameraq → {takePicture: true, state: READ_TAKE_PICTURE_FOR_CHECKING_KNUCKLE}
    Redis->>CameraServer: dequeue
    CameraServer->>CameraServer: Capture frame → run CheckKnuckle
    CameraServer->>Redis: camera2ioq → {result: PASS, state: WRITE_RESULT_OF_CHECKING_KNUCKLE}
    Redis->>IOServer: dequeue
    IOServer->>PLC: PC_PLC_KnuckleCheckOK = TRUE/FALSE
    IOServer->>PLC: PC_PLC_KnuckleCheckDone = TRUE
    IOServer->>Redis: io2dbq → {qrCode, result, image_path, timestamp}
    Redis->>DBServer: dequeue → persist to PostgreSQL
    IOServer->>Redis: io2frontendq → status update
    Redis->>Frontend: refresh UI
```

### Named Redis Queues

| Queue | Direction | Payload |
|---|---|---|
| `io2cameraq` | IOServer → CameraServer | `{takePicture, currentMachineState, timestamp}` |
| `camera2ioq` | CameraServer → IOServer | `{result, state, imagePath, timestamp}` |
| `io2qrcodeq` | IOServer → QRCodeServer | `{takePicture, state}` |
| `qrcode2ioq` | QRCodeServer → IOServer | `{qrCode}` |
| `io2dbq` | IOServer → DBServer | Inspection record payload |
| `io2frontendq` | IOServer → Frontend | Status / result for display |
| `logq` | All → LoggingServer | Log messages |
| `heartbeatq` | All → HeartbeatServer | Liveness pings |
| `stopq` | MainProgram → All | Graceful shutdown signal |

---

## Inspection Pipeline & State Machine

The assembly process is modelled as a 29-state `IntEnum` (`MachineState`). States alternate between **READ** states (waiting for PLC trigger) and **WRITE** states (writing result back to PLC).

```mermaid
stateDiagram-v2
    [*] --> READ_QR_CODE

    READ_QR_CODE --> WRITE_QR_CODE : QR code scanned & validated
    WRITE_QR_CODE --> READ_TAKE_PICTURE_FOR_CHECKING_KNUCKLE

    READ_TAKE_PICTURE_FOR_CHECKING_KNUCKLE --> WRITE_RESULT_OF_CHECKING_KNUCKLE : Camera inspection done
    WRITE_RESULT_OF_CHECKING_KNUCKLE --> READ_TAKE_PICTURE_FOR_CHECKING_HUB_AND_BOTTOM_BEARING

    READ_TAKE_PICTURE_FOR_CHECKING_HUB_AND_BOTTOM_BEARING --> WRITE_RESULT_OF_CHECKING_HUB_AND_BOTTOM_BEARING
    WRITE_RESULT_OF_CHECKING_HUB_AND_BOTTOM_BEARING --> READ_TAKE_PICTURE_FOR_CHECKING_TOP_BEARING

    READ_TAKE_PICTURE_FOR_CHECKING_TOP_BEARING --> WRITE_RESULT_OF_CHECKING_TOP_BEARING
    WRITE_RESULT_OF_CHECKING_TOP_BEARING --> READ_TAKE_PICTURE_FOR_CHECKING_NUT_AND_PLATEWASHER

    READ_TAKE_PICTURE_FOR_CHECKING_NUT_AND_PLATEWASHER --> WRITE_RESULT_OF_CHECKING_NUT_AND_PLATEWASHER
    WRITE_RESULT_OF_CHECKING_NUT_AND_PLATEWASHER --> READ_TIGHTENING_TORQUE_1_DONE

    READ_TIGHTENING_TORQUE_1_DONE --> READ_TIGHTENING_TORQUE_1 : Torque station 1 complete
    READ_TIGHTENING_TORQUE_1 --> READ_FREE_ROTATIONS_DONE

    READ_FREE_ROTATIONS_DONE --> READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_COMPONENT_PRESS
    READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_COMPONENT_PRESS --> WRITE_RESULT_OF_CHECKING_BUNK_FOR_COMPONENT_PRESS
    WRITE_RESULT_OF_CHECKING_BUNK_FOR_COMPONENT_PRESS --> READ_COMPONENT_PRESS_DONE

    READ_COMPONENT_PRESS_DONE --> READ_TAKE_PICTURE_FOR_CHECKING_NO_BUNK
    READ_TAKE_PICTURE_FOR_CHECKING_NO_BUNK --> WRITE_RESULT_OF_CHECKING_NO_BUNK

    WRITE_RESULT_OF_CHECKING_NO_BUNK --> READ_TIGHTENING_TORQUE_2_DONE
    READ_TIGHTENING_TORQUE_2_DONE --> READ_TIGHTENING_TORQUE_2
    READ_TIGHTENING_TORQUE_2 --> READ_TAKE_PICTURE_FOR_CHECKING_SPLITPIN_AND_WASHER

    READ_TAKE_PICTURE_FOR_CHECKING_SPLITPIN_AND_WASHER --> WRITE_RESULT_OF_CHECKING_SPLITPIN_AND_WASHER
    WRITE_RESULT_OF_CHECKING_SPLITPIN_AND_WASHER --> READ_TAKE_PICTURE_FOR_CHECKING_CAP

    READ_TAKE_PICTURE_FOR_CHECKING_CAP --> WRITE_RESULT_OF_CHECKING_CAP
    WRITE_RESULT_OF_CHECKING_CAP --> READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_CAP_PRESS

    READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_CAP_PRESS --> WRITE_RESULT_OF_CHECKING_BUNK_FOR_CAP_PRESS
    WRITE_RESULT_OF_CHECKING_BUNK_FOR_CAP_PRESS --> READ_CAP_PRESS_DONE

    READ_CAP_PRESS_DONE --> READ_FREE_ROTATION_TORQUE_1_DONE
    READ_FREE_ROTATION_TORQUE_1_DONE --> READ_FREE_ROTATION_TORQUE_1
    READ_FREE_ROTATION_TORQUE_1 --> READ_QR_CODE : Cycle complete
```

### Cycle Time Tracking

The IOServer tracks wall-clock durations for each operation segment, ignoring operator idle time, and logs cycle time analytics:

| Operation Key | Segment |
|---|---|
| `T1_Knuckle` | PLC trigger → knuckle check result written |
| `T2_HubAndBottomBearing` | PLC trigger → hub/bearing result written |
| `T3_TopBearing` | PLC trigger → top bearing result written |
| `T4_NutAndPlateWasher_to_FreeRotations` | Nut/washer check through free rotations |
| `T5_NoCapBunk` | Bunk check (no-cap) |
| `T6_NoCapBunkStart_to_Torque2Done` | Torque 2 segment |
| `T7_SplitPinAndWasher` | Split pin & washer check |
| `T8_Cap` | Cap check |
| `T9_BunkCapPress_to_Station3TorqueValueSet` | Cap press through final torque |

---

## Camera Vision Pipeline

```mermaid
flowchart TD
    A["RTSP Frame Grabbed\n(RTSPCam)"] --> B["MonitorGetPicQueue\nreceives trigger"]
    B --> C["CameraProcessorServer\nroutes to correct checker"]

    C --> D1["CheckKnuckle\n(polygon + brightness analysis)"]
    C --> D2["CheckTopBearing\n(RANSAC circle fit + arc coverage)"]
    C --> D3["CheckHubAndBottomBearing\n(MobileSAMv2 + YOLO segmentation)"]
    C --> D4["CheckNutAndPlateWasher\n(HexagonNutDetector)"]
    C --> D5["CheckBunk / CheckNoBunk\n(BunkSegmenter)"]
    C --> D6["CheckCap\n(gradient + delta threshold)"]
    C --> D7["CheckSplitPinAndWasher\n(pixel analysis)"]

    D1 & D2 & D3 & D4 & D5 & D6 & D7 --> E["Result: PASS / FAIL\n+ annotated image"]

    E --> F["Image saved to\narchive (OK / NOT_OK folder)"]
    E --> G["Result pushed to\ncamera2ioq (Redis)"]
```

### Per-Component Inspection Techniques

| Component | Primary Technique |
|---|---|
| **Knuckle** | Polygon-region brightness & contrast analysis |
| **Top Bearing** | RANSAC circle fitting, arc coverage scoring, gamma normalisation |
| **Hub & Bottom Bearing** | MobileSAMv2 automatic mask generation + YOLO object detection |
| **Nut & Plate Washer** | HexagonNutDetector — geometric contour + orientation analysis |
| **Bunk (presence)** | BunkSegmenter — SAM-based segmentation |
| **No Bunk (absence)** | Negative-space verification |
| **Cap** | Gradient-based delta threshold per model variant |
| **Split Pin & Washer** | Pixel-level presence check in ROI |

### Image Normalisation

Before inference, frames pass through `ImageNormalisationWithMask`, which applies:

- Gamma correction via precomputed LUT
- Per-channel normalisation within a configurable mask region
- Crop to annotated region of interest

---

## AI Model Architecture

```mermaid
graph TD
    subgraph MM["ModelManager (Singleton)"]
        SAM["MobileSAMv2\nSAM Predictor"]
        YOLO["YOLO Model\n(ultralytics)"]
        DEV["Device: CUDA / CPU"]
    end

    MM --> B["BunkSegmenter\n(CheckBunk)"]
    MM --> H["HubAndBearingSegmenter\n(CheckHubAndBottomBearing)"]
    MM --> N["HexagonNutDetector\n(CheckNutAndPlateWasher)"]

    B --> MG1["MobileSAMv2\nAutoMaskGenerator"]
    H --> MG2["MobileSAMv2\nAutoMaskGenerator"]
    N --> MG3["YOLO Inference"]
```

`ModelManager` is a thread-safe singleton that loads MobileSAMv2 and YOLO **once** and shares the same model objects across all inspection modules. This reduces GPU memory consumption from ~9–12 GB (three independent model sets) to **~3–4 GB**.

---

## PLC Integration & Tag Protocol

Communication with the Allen-Bradley PLC uses **EtherNet/IP** via the `pycomm3` `LogixDriver`. The IOServer maintains two driver instances: one dedicated to reads, one to writes.

```mermaid
sequenceDiagram
    participant PLC
    participant IOServer
    Note over IOServer: ReadLoop thread polls at configured interval

    PLC->>IOServer: PLC_PC_Check{Component} = TRUE (bool tag)
    IOServer->>IOServer: Identify current MachineState
    IOServer->>Redis: io2cameraq or io2qrcodeq
    Note over IOServer: Await result from CameraServer / QRCodeServer

    IOServer->>PLC: PC_PLC_{Component}CheckOK = TRUE/FALSE
    Note over IOServer: Sleep PLC_SLEEPTIME_BETWEEN_OK_AND_DONE
    IOServer->>PLC: PC_PLC_{Component}CheckDone = TRUE
    IOServer->>PLC: Reset PLC_PC_Check{Component} = FALSE
```

### PLC Tag Map (representative subset)

| Direction | Tag | Type | Purpose |
|---|---|---|---|
| PLC → PC | `PLC_PC_CheckQRCode` | bool | Request QR scan |
| PLC → PC | `PLC_PC_CheckKnuckle` | bool | Request knuckle inspection |
| PLC → PC | `PLC_PC_CheckHub` | bool | Request hub inspection |
| PLC → PC | `PLC_PC_CheckTopBearing` | bool | Request top bearing inspection |
| PLC → PC | `PLC_PC_CheckNutAndPlateWasher` | bool | Request nut/washer inspection |
| PLC → PC | `PLC_PC_TighteningTorque1Done` | bool | Torque station 1 complete |
| PC → PLC | `PC_PLC_QRCodeCheckOK` | bool | QR code result |
| PC → PLC | `PC_PLC_KnuckleCheckOK` | bool | Knuckle result |
| PC → PLC | `PC_PLC_HubCheckOK` | bool | Hub result |
| PC → PLC | `PC_PLC_NoOfRotation1CW` | int | Rotation count (LHS) |
| PC → PLC | `PC_PLC_NoOfRotation1CCW` | int | Rotation count (RHS) |
| PC → PLC | `PC_PLC_LH_RH_Selection` | int | 1 = LHS, 2 = RHS |
| PC → PLC | `PC_PLC_RotationUnitRPM` | int | Rotation speed |

---

## Database Schema

The system uses **PostgreSQL** (local, port 5432). The IOServer maintains a `ThreadedConnectionPool` (min 1, max 3 connections).

```mermaid
erDiagram
    INSPECTION_RECORDS {
        serial      id              PK
        text        qr_code
        text        model_name
        text        lhs_rhs
        float       tonnage
        boolean     knuckle_ok
        boolean     hub_ok
        boolean     top_bearing_ok
        boolean     nut_washer_ok
        boolean     split_pin_ok
        boolean     cap_ok
        boolean     bunk_ok
        boolean     overall_result
        text        knuckle_image_path
        text        hub_image_path
        text        top_bearing_image_path
        text        nut_washer_image_path
        text        cap_image_path
        float       torque_1_value
        float       torque_2_value
        float       free_rotation_torque
        timestamp   created_at
        text        username
        text        mode
    }

    MACHINE_SETTINGS {
        serial      id              PK
        int         NoOfRotation1CW
        int         NoOfRotation1CCW
        int         NoOfRotation2CW
        int         NoOfRotation2CCW
        int         RotationUnitRPM
        timestamp   updated_at
    }

    USERS {
        serial      id              PK
        text        username        UK
        text        password_hash
        text        role
        timestamp   created_at
    }

    AUDIT_LOG {
        serial      id              PK
        text        username
        text        action
        text        detail
        timestamp   logged_at
    }

    INSPECTION_RECORDS }o--|| MACHINE_SETTINGS : "uses settings at time of inspection"
    INSPECTION_RECORDS }o--|| USERS : "recorded by"
    AUDIT_LOG }o--|| USERS : "performed by"
```

---

## Heartbeat & Fault Monitoring

`HeartbeatAndAlarmServer` runs as a dedicated thread that monitors all five peer servers. Each server publishes a liveness signal to Redis at a configurable interval. If a server misses a threshold number of consecutive heartbeats, the alarm system fires.

```mermaid
flowchart LR
    subgraph Peers
        CS["CameraServer"]
        QR["QRCodeServer"]
        IO["IOServer"]
        DB["DBServer"]
        FE["FrontendServer"]
    end

    subgraph HB["HeartbeatAndAlarmServer"]
        POLL["Poll Redis\nheartbeat queues"]
        COUNT["Increment consecutive\ndown counter"]
        THRESH{"> N consecutive\ndowns?"}
        ALARM["Trigger audio alarm\n(Siren.wav)"]
        RESET["Reset counter\n(System ready.wav)"]
        BAD["Bad component alarm\n(BadComponent.wav)"]
    end

    Peers -- "heartbeat ping" --> POLL
    POLL -- "ALIVE" --> RESET
    POLL -- "DEAD / timeout" --> COUNT
    COUNT --> THRESH
    THRESH -- "Yes" --> ALARM
    THRESH -- "No" --> POLL
    IO -- "bad component flag" --> BAD
```

Connection status is relayed to the frontend in real time, allowing operators to see at a glance which servers are up.

---

## Configuration System

All runtime parameters are externalised to `ApplicationConfiguration.properties`. The `CosThetaConfigurator` class is a **thread-safe double-checked locking singleton** that hot-reloads the properties file every 5 seconds if a change is detected — no restart required.

```mermaid
flowchart TD
    A["ApplicationConfiguration.properties"] --> B["CosThetaConfigurator.getInstance()"]
    B --> C{"File changed\nsince last load?"}
    C -- "Yes" --> D["Reload Properties\n(_loadConfig)"]
    C -- "No" --> E["Return cached values"]
    D --> E

    E --> F1["CameraServer\n(IP, port, credentials, FPS)"]
    E --> F2["IOServer\n(PLC IP, tag names, sleep times)"]
    E --> F3["HeartbeatServer\n(intervals, alarm thresholds)"]
    E --> F4["DBServer\n(DB name, folders)"]
    E --> F5["FrontendServer\n(fonts, window title, UI params)"]
    E --> F6["CheckTopBearing / etc.\n(model-specific thresholds)"]
```

Key configuration categories:

| Category | Example Keys |
|---|---|
| Camera | `camera.ip`, `camera.port`, `camera.uid`, `camera.fps` |
| PLC | `plc.ip`, `plc.pc.check.knuckle.tagname`, `pc.plc.knuckle.check.ok.tagname` |
| Heartbeat | `heartbeat.minimum.continuous.disconnections.for.alarm`, `heartbeat.gap.between.alarms` |
| Image paths | `images.base.folder`, `images.knuckle.folder`, `images.ok.folder` |
| Logging | `logging.directory`, `logging.file.level`, `logging.console.level` |
| UI | `application.name`, `font.face`, `initial.fontsize` |

---

## Logging Architecture

```mermaid
graph LR
    subgraph Any["Any Process"]
        LB["logBoth(level, source, msg, type)"]
    end

    LB --> RC["Redis logq"]

    subgraph LogProc["LoggingServer Process (P1)"]
        SConsole["SlaveConsoleLogger\n(stdout with colours)"]
        SFile["SlaveFileLogger\n(rotating file handler)"]
        SFrontend["SlaveFrontendLogger\n(pushes to UI)"]
    end

    RC --> SConsole
    RC --> SFile
    RC --> SFrontend
```

All processes call the single `logBoth()` helper, which pushes a message onto the Redis log queue. The dedicated `LoggingServer` process drains this queue and fans messages out to three sinks: colour-coded console, rotating file, and the frontend log panel.

Log levels follow Python's standard hierarchy (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) with a custom `MessageType` enum (`SUCCESS`, `ISSUE`, `PROBLEM`, `RISK`, `GENERAL`) that drives colour coding.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| GUI | PyQt6 / PySide6 |
| Computer vision | OpenCV, NumPy |
| AI / Segmentation | MobileSAMv2, YOLO (ultralytics), PyTorch |
| PLC communication | pycomm3 (EtherNet/IP) |
| Message bus | Redis |
| Database | PostgreSQL + psycopg2 |
| QR scanning | pyserial (RS-232) |
| Configuration | pyjavaproperties |
| Compilation | Nuitka (standalone Windows exe) |
| Concurrency | Python `multiprocessing` (processes) + `threading` (intra-process threads) |

---

## Deployment

### Requirements

- Python 3.10 or 3.11
- Redis server (local or network)
- PostgreSQL 14+
- CUDA-capable GPU (recommended for SAM inference)
- Camera accessible via RTSP
- Allen-Bradley PLC on same LAN

### Running from source

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure the application
cp ApplicationConfiguration.properties.template ApplicationConfiguration.properties
# Edit the file with your camera IP, PLC IP, DB name, etc.

# 3. Start Redis
redis-server

# 4. Create the PostgreSQL database
createdb <your_db_name>

# 5. Launch
python MainProgram.py
```

### Building a standalone Windows executable

```bat
runNuitka.bat
```

The compiled binary and all dependencies are placed in `MainProgram.dist/`. Copy the `wavs/` and `internalimages/` directories alongside it before distributing.

### Modes

| Mode | Behaviour |
|---|---|
| `PRODUCTION` | Normal operation; only failed-inspection images are saved |
| `TRIAL` | All images saved regardless of result; useful for model tuning |
| `TEST` | Uses a mock PLC driver; camera and Redis required |

---

## Directory Structure

```
.
├── MainProgram.py                  # Entry point — spawns all processes
├── Configuration.py                # Singleton configuration manager
├── StateMachine.py                 # MachineState enum + MachineStateMachine
├── BaseUtils.py                    # Project root resolution, time utils, profiling
├── Constants.py                    # Application-wide string constants
├── ApplicationConfiguration.properties  # Runtime configuration (not committed)
│
├── camera/                         # All camera and vision logic
│   ├── CameraProcessorServer.py
│   ├── RTSPCam.py
│   ├── ModelManager.py             # Singleton GPU model loader
│   ├── CheckKnuckle.py
│   ├── CheckTopBearing.py
│   ├── CheckHubAndBottomBearing.py
│   ├── CheckNutAndPlateWasher.py
│   ├── CheckBunk.py / CheckNoBunk.py
│   ├── CheckCap.py / CheckNoCapBunk.py
│   ├── CheckSplitPinAndWasher.py
│   ├── BunkSegmenter.py
│   ├── HubAndBearingSegmenter.py
│   └── HexagonNutDetector.py
│
├── costhetaio/                     # Hardware I/O
│   ├── IOServer.py                 # PLC (EtherNet/IP) + DB connection pool
│   └── QRCodeScanningServer.py
│
├── persistence/                    # Database access
│   ├── DBServer.py
│   ├── Persistence.py
│   └── PostgresBackupUtility.py
│
├── frontend/                       # PyQt6 GUI
│   ├── AshokLeylandFrontEnd.py
│   ├── ImageProcessingGUI.py
│   └── SimplePopups.py
│
├── logutils/                       # Distributed logging
│   ├── Logger.py
│   ├── CentralLoggers.py
│   ├── AbstractSlaveLogger.py
│   └── SlaveLoggers.py
│
├── monitorAllConnections/          # Heartbeat & alarm
│   └── HeartbeatAndAlarmServer.py
│
├── processors/                     # Thread base classes
│   └── GenericQueueProcessor.py
│
├── utils/                          # Shared utilities
│   ├── RedisUtils.py               # All queue read/write helpers
│   ├── BaseUtils.py
│   ├── CosThetaFileUtils.py
│   ├── CosThetaImageUtils.py
│   ├── CosThetaColors.py
│   ├── IPUtils.py
│   └── QRCodeHelper.py
│
├── wavs/                           # Audio alarm files
│   ├── Siren.wav
│   ├── BadComponent.wav
│   └── System is ready.wav
│
└── runNuitka.bat                   # Windows standalone build script
```

---

*Developed by CosTheta Technologies. For integration support, contact the manufacturer.*