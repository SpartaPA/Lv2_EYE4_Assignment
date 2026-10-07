"""Bounded CSV sink: one executor producer, one file-owning worker.

No file I/O in record(). Not a real-time scheduling guarantee. Queue overflow
and write errors invalidate a complete evidence recording but do not block
motion control. Startup opens an exclusive file before the serial port opens.
"""
import csv
import queue
import threading
import time


class AsyncCsv:
    def __init__(self, path, capacity=4096, flush_sec=0.25):
        if capacity < 1 or flush_sec <= 0:
            raise ValueError('capacity and flush interval must be positive')
        self.queue = queue.Queue(maxsize=capacity)
        self.stop = threading.Event()
        self.accepted = self.written = self.dropped = 0
        self.error = ''
        self.flush_sec = flush_sec
        self.file = open(path, 'x', newline='')
        try:
            self.writer = csv.writer(self.file, lineterminator='\n')
            self.writer.writerow(['monotonic_sec', 'direction', 'line'])
            self.file.flush()
            self.worker = threading.Thread(target=self._run, name='serial-csv', daemon=True)
            self.worker.start()
        except BaseException:
            self.file.close()
            raise

    def record(self, now, direction, line):
        if self.stop.is_set() or self.error:
            self.dropped += 1
            return False
        try:
            self.queue.put_nowait((now, direction, line))
        except queue.Full:
            self.dropped += 1
            return False
        self.accepted += 1
        return True

    def _run(self):
        next_flush = time.monotonic() + self.flush_sec
        try:
            while not self.stop.is_set() or not self.queue.empty():
                batch = []
                try:
                    batch.append(self.queue.get(timeout=0.05))
                except queue.Empty:
                    pass
                for _ in range(127):
                    try:
                        batch.append(self.queue.get_nowait())
                    except queue.Empty:
                        break
                if batch:
                    self.writer.writerows(batch)
                    self.written += len(batch)
                if time.monotonic() >= next_flush:
                    self.file.flush()
                    next_flush = time.monotonic() + self.flush_sec
            self.file.flush()
        except Exception as exc:
            self.error = f'{type(exc).__name__}: {exc}'
        finally:
            try:
                self.file.close()
            except Exception as exc:
                if not self.error:
                    self.error = f'{type(exc).__name__}: {exc}'

    def snapshot(self):
        # Approximate live counters; final counters are stable after join.
        # written means handed to the file object, not fsync durability.
        return dict(enabled=True, accepted=self.accepted, written=self.written,
                    dropped=self.dropped, error=self.error,
                    worker_alive=self.worker.is_alive(), closing=self.stop.is_set())

    def close(self, timeout=1.0):
        self.stop.set()
        self.worker.join(timeout)
        return self.snapshot()
