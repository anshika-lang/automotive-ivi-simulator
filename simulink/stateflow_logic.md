# Simulink & Stateflow Model Design Specification

## 1. Overview
This model specifies the Service Interaction and Audio/HMI Arbitration logic for an In-Vehicle Infotainment (IVI) and Digital Cockpit Controller. It is modeled for implementation in **Simulink / Stateflow** (compatible with AUTOSAR Adaptive / Classic code generation via Embedded Coder).

---

## 2. Model Interface (Signal Dictionary)

### Inputs
| Port Name | Data Type | Dimensions | Range / Enum | Description |
| :--- | :--- | :--- | :--- | :--- |
| `u_MediaCmd` | `uint8` | 1 | 0: None, 1: Play, 2: Pause | User media controls via HMI / Steering Wheel Control |
| `u_NavActive` | `boolean` | 1 | 0: False, 1: True | Route guidance status |
| `u_NavVoicePrompt` | `boolean` | 1 | 0: Idle, 1: Prompt Active | Trigger from Turn-by-Turn GPS guidance algorithm |
| `u_IncomingCall` | `boolean` | 1 | 0: False, 1: True | Signal from Cellular Baseband / Telephony Modem |
| `u_CallAction` | `uint8` | 1 | 0: None, 1: Accept, 2: Hangup / Decline | Driver response via Touchscreen or Steering Wheel Button |

### Outputs
| Port Name | Data Type | Dimensions | Range / Enum | Description |
| :--- | :--- | :--- | :--- | :--- |
| `y_MediaState` | `uint8` | 1 | 0: Stopped, 1: Playing, 2: PausedTransient, 3: Ducked | Current playback operational state |
| `y_MediaVolume` | `double` | 1 | 0.0 to 1.0 | Attenuated or nominal media stream gain |
| `y_CallState` | `uint8` | 1 | 0: Idle, 1: Ringing, 2: Connected | Telephony call session state |
| `y_DisplayMode` | `uint8` | 1 | 0: FullMedia, 1: FullNav, 2: NavCallOverlay, 3: SplitNavCall | HMI layout configuration for Center Display |
| `y_NavHUDActive` | `boolean` | 1 | 0: False, 1: True | Heads-up display visual route prompt indicator |

### Internal Local Data
| Variable Name | Data Type | Scope | Description |
| :--- | :--- | :--- | :--- |
| `auto_resume_pending` | `boolean` | Local | Preserves driver intent to resume playback once transient call ends |
| `saved_track_offset` | `uint32` | Local | Playback timestamp in milliseconds |

---

## 3. Stateflow State Machine Architecture

```
+----------------------------------------------------------------------------------------------------+
|                                    [Service_Arbitrator_Chart]                                      |
|                                                                                                    |
|   +-------------------+              [u_MediaCmd == 1]             +---------------------------+   |
|   |       IDLE        | -----------------------------------------> |       MEDIA_PLAYING       |   |
|   |                   | <----------------------------------------- |                           |   |
|   +-------------------+              [u_MediaCmd == 2]             +---------------------------+   |
|            ^                                                               |          ^            |
|            |                                            [u_NavPrompt == 1] |          |            |
|            |                                                               v          | [Prompt==0]|
|            |                                                       +---------------------------+   |
|            |                                                       |        MEDIA_DUCKED       |   |
|            |                                                       |    (Vol = 0.2, Ducked)    |   |
|            |                                                       +---------------------------+   |
|            |                                                               |                       |
|            |                                    [u_IncomingCall == 1]      |                       |
|            |                               +-------------------------------+                       |
|            |                               |                                                       |
|            |                               v                                                       |
|            |                       +-----------------------------------------------+               |
|            |                       |                 CALL_RINGING                  |               |
|            |                       |  entry: y_MediaVol=0; auto_resume=true;       |               |
|            |                       |         y_DisplayMode=NavCallOverlay;         |               |
|            |                       +-----------------------------------------------+               |
|            |                                               |                                       |
|            |                                               | [u_CallAction == 1] (Accept)          |
|            |                                               v                                       |
|            |                       +-----------------------------------------------+               |
|            |                       |                  CALL_ACTIVE                  |               |
|            |                       |  entry: y_CallState=InCall;                   |               |
|            |                       |         y_DisplayMode=SplitNavCall;           |               |
|            |                       +-----------------------------------------------+               |
|            |                                               |                                       |
|            |   [u_CallAction == 2                          | [u_CallAction == 2                    |
|            |    && auto_resume == false]                   |  && auto_resume == true]              |
|            +-----------------------------------------------+ (Call Ended -> AUTO RESUME!)         |
|                                                            |                                       |
|                                                            +---------------------------------------+
|                                                                     (Transitions back to           
|                                                                      MEDIA_PLAYING!)               
+----------------------------------------------------------------------------------------------------+
```

---

## 4. Priority & Arbitration Truth Table

| Active Priority Stream | Incoming Request | Priority Delta | Focus Decision | System Action |
| :--- | :--- | :--- | :--- | :--- |
| **Media Playback** (P=40) | **Nav Prompt** (P=60) | Nav > Media | `GAIN_TRANSIENT_MAY_DUCK` | Media volume attenuated from 1.0 to 0.2; Nav voice plays over front speakers |
| **Nav Prompt** (P=60) | **Prompt Finishes** | N/A | `ABANDON` | Media volume ramped back to 1.0; Nav returns to silent guidance |
| **Media Playback** (P=40) | **Incoming Call** (P=75) | Call > Media | `GAIN_TRANSIENT` | Media playback paused; `auto_resume_pending = true`; CID displays call banner overlay; Ringtone plays |
| **Incoming Call** (P=75) | **Call Accepted** (P=80) | Upgrade | `GAIN_TRANSIENT_EXCLUSIVE` | Voice call session active; CID switches to split view (Nav + Call); Hands-free mic/speakers active |
| **Active Call** (P=80) | **Nav Prompt** (P=60) | Call > Nav | `CONCURRENT_MIX` / `ZONE_ROUTING` | Visual turn prompt emphasized on Cluster/HUD; Voice prompt routed to Driver Headrest speaker or suppressed |
| **Active Call** (P=80) | **Call Terminated** | N/A | `ABANDON` | Call session closed; Focus returns to previous stack holder; Since `auto_resume_pending == true`, **Media resumes automatically!** |

---

## 5. C-Code Generation and AUTOSAR Mapping
Using Embedded Coder, this Stateflow model generates ANSI C/C++ conforming to:
- **AUTOSAR Adaptive Platform:** Modeled as `ara::com` Service Interfaces with Skeleton/Proxy classes.
- **Android Automotive OS (AAOS):** Maps directly to `CarAudioService`, `AudioFocusManager`, and `CarActivityManager`.
