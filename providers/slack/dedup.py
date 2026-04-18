from collections import OrderedDict


class DedupCache:
    """Tiny in-memory LRU for Slack event dedup.

    Slack may redeliver the same event within a few seconds if the first
    ack times out. Key by `client_msg_id` when present, otherwise fall back
    to `event_ts + channel`. 1000 entries is enough for the redelivery
    window and costs < 100 KB.
    """

    def __init__(self, maxsize: int = 1000) -> None:
        self._d: OrderedDict[str, bool] = OrderedDict()
        self._max = maxsize

    def seen(self, key: str) -> bool:
        if key in self._d:
            self._d.move_to_end(key)
            return True
        self._d[key] = True
        if len(self._d) > self._max:
            self._d.popitem(last=False)
        return False
