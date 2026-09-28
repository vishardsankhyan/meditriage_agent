import sounddevice as sd
from queue import Queue

SAMPLE_RATE = 24000
CHUNK_SIZE = 1200 # 50ms chunks at 24kHz

class Mic:
    def __init__(self):
        self.queue = Queue()
        self._stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=CHUNK_SIZE,
            channels=1,
            dtype='int16',
            callback=self._callback
        )

    def _callback(self, indata, frames, time, status):
        self.queue.put(bytes(indata))

    def start(self):
        self._stream.start()

    def stop(self):
        self._stream.stop()
        self._stream.close()

class Speaker:
    def __init__(self):
        self._stream = self._open()
        self._stream.start()

    def _open(self):
        return sd.RawOutputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype='int16'
        )

    def play(self, audio_bytes):
        self._stream.write(audio_bytes)

    def flush_and_restart(self):
        try:
            self._stream.stop()
            self._stream.close()
        except Exception:
            pass
        self._stream = self._open()
        self._stream.start()

    def close(self):
        self._stream.stop()
        self._stream.close()