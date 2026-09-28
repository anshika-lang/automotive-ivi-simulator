"""
Display & HMI Manager (Cockpit Window Arbitrator).
Manages multi-display layout policies (Center Display, Instrument Cluster, HUD)
ensuring route guidance visibility remains intact even during call interruption.
"""

from enum import Enum, auto
from typing import Dict, Any
import logging

logger = logging.getLogger("DisplayManager")


class CIDLayoutMode(Enum):
    FULL_MEDIA = auto()
    FULL_NAVIGATION = auto()
    NAV_WITH_CALL_OVERLAY = auto()
    SPLIT_NAV_AND_CALL = auto()


class DisplayManager:
    def __init__(self, system_bus=None):
        self.system_bus = system_bus

        self.cid_mode: CIDLayoutMode = CIDLayoutMode.FULL_NAVIGATION
        self.cluster_display: str = "Speedometer | Mini-Map Turn Indicator"
        self.hud_display: str = "Speed: 65 km/h | Arrow: Turn Right in 250m"
        self.call_overlay_visible: bool = False
        self.active_banner: str = ""

        if self.system_bus:
            self._register_listeners()

    def _register_listeners(self) -> None:
        self.system_bus.subscribe("telephony/call_incoming", self._on_call_incoming)
        self.system_bus.subscribe("telephony/call_connected", self._on_call_connected)
        self.system_bus.subscribe("telephony/call_ended", self._on_call_ended)
        self.system_bus.subscribe("telephony/call_rejected", self._on_call_rejected)
        self.system_bus.subscribe("nav/state_changed", self._on_nav_updated)

    def _on_call_incoming(self, payload: Dict[str, Any]) -> None:
        caller = payload.get("caller_name", "Unknown")
        logger.info(f"HMI Display: Displaying Incoming Call Overlay for {caller}")
        self.cid_mode = CIDLayoutMode.NAV_WITH_CALL_OVERLAY
        self.call_overlay_visible = True
        self.active_banner = f"INCOMING CALL: {caller}"

    def _on_call_connected(self, payload: Dict[str, Any]) -> None:
        caller = payload.get("caller_name", "Unknown")
        logger.info(f"HMI Display: Switching to Split View (Nav + In-Call controls)")
        self.cid_mode = CIDLayoutMode.SPLIT_NAV_AND_CALL
        self.call_overlay_visible = True
        self.active_banner = f"IN CALL: {caller}"

    def _on_call_ended(self, payload: Dict[str, Any]) -> None:
        logger.info("HMI Display: Restoring Full Navigation screen")
        self.cid_mode = CIDLayoutMode.FULL_NAVIGATION
        self.call_overlay_visible = False
        self.active_banner = ""

    def _on_call_rejected(self, payload: Dict[str, Any]) -> None:
        logger.info("HMI Display: Restoring Full Navigation screen after rejection")
        self.cid_mode = CIDLayoutMode.FULL_NAVIGATION
        self.call_overlay_visible = False
        self.active_banner = ""

    def _on_nav_updated(self, payload: Dict[str, Any]) -> None:
        instruction = payload.get("instruction", "")
        dist = payload.get("distance_m", 0)
        self.hud_display = f"Speed: 65 km/h | Arrow: {instruction} ({dist}m)"
        self.cluster_display = f"Speedometer | {instruction} [{dist}m]"

    def get_layout_state(self) -> Dict[str, Any]:
        return {
            "cid_mode": self.cid_mode.name,
            "call_overlay_visible": self.call_overlay_visible,
            "active_banner": self.active_banner,
            "cluster": self.cluster_display,
            "hud": self.hud_display,
        }
