# Simulink & Stateflow Implementation Guide

This guide details how to import and run the automotive IVI service interaction model in MathWorks MATLAB/Simulink and Stateflow.

---

## 1. Prerequisites
- MATLAB R2020b or higher
- Simulink
- Stateflow (optional for Stateflow chart; fallback Simulink subsystem provided)
- Embedded Coder (optional, for C/C++ AUTOSAR code generation)

---

## 2. Generating the Model Programmatically
1. Open MATLAB.
2. Navigate to `d:\Automotive\mod6\simulink`.
3. In the MATLAB Command Window, execute:
   ```matlab
   create_ivi_service_model
   ```
4. This script programmatically initializes `IVI_Service_Interaction_Model.slx`, instantiates the input ports (`u_MediaCmd`, `u_NavVoicePrompt`, `u_IncomingCall`, `u_CallAction`), the Stateflow Chart with all hierarchical states (`IDLE`, `MEDIA_PLAYING`, `MEDIA_DUCKED`, `CALL_RINGING`, `CALL_ACTIVE`), and sets the discrete fixed-step solver to 10 ms.

---

## 3. Signal Mapping & Execution
- In Stateflow, transitions are driven by discrete events:
  - When `u_IncomingCall == true`, the chart executes an entry action saving `auto_resume_pending = true` and muting `y_MediaVolume`.
  - When `u_CallAction == 2` (Hang up) and `auto_resume_pending == true`, the Stateflow chart transitions directly back to `MEDIA_PLAYING` and restores `y_MediaVolume = 1.0`.
