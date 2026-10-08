import csv
import tempfile
import threading
import unittest
from pathlib import Path
from realsense_tracker.async_csv import AsyncCsv


class AsyncCsvTests(unittest.TestCase):
    def test_rows_and_exclusive_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'log.csv'
            sink = AsyncCsv(path)
            for i in range(20):
                self.assertTrue(sink.record(i, 'RX', 'a,b'))
            result = sink.close()
            self.assertFalse(result['worker_alive'])
            self.assertEqual(result['written'], 20)
            self.assertEqual(result['dropped'], 0)
            self.assertEqual(result['error'], '')
            with path.open(newline='') as f:
                rows = list(csv.reader(f))
            self.assertEqual(len(rows), 21)
            self.assertEqual(rows[-1], ['19', 'RX', 'a,b'])
            with self.assertRaises(FileExistsError):
                AsyncCsv(path)

    def test_stalled_writer_queue_overflow_and_bounded_close(self):
        with tempfile.TemporaryDirectory() as d:
            sink = AsyncCsv(Path(d) / 'log.csv', capacity=2)
            entered, release, submitted = threading.Event(), threading.Event(), threading.Event()
            real = sink.writer
            class Slow:
                def writerows(self, rows):
                    entered.set()
                    release.wait(3)
                    real.writerows(rows)
            sink.writer = Slow()
            sink.record(0, 'RX', 'first')
            self.assertTrue(entered.wait(1))
            def produce():
                for i in range(100):
                    sink.record(i, 'TX', 'next')
                submitted.set()
            producer = threading.Thread(target=produce, daemon=True)
            try:
                producer.start()
                self.assertTrue(submitted.wait(1), 'Producer blocked on writer')
                result = sink.close(timeout=0.01)
                self.assertTrue(result['worker_alive'])
                self.assertEqual(result['accepted'], 3)
                self.assertEqual(result['dropped'], 98)
            finally:
                release.set()
                producer.join(1)
                result = sink.close()
            self.assertFalse(result['worker_alive'])
            self.assertEqual(result['written'], 3)

    def test_write_failure_reported_and_later_records_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            sink = AsyncCsv(Path(d) / 'log.csv')
            class Broken:
                def writerows(self, rows):
                    raise OSError('injected disk error')
            sink.writer = Broken()
            sink.record(1, 'RX', 'row')
            result = sink.close()
            self.assertIn('injected disk error', result['error'])
            self.assertFalse(sink.record(2, 'TX', 'later'))
            self.assertEqual(sink.snapshot()['dropped'], 1)


if __name__ == '__main__':
    unittest.main()
