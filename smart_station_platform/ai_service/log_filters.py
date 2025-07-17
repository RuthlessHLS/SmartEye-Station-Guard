import logging

class QuietWebRTCFilter(logging.Filter):
    def filter(self, record):
        if record.levelno <= logging.DEBUG and "发送帧" in record.getMessage():
            return False
        return True

class QuietICEFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        if "Could not bind to" in msg or "Connection(" in msg and record.levelno < logging.WARNING:
            return False
        return True 