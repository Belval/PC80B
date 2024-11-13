from pathlib import Path

from pc80b.session import Session

def strip_empty(l):
    return [e for e in l if len(e)]

class Device:
    def __init__(self, path):
        self.path = Path(path)
        self.sessions = []
        self.create_sessions()

    def create_sessions(self):
        if self.sessions:
            return
        with open(self.path / "README.TXT", "r") as fh:
            lines = fh.readlines()
            self.max_per_dir = int(lines[2][:-1])
            self.version_id = lines[4][:-1]
            self.product_id = lines[6][:-1]

            assert len(lines) > 9, "No sessions are listed in the README.TXT"

            for session_line in lines[9:]:
                fields = strip_empty(session_line.split(" "))
                if not len(fields) == 4:
                    continue
                session_id, session_start, session_end = fields[0], fields[1], fields[2]
                self.sessions.append(
                    Session(
                        id=session_id,
                        start=int(session_start.split(".")[0]),
                        end=int(session_end.split(".")[0]),
                        record_per_dir=self.max_per_dir,
                        path=self.path
                    )
                )
