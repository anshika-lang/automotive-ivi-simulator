"""
Navigation Guidance Service.
Generates visual maneuvers and requests transient audio focus for turn-by-turn voice prompts.
Handles arbitration and ducking interaction with media and active phone calls.
"""

from enum import Enum, auto
from typing import Optional
import logging
from src.audio_policy import AudioPolicyManager, AudioStreamType, FocusRequestType, FocusChangeType

logger = logging.getLogger("NavigationService")


class NavState(Enum):
    IDLE = auto()
    GUIDING_SILENT = auto()
    VOICE_PROMPT_ACTIVE = auto()


class NavigationService:
    CLIENT_ID = "service.navigation"

    def __init__(self, audio_policy: AudioPolicyManager, system_bus=None):
        self.audio_policy = audio_policy
        self.system_bus = system_bus

        self.state: NavState = NavState.IDLE
        self.destination: Optional[str] = None
        self.current_instruction: str = "No Route"
        self.distance_remaining_m: int = 0
        self.current_prompt_text: Optional[str] = None

    def start_guidance(self, destination: str) -> None:
        """Start turn-by-turn guidance along a route."""
        self.destination = destination
        self.state = NavState.GUIDING_SILENT
        self.current_instruction = "Follow Route to " + destination
        self.distance_remaining_m = 5000
        logger.info(f"Guidance started to: {destination}")
        self._notify_nav_update("Route started")

    def stop_guidance(self) -> None:
        """Cancel active navigation."""
        if self.state == NavState.VOICE_PROMPT_ACTIVE:
            self.finish_voice_prompt()
        self.state = NavState.IDLE
        self.destination = None
        self.current_instruction = "No Route"
        self.distance_remaining_m = 0
        logger.info("Guidance stopped")
        self._notify_nav_update("Route cancelled")

    def update_maneuver(self, instruction: str, distance_m: int, trigger_audio: bool = False) -> None:
        """Update upcoming turn/maneuver instruction and optionally fire voice prompt."""
        self.current_instruction = instruction
        self.distance_remaining_m = distance_m
        logger.info(f"Nav maneuver update: '{instruction}' in {distance_m}m")
        self._notify_nav_update("Maneuver updated")

        if trigger_audio and self.state != NavState.IDLE:
            self.trigger_voice_prompt(f"In {distance_m} meters, {instruction}")

    def trigger_voice_prompt(self, prompt_text: str) -> bool:
        """Requests transient focus to speak a turn-by-turn alert."""
        logger.info(f"Triggering voice prompt: '{prompt_text}'")
        self.current_prompt_text = prompt_text

        # Nav voice prompts request transient focus and allow ducking of lower streams (like media)
        granted = self.audio_policy.request_audio_focus(
            client_id=self.CLIENT_ID,
            stream_type=AudioStreamType.STREAM_NAVIGATION,
            request_type=FocusRequestType.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK,
            listener=self.on_audio_focus_change,
        )

        if granted:
            self.state = NavState.VOICE_PROMPT_ACTIVE
            if self.system_bus:
                self.system_bus.publish("nav/prompt_started", {
                    "prompt": prompt_text,
                    "distance_m": self.distance_remaining_m
                })
            return True
        else:
            logger.warning("Voice prompt focus request denied by AudioPolicyManager")
            return False

    def finish_voice_prompt(self) -> None:
        """Prompt has finished playing, abandon focus."""
        if self.state == NavState.VOICE_PROMPT_ACTIVE:
            logger.info("Voice prompt finished; abandoning audio focus")
            self.state = NavState.GUIDING_SILENT
            finished_prompt = self.current_prompt_text
            self.current_prompt_text = None
            self.audio_policy.abandon_audio_focus(self.CLIENT_ID)
            if self.system_bus:
                self.system_bus.publish("nav/prompt_finished", {"prompt": finished_prompt})

    def on_audio_focus_change(self, focus_change: FocusChangeType) -> None:
        logger.info(f"Nav Service received audio focus change: {focus_change.name}")
        if focus_change in [FocusChangeType.AUDIOFOCUS_LOSS, FocusChangeType.AUDIOFOCUS_LOSS_TRANSIENT]:
            if self.state == NavState.VOICE_PROMPT_ACTIVE:
                logger.info("Nav voice prompt interrupted by higher priority stream (e.g. Call/Emergency)")
                self.state = NavState.GUIDING_SILENT
                self.current_prompt_text = None
                self._notify_nav_update("Voice prompt preempted")

    def _notify_nav_update(self, reason: str) -> None:
        if self.system_bus:
            self.system_bus.publish("nav/state_changed", {
                "state": self.state.name,
                "destination": self.destination,
                "instruction": self.current_instruction,
                "distance_m": self.distance_remaining_m,
                "prompt": self.current_prompt_text,
                "reason": reason,
            })
