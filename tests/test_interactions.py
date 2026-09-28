"""
Automated Unit and Integration Tests for IVI Service Interactions.
Validates:
- Incoming call interruption of media and navigation.
- Automatic media resume on call termination.
- Automatic media resume on call rejection.
- User-paused media does NOT auto-resume after call.
- Navigation voice prompt ducking of media.
- Display layout coordination.
"""

import unittest
from src.simulation import IVISystemSimulator
from src.media_service import MediaState
from src.navigation_service import NavState
from src.telephony_service import CallState
from src.display_manager import CIDLayoutMode


class TestServiceInteractions(unittest.TestCase):
    def setUp(self):
        self.sim = IVISystemSimulator()

    def test_incoming_call_interruption_and_auto_resume(self):
        """
        Verify that an incoming call pauses media with auto-resume pending,
        and terminating the call automatically resumes media playback.
        """
        # Start media
        self.sim.media.user_play()
        self.assertEqual(self.sim.media.state, MediaState.PLAYING)
        self.assertEqual(self.sim.media.volume, 1.0)
        self.assertFalse(self.sim.media.auto_resume_pending)

        # Incoming call arrives
        self.sim.telephony.receive_incoming_call("+1-555-0199", "John Doe")
        self.assertEqual(self.sim.telephony.state, CallState.RINGING)

        # Media must be paused due to transient focus loss
        self.assertEqual(self.sim.media.state, MediaState.PAUSED_TRANSIENT_LOSS)
        self.assertTrue(self.sim.media.auto_resume_pending)
        self.assertEqual(self.sim.display.cid_mode, CIDLayoutMode.NAV_WITH_CALL_OVERLAY)

        # Driver accepts call
        self.sim.telephony.accept_call()
        self.assertEqual(self.sim.telephony.state, CallState.IN_CALL)
        self.assertEqual(self.sim.media.state, MediaState.PAUSED_TRANSIENT_LOSS)
        self.assertEqual(self.sim.display.cid_mode, CIDLayoutMode.SPLIT_NAV_AND_CALL)

        # Driver ends call
        self.sim.telephony.end_call()
        self.assertEqual(self.sim.telephony.state, CallState.IDLE)

        # Media MUST automatically resume!
        self.assertEqual(self.sim.media.state, MediaState.PLAYING)
        self.assertEqual(self.sim.media.volume, 1.0)
        self.assertFalse(self.sim.media.auto_resume_pending)
        self.assertEqual(self.sim.display.cid_mode, CIDLayoutMode.FULL_NAVIGATION)

    def test_call_rejection_auto_resumes_media(self):
        """Verify rejecting a call also triggers automatic media resume."""
        self.sim.media.user_play()
        self.sim.telephony.receive_incoming_call("+1-555-0144", "Spam Caller")

        self.assertEqual(self.sim.media.state, MediaState.PAUSED_TRANSIENT_LOSS)
        self.assertTrue(self.sim.media.auto_resume_pending)

        # Driver rejects call
        self.sim.telephony.reject_call()
        self.assertEqual(self.sim.telephony.state, CallState.IDLE)

        # Media resumes automatically
        self.assertEqual(self.sim.media.state, MediaState.PLAYING)
        self.assertFalse(self.sim.media.auto_resume_pending)

    def test_no_auto_resume_if_user_explicitly_paused(self):
        """
        If the user intentionally paused media, an incoming call and subsequent
        hangup must NOT spuriously resume media playback.
        """
        self.sim.media.user_play()
        self.sim.media.user_pause()
        self.assertEqual(self.sim.media.state, MediaState.PAUSED_BY_USER)
        self.assertFalse(self.sim.media.auto_resume_pending)

        # Incoming call and completion
        self.sim.telephony.receive_incoming_call("+1-555-0188", "Boss")
        self.sim.telephony.accept_call()
        self.sim.telephony.end_call()

        # Media should remain paused by user!
        self.assertEqual(self.sim.media.state, MediaState.PAUSED_BY_USER)
        self.assertFalse(self.sim.media.auto_resume_pending)

    def test_navigation_prompt_ducking_media(self):
        """Verify navigation voice prompt ducks media volume without stopping playback."""
        self.sim.media.user_play()
        self.sim.nav.start_guidance("Convention Center")

        # Maneuver with audio prompt
        self.sim.nav.update_maneuver("Turn left in 300 meters", 300, trigger_audio=True)
        self.assertEqual(self.sim.nav.state, NavState.VOICE_PROMPT_ACTIVE)
        self.assertEqual(self.sim.media.state, MediaState.DUCKED)
        self.assertAlmostEqual(self.sim.media.volume, 0.2)

        # Maneuver audio prompt completes
        self.sim.nav.finish_voice_prompt()
        self.assertEqual(self.sim.nav.state, NavState.GUIDING_SILENT)
        self.assertEqual(self.sim.media.state, MediaState.PLAYING)
        self.assertEqual(self.sim.media.volume, 1.0)


if __name__ == "__main__":
    unittest.main()
