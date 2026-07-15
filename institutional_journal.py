"""Redundant FII/DII institutional journal storage.

V50.8.5 goals
-------------
* Preserve at least 30 trading days (default 60) across browser sessions.
* Mirror every save to CSV + JSON using atomic writes.
* Merge legacy/current/session copies by trade date instead of replacing files.
* Never treat a missing day as zero institutional flow.
* Keep this journal as evidence only; it has no execution authority.

Streamlit Cloud note
--------------------
The mirrors survive browser reconnects and ordinary app reruns while the same
app filesystem exists. A complete app redeploy can replace the filesystem, so
users should also keep the downloadable CSV backup or configure an external
store in a future version.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
from typing import Any, Iterable, Mapping, MutableMapping, Optional

import pandas as pd

try:
    import fcntl  # type: ignore
except Exception:  # pragma: no cover
    fcntl = None


JOURNAL_COLUMNS = [
    "Date",
    "FII Cash Cr",
    "DII Cash Cr",
    "FII Index Futures Contracts",
    "FII Long %",
    "FII Short %",
    "FII Index Futures Bias",
    "FII Options Bias",
    "Source",
    "Saved At",
    "Revision Status",
    "Notes",
]

NUMERIC_COLUMNS = {
    "FII Cash Cr",
    "DII Cash Cr",
    "FII Index Futures Contracts",
    "FII Long %",
    "FII Short %",
}

PRIMARY_CSV = Path(os.environ.get("NIFTY_FII_DII_STORE", "data/fii_dii_journal.csv"))
RUNTIME_CSV = Path(os.environ.get("NIFTY_FII_DII_RUNTIME_CSV", ".runtime_state/fii_dii_journal.csv"))
RUNTIME_JSON = Path(os.environ.get("NIFTY_FII_DII_RUNTIME_JSON", ".runtime_state/fii_dii_journal.json"))
LOCK_PATH = Path(os.environ.get("NIFTY_FII_DII_LOCK", ".runtime_state/fii_dii_journal.lock"))
SESSION_KEY = "v5085_fii_dii_journal_records"
DEFAULT_MAX_ROWS = 60
_THREAD_LOCK = threading.RLock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    return str(value).strip().lower() in {"", "nan", "none", "nat"}


def _parse_saved_at(value: Any) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _normalise_frame(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        df = value.copy()
    elif isinstance(value, list):
        df = pd.DataFrame(value)
    elif isinstance(value, Mapping):
        rows = value.get("records", value.get("rows", []))
        df = pd.DataFrame(rows if isinstance(rows, list) else [])
    else:
        df = pd.DataFrame()

    for col in JOURNAL_COLUMNS:
        if col not in df.columns:
            df[col] = float("nan") if col in NUMERIC_COLUMNS else ""

    if df.empty:
        return pd.DataFrame(columns=JOURNAL_COLUMNS)

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
    df = df.dropna(subset=["Date"])
    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in JOURNAL_COLUMNS:
        if col not in NUMERIC_COLUMNS and col != "Date":
            df[col] = df[col].fillna("").astype(str)
    return df[JOURNAL_COLUMNS]


def _row_completeness(row: Mapping[str, Any]) -> tuple[int, float]:
    present = 0
    for col in JOURNAL_COLUMNS:
        if col == "Date":
            continue
        if col in NUMERIC_COLUMNS:
            value = row.get(col)
            if value is not None and not (isinstance(value, float) and pd.isna(value)):
                present += 1
        elif not _is_missing(row.get(col)):
            present += 1
    return present, _parse_saved_at(row.get("Saved At"))


def _merge_rows(old: Mapping[str, Any], new: Mapping[str, Any]) -> dict[str, Any]:
    old_d, new_d = dict(old), dict(new)
    # Latest timestamp wins; completeness breaks ties. Blank values never erase
    # an existing field during mirror/session reconciliation.
    old_score = (_parse_saved_at(old_d.get("Saved At")), _row_completeness(old_d)[0])
    new_score = (_parse_saved_at(new_d.get("Saved At")), _row_completeness(new_d)[0])
    preferred, other = (new_d, old_d) if new_score >= old_score else (old_d, new_d)
    result = deepcopy(preferred)
    for col in JOURNAL_COLUMNS:
        if col == "Date":
            continue
        if _is_missing(result.get(col)) and not _is_missing(other.get(col)):
            result[col] = other.get(col)
    result["Date"] = preferred.get("Date") or other.get("Date")
    return result


def merge_journals(values: Iterable[Any], *, max_rows: int = DEFAULT_MAX_ROWS) -> pd.DataFrame:
    by_date: dict[str, dict[str, Any]] = {}
    for value in values:
        df = _normalise_frame(value)
        for row in df.to_dict("records"):
            key = str(row.get("Date"))
            if key in by_date:
                by_date[key] = _merge_rows(by_date[key], row)
            else:
                by_date[key] = dict(row)
    merged = _normalise_frame(list(by_date.values()))
    if merged.empty:
        return merged
    merged = merged.sort_values("Date").tail(max(30, int(max_rows)))
    return merged.reset_index(drop=True)


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path) if path.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _read_json(path: Path) -> Any:
    try:
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _lock():
    class _LockCtx:
        def __enter__(self):
            LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
            _THREAD_LOCK.acquire()
            self.handle = LOCK_PATH.open("a+", encoding="utf-8")
            if fcntl is not None:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
            return self

        def __exit__(self, exc_type, exc, tb):
            try:
                if fcntl is not None:
                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
                self.handle.close()
            finally:
                _THREAD_LOCK.release()
    return _LockCtx()


def load_institutional_journal(
    session_state: Optional[MutableMapping[str, Any]] = None,
    *,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> pd.DataFrame:
    """Load and heal the journal from all known copies."""
    session_rows = []
    if session_state is not None:
        try:
            session_rows = session_state.get(SESSION_KEY, [])
        except Exception:
            session_rows = []
    legacy_candidates = [
        PRIMARY_CSV,
        RUNTIME_CSV,
        Path("fii_dii_journal.csv"),
        Path("data/fii_dii_journal_backup.csv"),
    ]
    sources: list[Any] = [_read_csv(path) for path in legacy_candidates]
    sources.extend([_read_json(RUNTIME_JSON), session_rows])
    merged = merge_journals(sources, max_rows=max_rows)
    if session_state is not None:
        try:
            session_state[SESSION_KEY] = serialise_records(merged)
        except Exception:
            pass
    # Self-heal mirrors only when there is at least one valid row.
    if not merged.empty:
        save_institutional_journal(merged, session_state=session_state, max_rows=max_rows)
    return merged


def serialise_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    norm = _normalise_frame(df)
    records: list[dict[str, Any]] = []
    for row in norm.to_dict("records"):
        out = dict(row)
        out["Date"] = str(out.get("Date", ""))
        for col in NUMERIC_COLUMNS:
            value = out.get(col)
            out[col] = None if value is None or (isinstance(value, float) and pd.isna(value)) else float(value)
        records.append(out)
    return records


def save_institutional_journal(
    df: pd.DataFrame,
    session_state: Optional[MutableMapping[str, Any]] = None,
    *,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> bool:
    """Monotonically merge and mirror the journal.

    Existing on-disk rows are read under the same lock so a shorter browser
    session cannot replace a longer journal.
    """
    try:
        with _lock():
            existing = merge_journals(
                [_read_csv(PRIMARY_CSV), _read_csv(RUNTIME_CSV), _read_json(RUNTIME_JSON)],
                max_rows=max_rows,
            )
            merged = merge_journals([existing, df], max_rows=max_rows)
            records = serialise_records(merged)
            csv_df = merged.copy()
            if not csv_df.empty:
                csv_df["Date"] = csv_df["Date"].astype(str)
            _atomic_text(PRIMARY_CSV, csv_df.to_csv(index=False))
            _atomic_text(RUNTIME_CSV, csv_df.to_csv(index=False))
            _atomic_text(
                RUNTIME_JSON,
                json.dumps(
                    {"schema_version": 2, "updated_at": _now_iso(), "records": records},
                    ensure_ascii=True,
                    separators=(",", ":"),
                    default=str,
                ),
            )
            if session_state is not None:
                try:
                    session_state[SESSION_KEY] = records
                except Exception:
                    pass
        return True
    except Exception:
        return False


def prepare_upsert_row(row: Mapping[str, Any], *, source: str = "MANUAL") -> dict[str, Any]:
    out = {col: row.get(col, None if col in NUMERIC_COLUMNS else "") for col in JOURNAL_COLUMNS}
    out["Date"] = row.get("Date")
    out["Source"] = str(row.get("Source") or source)
    out["Saved At"] = str(row.get("Saved At") or _now_iso())
    out["Revision Status"] = str(row.get("Revision Status") or "CURRENT")
    return out


def journal_stats(df: pd.DataFrame, *, lookback: int = DEFAULT_MAX_ROWS) -> dict[str, Any]:
    d = _normalise_frame(df)
    if d.empty:
        return {
            "rows": 0,
            "fii_5": 0.0, "dii_5": 0.0,
            "fii_10": 0.0, "dii_10": 0.0,
            "fii_15": 0.0, "dii_15": 0.0,
            "fii_30": 0.0, "dii_30": 0.0,
            "latest_date": "", "missing_latest": True,
        }
    d = d.sort_values("Date").tail(max(30, int(lookback)))
    for col in ("FII Cash Cr", "DII Cash Cr"):
        d[col] = pd.to_numeric(d[col], errors="coerce")
    def total(col: str, n: int) -> float:
        return float(d.tail(n)[col].dropna().sum())
    latest = d.iloc[-1]
    return {
        "rows": len(d),
        "fii_5": total("FII Cash Cr", 5), "dii_5": total("DII Cash Cr", 5),
        "fii_10": total("FII Cash Cr", 10), "dii_10": total("DII Cash Cr", 10),
        "fii_15": total("FII Cash Cr", 15), "dii_15": total("DII Cash Cr", 15),
        "fii_30": total("FII Cash Cr", 30), "dii_30": total("DII Cash Cr", 30),
        "latest_date": str(latest.get("Date", "")),
        "latest_source": str(latest.get("Source", "")),
        "missing_latest": False,
    }
