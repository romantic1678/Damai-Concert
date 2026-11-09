"""Optional sound alert; disableable; no-op without audio."""

from __future__ import annotations

import sys
from pathlib import Path

from app.logging_config import get_logger

logger = get_logger("notify.sound")


class SoundNotifier:
    name = "sound"

    def __init__(
        self,
        *,
        enabled: bool = True,
        wav_path: Path | None = None,
    ) -> None:
        self.enabled = enabled
        self._wav_path = wav_path

    def send(self, title: str, message: str, *, urgent: bool = False) -> bool:
        if not self.enabled:
            return False
        try:
            if self._wav_path and self._wav_path.is_file():
                return self._play_wav(self._wav_path)
            return self._beep()
        except Exception as exc:  # noqa: BLE001
            logger.debug("sound notify failed: %s", exc)
            return False

    def _beep(self) -> bool:
        if sys.platform.startswith("win"):
            import winsound

            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            return True
        # Portable ASCII bell — may be ignored on headless terminals
        sys.stdout.write("\a")
        sys.stdout.flush()
        return True

    def _play_wav(self, path: Path) -> bool:
        if sys.platform.startswith("win"):
            import winsound

            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
            return True
        # Non-Windows: do not shell out to players; treat as soft no-op success=False
        logger.debug("wav playback not implemented on %s", sys.platform)
        return self._beep()
