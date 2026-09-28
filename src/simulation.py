"""
System Simulation Orchestrator.
Initializes the IVI services (AudioPolicy, Media, Nav, Telephony, Display)
and runs interactive or automated scenario traces.
"""

from typing import Dict, Any
from src.system_bus import SystemBus
from src.audio_policy import AudioPolicyManager
from src.media_service import MediaPlaybackService, MediaState
from src.navigation_service import NavigationService, NavState
from src.telephony_service import TelephonyService, CallState
from src.display_manager import DisplayManager, CIDLayoutMode


class IVISystemSimulator:
    def __init__(self):
        self.bus = SystemBus()
        self.audio_policy = AudioPolicyManager(system_bus=self.bus)
        self.media = MediaPlaybackService(audio_policy=self.audio_policy, system_bus=self.bus)
        self.nav = NavigationService(audio_policy=self.audio_policy, system_bus=self.bus)
        self.telephony = TelephonyService(audio_policy=self.audio_policy, system_bus=self.bus)
        self.display = DisplayManager(system_bus=self.bus)

    def get_snapshot(self) -> Dict[str, Any]:
        """Get instantaneous state snapshot of all services."""
        return {
            "media": {
                "state": self.media.state.name,
                "track": self.media.current_track,
                "volume": self.media.volume,
                "position_ms": self.media.playback_position_ms,
                "auto_resume_pending": self.media.auto_resume_pending,
            },
            "navigation": {
                "state": self.nav.state.name,
                "destination": self.nav.destination,
                "instruction": self.nav.current_instruction,
                "distance_m": self.nav.distance_remaining_m,
                "prompt": self.nav.current_prompt_text,
            },
            "telephony": {
                "state": self.telephony.state.name,
                "caller": self.telephony.caller_name,
                "duration_s": self.telephony.call_duration_s,
            },
            "audio_policy": {
                "active_focus": self.audio_policy.current_focus_holder.client_id
                if self.audio_policy.current_focus_holder
                else "None",
                "stack": self.audio_policy.get_stack_summary(),
            },
            "display": self.display.get_layout_state(),
        }

    def run_full_use_case_sequence(self) -> None:
        """Executes the standard end-to-end user scenario."""
        print("=== Step 1: User starts Navigation and Media Playback ===")
        self.nav.start_guidance("Munich Airport - Terminal 2")
        self.media.user_play()
        self.media.simulate_playback_progress(15000)

        print("\n=== Step 2: Navigation Voice Prompt Ducking Media ===")
        self.nav.update_maneuver("Take Exit 42 toward Airport", 800, trigger_audio=True)
        # Media volume should duck to 0.2
        self.nav.finish_voice_prompt()
        # Media volume restored to 1.0

        print("\n=== Step 3: Incoming Call Interruption ===")
        self.telephony.receive_incoming_call("+49-170-1234567", "Alice (Engineering Lead)")

        print("\n=== Step 4: Driver Accepts Call via Steering Wheel Controls ===")
        self.telephony.accept_call()

        print("\n=== Step 5: Navigation Maneuver Update during Active Call ===")
        self.nav.update_maneuver("Keep Left at fork", 250, trigger_audio=False)

        print("\n=== Step 6: Call Ends - Automatic Media Resume ===")
        self.telephony.end_call()
        # Media should automatically resume to PLAYING!


if __name__ == "__main__":
    sim = IVISystemSimulator()
    sim.run_full_use_case_sequence()
