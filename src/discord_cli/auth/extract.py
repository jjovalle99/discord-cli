import shutil
import tempfile
from collections.abc import Iterable
from pathlib import Path

from ccl_chromium_reader.ccl_chromium_localstorage import LocalStoreDb


def parse_token_from_records(records: Iterable[tuple[str, str]]) -> str | None:
    for key, value in records:
        if key == "token":
            return value.strip('"')
    return None


def extract_token_from_leveldb(leveldb_dir: Path) -> str | None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_db = Path(tmp) / "leveldb"
        shutil.copytree(leveldb_dir, tmp_db)

        db = LocalStoreDb(tmp_db)
        try:
            records = [
                (record.script_key, record.value)
                for record in db.iter_all_records()
                if record.is_live
            ]
        finally:
            db.close()

    return parse_token_from_records(records)
