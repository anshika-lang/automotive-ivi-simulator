# Automotive IVI Service Interaction Model & Cockpit Simulator

A simplified, automotive-grade service interaction model demonstrating **Audio Focus Arbitration**, **Incoming Call Interruption during Navigation**, and **Automatic Media Resumption**.

Modeled for **UML 2.5**, **Simulink / Stateflow**, and executable **Python / HTML5 Cockpit Simulation**.

---

## 📁 Repository Structure

```
d:\Automotive\mod6\
├── README.md                           # Main Overview & Quick Start
├── docs/
│   ├── service_interaction_spec.md     # Detailed Architectural Specification & Mermaid Diagrams
│   └── simulink_model_guide.md         # Simulink & Stateflow Model Design & Signals
├── uml/                                # Complete PlantUML Diagrams
│   ├── component_architecture.puml     # Component & Port Interface Diagram
│   ├── class_diagram.puml              # Object-Oriented Class Diagram
│   ├── seq_incoming_call.puml          # Sequence: Incoming Call Interruption
│   ├── seq_nav_during_call.puml        # Sequence: Navigation Prompt during Call
│   ├── seq_call_end_resume.puml        # Sequence: Call Termination & Automatic Media Resume
│   ├── state_media_player.puml         # State Machine: Media Playback Service
│   ├── state_audio_policy.puml         # State Machine: Audio Focus Manager
│   └── state_telephony.puml            # State Machine: Telephony Service
├── simulink/
│   ├── create_ivi_service_model.m      # MATLAB script to generate Simulink/Stateflow model
│   └── stateflow_logic.md              # Stateflow Charts, Truth Tables & Data Dictionary
├── src/                                # Executable Service Architecture Engine (Python)
│   ├── audio_policy.py                 # Priority Stack & Audio Focus Arbiter
│   ├── media_service.py                # Media Player with Auto-Resume Memory
│   ├── navigation_service.py           # Route Guidance & Maneuver Prompts
│   ├── telephony_service.py            # Call Session Manager
│   ├── display_manager.py              # CID / Cluster / HUD Display Arbitrator
│   ├── system_bus.py                   # Event Bus simulating SOME/IP & Android IPC
│   └── simulation.py                   # Scenario Simulation Orchestrator
├── tests/
│   └── test_interactions.py            # Automated Unit & Integration Tests (100% Pass)
└── web/
    └── index.html                      # Interactive Cockpit HMI Simulator & VU Meters
```

---

## 🚀 Quick Start

### 1. Run the Python Simulation Orchestrator
To observe the step-by-step service interaction trace in the console:
```bash
python -m src.simulation
```

### 2. Run the Automated Test Suite
To verify interruption, ducking, and auto-resume edge cases:
```bash
python -m unittest tests/test_interactions.py
```

### 3. Open the Interactive Digital Cockpit Simulator
Open `web/index.html` in any web browser. You can:
- Trigger music playback and observe audio meters.
- Trigger turn-by-turn voice prompts to see **Media Ducking (attenuated to 20%)**.
- Trigger an **Incoming Phone Call** to see:
  - Media automatically pause and arm the `auto_resume_pending` flag.
  - The Center Display overlay an incoming call dialog while keeping turn-by-turn guidance visible on the Cluster/HUD.
- Accept the call and converse hands-free.
- Hang up the call to witness **Automatic Media Resume** (music smoothly resumes at its saved position)!

---

## 🎯 Key Use Cases Implemented

1. **Incoming Call Interruption during Active Media & Navigation Guidance:**
   - Preemption of lower-priority `STREAM_MEDIA` (Priority 40) by `STREAM_RING_TONE` (Priority 75).
   - Display arbitration preserving navigation route guidance while overlaying call controls.
2. **Navigation Turn Maneuver Arbitration during an Active Call:**
   - Safety route guidance preservation via HUD/Cluster display or driver-headrest speaker routing.
3. **Automatic Media Resumption:**
   - Stateful restoration of audio focus to the preempted media service when the call terminates.
   - Guard against spurious resumption if the driver had paused playback manually prior to the call.

---

## 📊 Models Included

- **UML Diagrams:** Component, Class, Sequence, and State Machine diagrams located in `uml/` and rendered in `docs/service_interaction_spec.md`.
- **Simulink / Stateflow:** MATLAB programmatic model generator in `simulink/create_ivi_service_model.m` and architectural spec in `simulink/stateflow_logic.md`.
