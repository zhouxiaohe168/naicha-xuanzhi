import os
import json
import tempfile
import logging

logger = logging.getLogger("TitanUtils")


def atomic_json_save(filepath, data, ensure_ascii=False, indent=2):
    dirpath = os.path.dirname(filepath)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    try:
        fd, tmp_path = tempfile.mkstemp(dir=dirpath, suffix=".tmp", prefix=".titan_")
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)
            os.replace(tmp_path, filepath)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except Exception as e:
        logger.warning(f"Atomic save failed for {filepath}, falling back to direct write: {e}")
        with open(filepath, 'w') as f:
            json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)
