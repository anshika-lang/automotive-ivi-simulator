"""
Media Playback Service.
Handles audio playback states, user commands, and automatic resumption logic
upon regaining audio focus following transient interruption (e.g. incoming call).
"""

from enum import Enum, auto
from typing import Optional
import logging
from src.audio_policy import AudioPolicyManager, AudioStreamType, FocusRequestType, FocusChangeType

logger = logging.getLogger("MediaPlaybackService")


class MediaState(Enum):
    STOPPED = auto()
    PLAYING = auto()
    PAUSED_BY_USER = auto()
    PAUSED_TRANSIENT_LOSS = auto()
    DUCKED = auto()


class MediaPlaybackService:
    CLIENT_ID = "service.media_playback"

    def __init__(self, audio_policy: AudioPolicyManager, system_bus=None):
        self.audio_policy = audio_policy
        self.system_bus = system_bus

        self.state: MediaState = MediaState.STOPPED
        self.current_track: str = "Automotive Synthwave - CyberDrive"
        self.playback_position_ms: int = 0
        self.volume: float = 1.0
        self.auto_resume_pending: bool = False

    def user_play(self) -> bool:
        """User commands playback to start or resume."""
        logger.info("User requested Play")
        granted = self.audio_policy.request_audio_focus(
            client_id=self.CLIENT_ID,
            stream_type=AudioStreamType.STREAM_MEDIA,
            request_type=FocusRequestType.AUDIOFOCUS_GAIN,
            listener=self.on_audio_focus_change,
        )

        if granted:
            self.state = MediaState.PLAYING
            self.volume = 1.0
            self.auto_resume_pending = False
            self._notify_state_changed("User started playback")
            return True
        else:
            logger.warning("Play request rejected by AudioPolicyManager")
            return False

    def user_pause(self) -> None:
        """User explicitly pauses media."""
        logger.info("User requested Pause")
        self.state = MediaState.PAUSED_BY_USER
        self.auto_resume_pending = False
        self.audio_policy.abandon_audio_focus(self.CLIENT_ID)
        self._notify_state_changed("User paused playback")

    def on_audio_focus_change(self, focus_change: FocusChangeType) -> None:
        """Callback invoked by AudioPolicyManager when audio focus shifts."""
        logger.info(f"Media Service received audio focus change: {focus_change.name}")

        if focus_change == FocusChangeType.AUDIOFOCUS_GAIN:
            if self.state == MediaState.PAUSED_TRANSIENT_LOSS and self.auto_resume_pending:
                # AUTOMATIC RESUME USE CASE
                logger.info(">>> AUTOMATIC RESUME: Restoring media playback after call/prompt interruption <<<")
                self.state = MediaState.PLAYING
                self.volume = 1.0
                self.auto_resume_pending = False
                self._notify_state_changed("Automatic media resume triggered")
            elif self.state == MediaState.DUCKED:
                logger.info("Restoring volume from ducked state")
                self.state = MediaState.PLAYING
                self.volume = 1.0
                self._notify_state_changed("Volume restored from duck")
            elif self.state == MediaState.PAUSED_BY_USER:
                logger.info("Media was paused explicitly by user; ignoring focus gain")

        elif focus_change == FocusChangeType.AUDIOFOCUS_LOSS_TRANSIENT:
            # INCOMING CALL INTERRUPTION USE CASE
            if self.state in [MediaState.PLAYING, MediaState.DUCKED]:
                logger.info(">>> INTERRUPTION: Pausing media due to transient call/alert focus loss <<<")
                self.state = MediaState.PAUSED_TRANSIENT_LOSS
                self.auto_resume_pending = True
                self.volume = 0.0
                self._notify_state_changed("Playback paused due to transient focus loss (Call/High priority)")

        elif focus_change == FocusChangeType.AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK:
            if self.state == MediaState.PLAYING:
                logger.info("Ducking media volume for navigation prompt")
                self.state = MediaState.DUCKED
                self.volume = 0.2
                self._notify_state_changed("Media volume ducked to 20%")

        elif focus_change == FocusChangeType.AUDIOFOCUS_LOSS:
            logger.info("Permanent audio focus loss; stopping playback")
            self.state = MediaState.STOPPED
            self.auto_resume_pending = False
            self.volume = 0.0
            self._notify_state_changed("Media stopped due to permanent focus loss")

    def simulate_playback_progress(self, elapsed_ms: int) -> None:
        if self.state in [MediaState.PLAYING, MediaState.DUCKED]:
            self.playback_position_ms += elapsed_ms

    def _notify_state_changed(self, reason: str) -> None:
        if self.system_bus:
            self.system_bus.publish("media/state_changed", {
                "state": self.state.name,
                "track": self.current_track,
                "position_ms": self.playback_position_ms,
                "volume": self.volume,
                "auto_resume_pending": self.auto_resume_pending,
                "reason": reason,
            })
