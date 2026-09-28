"""
Telephony Service (In-Vehicle Call Manager).
Manages call lifecycles (Incoming, Ringing, Connected, Terminated),
requests high-priority transient audio focus, and coordinates with display and audio managers.
"""

from enum import Enum, auto
from typing import Optional
import logging
from src.audio_policy import AudioPolicyManager, AudioStreamType, FocusRequestType, FocusChangeType

logger = logging.getLogger("TelephonyService")


class CallState(Enum):
    IDLE = auto()
    RINGING = auto()
    IN_CALL = auto()


class TelephonyService:
    CLIENT_ID = "service.telephony"

    def __init__(self, audio_policy: AudioPolicyManager, system_bus=None):
        self.audio_policy = audio_policy
        self.system_bus = system_bus

        self.state: CallState = CallState.IDLE
        self.caller_id: Optional[str] = None
        self.caller_name: Optional[str] = None
        self.call_duration_s: int = 0

    def receive_incoming_call(self, caller_id: str, caller_name: str) -> bool:
        """Trigger an incoming cellular/VoIP call."""
        logger.info(f"Incoming call from {caller_name} ({caller_id})")
        self.caller_id = caller_id
        self.caller_name = caller_name
        self.call_duration_s = 0
        self.state = CallState.RINGING

        # Acquire transient audio focus for ringtone
        # This will preempt media (causing PAUSED_TRANSIENT_LOSS)
        granted = self.audio_policy.request_audio_focus(
            client_id=self.CLIENT_ID,
            stream_type=AudioStreamType.STREAM_RING_TONE,
            request_type=FocusRequestType.AUDIOFOCUS_GAIN_TRANSIENT,
            listener=self.on_audio_focus_change,
        )

        if self.system_bus:
            self.system_bus.publish("telephony/call_incoming", {
                "caller_id": caller_id,
                "caller_name": caller_name,
                "focus_granted": granted,
            })

        return granted

    def accept_call(self) -> bool:
        """User or auto-answer accepts the incoming call."""
        if self.state != CallState.RINGING:
            logger.warning("Cannot accept call: Telephony is not in RINGING state")
            return False

        logger.info(f"Call accepted from {self.caller_name}")
        self.state = CallState.IN_CALL

        # Upgrade focus to STREAM_VOICE_CALL with exclusive transient focus
        granted = self.audio_policy.request_audio_focus(
            client_id=self.CLIENT_ID,
            stream_type=AudioStreamType.STREAM_VOICE_CALL,
            request_type=FocusRequestType.AUDIOFOCUS_GAIN_TRANSIENT_EXCLUSIVE,
            listener=self.on_audio_focus_change,
        )

        if self.system_bus:
            self.system_bus.publish("telephony/call_connected", {
                "caller_id": self.caller_id,
                "caller_name": self.caller_name,
            })

        return granted

    def reject_call(self) -> None:
        """User declines the incoming call."""
        if self.state != CallState.RINGING:
            return

        logger.info(f"Call from {self.caller_name} rejected")
        self.state = CallState.IDLE
        caller = self.caller_name
        self.caller_id = None
        self.caller_name = None

        # Abandon focus so preempted services (Media) can resume
        self.audio_policy.abandon_audio_focus(self.CLIENT_ID)

        if self.system_bus:
            self.system_bus.publish("telephony/call_rejected", {"caller": caller})

    def end_call(self) -> None:
        """User or remote party hangs up the active call."""
        if self.state == CallState.IDLE:
            return

        logger.info(f"Call ended with {self.caller_name} (Duration: {self.call_duration_s}s)")
        self.state = CallState.IDLE
        caller = self.caller_name
        duration = self.call_duration_s
        self.caller_id = None
        self.caller_name = None
        self.call_duration_s = 0

        # Abandon focus -> AudioPolicyManager will automatically restore focus to previous holder!
        self.audio_policy.abandon_audio_focus(self.CLIENT_ID)

        if self.system_bus:
            self.system_bus.publish("telephony/call_ended", {
                "caller": caller,
                "duration_s": duration,
            })

    def on_audio_focus_change(self, focus_change: FocusChangeType) -> None:
        logger.info(f"Telephony Service received focus change: {focus_change.name}")
        # In a real system, if emergency audio (ADAS warning) preempts, call mic/speaker might mute transiently
