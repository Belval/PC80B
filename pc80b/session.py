from pathlib import Path
from pc80b.segment import Segment

class Session:
    def __init__(self, id: str, start: int, end: int, record_per_dir: int, path: Path):
        self.id = id
        self.start = start
        self.end = end
        self.record_per_dir = record_per_dir + 1
        self.path = path
        self.segments = []
        self.read_segments()

    def read_segments(self):
        if self.segments:
            return

        for i in range(self.start, self.end):
            print(self.path / f"ECG_{i // self.record_per_dir}" / f"{i}.SCP")
            self.segments.append(
                Segment(self.path / f"ECG_{i // self.record_per_dir}" / f"{i}.SCP")
            )

