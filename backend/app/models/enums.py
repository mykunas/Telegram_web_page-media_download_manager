from enum import Enum


class DownloadStatus(str, Enum):
    WAITING = "waiting"
    DOWNLOADING = "downloading"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    DUPLICATE = "duplicate"
