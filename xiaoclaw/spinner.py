"""Spinner progress indicator using threading (works with async main loop)."""

import sys
import threading
import time


class Spinner:
    """A spinner progress indicator that runs in a background thread.
    
    Usage:
        spinner = Spinner("思考中...")
        spinner.start()
        # ... do work ...
        spinner.stop()
    """
    
    def __init__(self, message: str = "思考中..."):
        self.message = message
        self.frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self._stop_event = threading.Event()
        self._thread: threading.Thread = None
    
    def start(self):
        """Start the spinner in a background thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
    
    def _spin(self):
        """Background thread that prints the spinning animation."""
        i = 0
        while not self._stop_event.is_set():
            sys.stdout.write(f'\r{self.message}{self.frames[i % len(self.frames)]}')
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1
        # Clear the line when stopped
        sys.stdout.write('\r' + ' ' * (len(self.message) + 2))
        sys.stdout.flush()
    
    def stop(self):
        """Stop the spinner."""
        self._stop_event.set()
        if self._thread:
            self._thread.join()
