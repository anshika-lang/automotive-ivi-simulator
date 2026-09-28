"""
Audio Policy & Focus Arbitration Manager.
Implements automotive-grade audio stream arbitration, focus stack management,
and ducking/preemption policies (similar to Android Automotive CarAudioService and COVESA Audio Manager).
"""

from enum import Enum, auto
from typing import Dict, List, Optional, Callable
import logging

logger = logging.getLogger("AudioPolicyManager")


class AudioStreamType(Enum):
    STREAM_EMERGENCY = 100
    STREAM_VOICE_CALL = 80
    STREAM_RING_TONE = 75
    STREAM_VOICE_ASSISTANT = 70
    STREAM_NAVIGATION = 60
    STREAM_MEDIA = 40
    STREAM_NOTIFICATION = 30


class FocusRequestType(Enum):
    AUDIOFOCUS_GAIN = auto()
    AUDIOFOCUS_GAIN_TRANSIENT = auto()
    AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK = auto()
    AUDIOFOCUS_GAIN_TRANSIENT_EXCLUSIVE = auto()


class FocusChangeType(Enum):
    AUDIOFOCUS_GAIN = auto()
    AUDIOFOCUS_LOSS = auto()
    AUDIOFOCUS_LOSS_TRANSIENT = auto()
    AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK = auto()


class AudioFocusEntry:
    def __init__(
        self,
        client_id: str,
        stream_type: AudioStreamType,
        request_type: FocusRequestType,
        listener: Callable[[FocusChangeType], None],
    ):
        self.client_id = client_id
        self.stream_type = stream_type
        self.request_type = request_type
        self.listener = listener
        self.current_volume: float = 1.0  # 0.0 to 1.0


class AudioPolicyManager:
    """Arbitrates audio requests according to stream priorities and ducking rules."""

    def __init__(self, system_bus=None):
        self.system_bus = system_bus
        # Stack of active focus holders, ordered from lowest to highest priority / recency
        self._focus_stack: List[AudioFocusEntry] = []
        self._duck_factor: float = 0.2  # 20% volume during ducking

    @property
    def current_focus_holder(self) -> Optional[AudioFocusEntry]:
        return self._focus_stack[-1] if self._focus_stack else None

    def request_audio_focus(
        self,
        client_id: str,
        stream_type: AudioStreamType,
        request_type: FocusRequestType,
        listener: Callable[[FocusChangeType], None],
    ) -> bool:
        """
        Request audio focus for a client stream.
        Returns True if granted, False if rejected.
        """
        logger.info(
            f"Focus request from '{client_id}' (stream: {stream_type.name}, req: {request_type.name})"
        )

        new_entry = AudioFocusEntry(client_id, stream_type, request_type, listener)

        # Check against current stack top
        if self._focus_stack:
            top_entry = self._focus_stack[-1]

            # If top entry has strictly higher priority and is exclusive, evaluate preemption
            if top_entry.stream_type.value > stream_type.value and \
               top_entry.request_type in [FocusRequestType.AUDIOFOCUS_GAIN_TRANSIENT, FocusRequestType.AUDIOFOCUS_GAIN_TRANSIENT_EXCLUSIVE]:
                # Special automotive arbitration:
                # E.g., If in active phone call (80) and Nav prompt (60) arrives:
                # Nav prompt request is allowed if it's transient may duck or cluster routing,
                # but if call is exclusive, Nav may be ducked or mixed into driver side.
                if request_type == FocusRequestType.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK:
                    # Let Nav prompt play concurrently without demoting the top phone call
                    logger.info(f"Concurrently mixing {client_id} with higher priority {top_entry.client_id}")
                    # Insert below top or handle concurrent secondary focus
                    self._focus_stack.insert(-1, new_entry)
                    listener(FocusChangeType.AUDIOFOCUS_GAIN)
                    if self.system_bus:
                        self.system_bus.publish("audio/focus_granted", {
                            "client_id": client_id,
                            "stream": stream_type.name,
                            "mixed_with": top_entry.client_id
                        })
                    return True
                else:
                    logger.warning(
                        f"Focus request denied for '{client_id}'. Current focus held by higher priority '{top_entry.client_id}'"
                    )
                    return False

            # Existing entries need to be notified of loss / ducking
            for entry in self._focus_stack:
                if entry.client_id == client_id:
                    continue  # Will be removed/re-added

                if request_type == FocusRequestType.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK:
                    # Notify existing entries they can duck if lower priority
                    if entry.stream_type.value < stream_type.value:
                        logger.info(f"Notifying '{entry.client_id}' to DUCK")
                        entry.current_volume = self._duck_factor
                        entry.listener(FocusChangeType.AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK)
                elif request_type in [FocusRequestType.AUDIOFOCUS_GAIN_TRANSIENT, FocusRequestType.AUDIOFOCUS_GAIN_TRANSIENT_EXCLUSIVE]:
                    # Full transient preemption (e.g. Phone call interrupts Media)
                    logger.info(f"Notifying '{entry.client_id}' of TRANSIENT LOSS")
                    entry.current_volume = 0.0
                    entry.listener(FocusChangeType.AUDIOFOCUS_LOSS_TRANSIENT)
                elif request_type == FocusRequestType.AUDIOFOCUS_GAIN:
                    # Permanent gain (e.g. User starts new media source)
                    logger.info(f"Notifying '{entry.client_id}' of PERMANENT LOSS")
                    entry.current_volume = 0.0
                    entry.listener(FocusChangeType.AUDIOFOCUS_LOSS)

        # Remove any existing entry for this client to avoid duplicates
        self._focus_stack = [e for e in self._focus_stack if e.client_id != client_id]
        self._focus_stack.append(new_entry)

        # Grant focus to requester
        listener(FocusChangeType.AUDIOFOCUS_GAIN)

        if self.system_bus:
            self.system_bus.publish("audio/focus_granted", {
                "client_id": client_id,
                "stream": stream_type.name,
                "request_type": request_type.name,
                "stack": [e.client_id for e in self._focus_stack]
            })

        return True

    def abandon_audio_focus(self, client_id: str) -> None:
        """
        Abandon audio focus when playback/call finishes.
        Restores focus to the next eligible client in the stack.
        """
        logger.info(f"Focus abandoned by '{client_id}'")

        if not self._focus_stack:
            return

        was_top = (self._focus_stack[-1].client_id == client_id)
        self._focus_stack = [e for e in self._focus_stack if e.client_id != client_id]

        if self.system_bus:
            self.system_bus.publish("audio/focus_abandoned", {
                "client_id": client_id,
                "remaining_stack": [e.client_id for e in self._focus_stack]
            })

        # If the departing client was at the top, restore focus to the new top
        if was_top and self._focus_stack:
            new_top = self._focus_stack[-1]
            logger.info(f"Restoring audio focus to '{new_top.client_id}'")
            new_top.current_volume = 1.0
            new_top.listener(FocusChangeType.AUDIOFOCUS_GAIN)

            if self.system_bus:
                self.system_bus.publish("audio/focus_restored", {
                    "client_id": new_top.client_id,
                    "stream": new_top.stream_type.name
                })

    def get_stack_summary(self) -> List[Dict[str, Any]]:
        return [
            {
                "client_id": e.client_id,
                "stream_type": e.stream_type.name,
                "request_type": e.request_type.name,
                "volume": e.current_volume,
            }
            for e in self._focus_stack
        ]
