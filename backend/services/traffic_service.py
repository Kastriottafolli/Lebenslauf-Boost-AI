"""First-party, consent-only traffic measurement using local country databases.

Raw client addresses are transient inputs to local lookup and abuse prevention.
No network lookup is ever made. Durations are bounded observations, not proof
that somebody read a page; reloads and tabs are separate visits.
"""

import bisect
import csv
import hashlib
import ipaddress
import secrets
import threading
import time
from collections import OrderedDict, deque
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError

from backend.analytics_models import TrafficDaily, TrafficVisit
from backend.config import get_settings

PAGES = frozenset({
    "home", "app", "account", "pricing", "imprint", "privacy", "terms", "withdrawal",
    "resume", "cover-letter",
})
MAX_VISIT_SECONDS = 86400
HEARTBEAT_SECONDS = 15
MAX_PULSE_SECONDS = 30
DETAIL_DAYS = 30
MASK_DAYS = 7
AGGREGATE_DAYS = 90

# ISO 3166-1 alpha-2. No synthetic "ZZ" country is manufactured for unknown IPs.
COUNTRIES = frozenset("AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW".split())

_rate_lock = threading.Lock()
_rate_secret = secrets.token_bytes(32)
_rate_buckets = OrderedDict()
_MAX_RATE_BUCKETS = 4096
_country_lock = threading.Lock()
_country_cache = None


def now():
    return datetime.now(UTC).replace(tzinfo=None)


def _utc_naive(value):
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


def _token_hash(token):
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _address(raw):
    try:
        address = ipaddress.ip_address(raw)
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            return address.ipv4_mapped
        return address
    except (ValueError, TypeError):
        return None


def mask_ip(raw):
    address = _address(raw)
    if address is None:
        return None
    prefix = 24 if address.version == 4 else 48
    return str(ipaddress.ip_network(f"{address}/{prefix}", strict=False))


def device_from_user_agent(user_agent):
    # Inspect only a bounded prefix and discard it immediately after classification.
    ua = (user_agent or "")[:512].lower()
    if any(word in ua for word in ("bot", "spider", "crawler", "headless", "curl/", "wget/")):
        return "bot"
    if "ipad" in ua or "tablet" in ua or ("android" in ua and "mobile" not in ua):
        return "tablet"
    if any(word in ua for word in ("mobi", "iphone", "ipod", "windows phone")):
        return "mobile"
    return "desktop"


def limit_request(client_ip, category, token=None):
    """Bounded in-memory keyed digests, never persisted or joined to visit data.

    Start is limited per network peer; pulses have both peer and capability
    budgets. All forwarding headers are intentionally irrelevant here.
    """
    current = time.monotonic()
    peer = str(_address(client_ip) or "unknown").encode("ascii")
    peer_key = hashlib.blake2b(peer, key=_rate_secret, digest_size=16).digest()
    keys = [(peer_key, category, 20 if category == "start" else 120)]
    if token:
        token_key = hashlib.blake2b(token.encode("ascii"), key=_rate_secret, digest_size=16).digest()
        keys.append((token_key, "token", 12))
    with _rate_lock:
        for key, bucket in list(_rate_buckets.items()):
            if not bucket or bucket[-1] <= current - 60:
                _rate_buckets.pop(key, None)
        for key, kind, limit in keys:
            bucket = _rate_buckets.get((key, kind), deque())
            while bucket and bucket[0] <= current - 60:
                bucket.popleft()
            if len(bucket) >= limit:
                raise HTTPException(429, "Too many traffic requests", headers={"Retry-After": "60"})
        for key, kind, _limit in keys:
            bucket = _rate_buckets.setdefault((key, kind), deque())
            bucket.append(current)
            _rate_buckets.move_to_end((key, kind))
        while len(_rate_buckets) > _MAX_RATE_BUCKETS:
            _rate_buckets.popitem(last=False)


class _CountryCSV:
    """IP2Location LITE DB1 numeric ranges: start, end, ISO2, country name.

    IPv4 DB1 CSV is supported. For IPv6 use a local .mmdb or IP2Location .bin.
    The range arrays are read once per file revision; no names are retained.
    """

    def __init__(self, path):
        ranges = []
        with path.open(newline="", encoding="utf-8-sig") as stream:
            for row in csv.reader(stream):
                if len(row) < 3:
                    continue
                start, end = int(row[0]), int(row[1])
                code = row[2].strip().upper()
                if not (0 <= start <= end <= 0xFFFFFFFF):
                    raise ValueError("Use an IPv4 DB1 CSV or an IPv6-capable binary database")
                ranges.append((start, end, code if code in COUNTRIES else ""))
        ranges.sort()
        self.starts = [row[0] for row in ranges]
        self.ends = [row[1] for row in ranges]
        self.codes = [row[2] for row in ranges]

    def lookup(self, address):
        if address.version != 4:
            return None
        numeric = int(address)
        index = bisect.bisect_right(self.starts, numeric) - 1
        return self.codes[index] if index >= 0 and numeric <= self.ends[index] else None


def _open_country_database(path):
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _CountryCSV(path)
    if suffix == ".mmdb":
        import maxminddb

        return maxminddb.open_database(str(path))
    if suffix == ".bin":
        import IP2Location

        return IP2Location.IP2Location(str(path))
    raise ValueError("Local country database must be .mmdb, .bin or IP2Location DB1 .csv")


def country_for_ip(raw):
    """Use only a configured local file. Errors and private IPs remain unknown."""
    global _country_cache
    address = _address(raw)
    if address is None or not address.is_global:
        return None
    configured = getattr(get_settings(), "traffic_geoip_db_path", "")
    if not configured:
        return None
    try:
        path = Path(configured)
        stamp = (str(path.resolve()), path.stat().st_mtime_ns, path.stat().st_size)
        with _country_lock:
            if _country_cache is None or _country_cache[0] != stamp:
                reader = _open_country_database(path)
                old = _country_cache
                _country_cache = (stamp, reader)
                if old and hasattr(old[1], "close"):
                    old[1].close()
            reader = _country_cache[1]
            if isinstance(reader, _CountryCSV):
                code = reader.lookup(address)
            elif path.suffix.lower() == ".mmdb":
                record = reader.get(str(address))
                code = record.get("country", {}).get("iso_code") if isinstance(record, dict) else None
            else:
                code = reader.get_country_short(str(address))
        return code.upper() if isinstance(code, str) and code.upper() in COUNTRIES else None
    except Exception:
        # Never log the lookup argument, database record or exception body.
        return None


def country_status():
    """Admin-safe operational status without publishing the server file path."""
    configured = getattr(get_settings(), "traffic_geoip_db_path", "")
    available = False
    if configured:
        try:
            path = Path(configured)
            reader = _open_country_database(path)
            available = True
            if hasattr(reader, "close"):
                reader.close()
        except Exception:
            pass
    return {"configured": bool(configured), "available": available, "source": "local_country_database" if available else "unknown"}


def _adjust_daily(db, visit, visits=0, active=0, elapsed=0):
    identity = {
        "day": visit.started_at.date().isoformat(), "page": visit.page,
        "device": visit.device, "country_code": visit.country_code,
    }
    where = [getattr(TrafficDaily, key) == value for key, value in identity.items()]
    changes = {
        TrafficDaily.visits: TrafficDaily.visits + visits,
        TrafficDaily.active_seconds: TrafficDaily.active_seconds + active,
        TrafficDaily.elapsed_seconds: TrafficDaily.elapsed_seconds + elapsed,
    }
    if not db.execute(update(TrafficDaily).where(*where).values(changes)).rowcount:
        try:
            with db.begin_nested():
                db.add(TrafficDaily(**identity, visits=visits, active_seconds=active, elapsed_seconds=elapsed))
                db.flush()
        except IntegrityError:
            db.execute(update(TrafficDaily).where(*where).values(changes))


def start(db, *, page, analytics_consent, client_ip, user_agent="", country_lookup=None, current=None):
    if analytics_consent is not True:
        raise HTTPException(400, "Analytics consent required")
    if page not in PAGES:
        raise HTTPException(400, "Unknown public page label")
    current = _utc_naive(current) if current else now()
    token = secrets.token_urlsafe(32)
    lookup = country_lookup or country_for_ip
    address = _address(client_ip)
    country = None
    if address is not None and address.is_global:
        try:
            country = lookup(str(address))
        except Exception:
            pass
    country = country.upper() if isinstance(country, str) and country.upper() in COUNTRIES else ""
    visit = TrafficVisit(
        token_hash=_token_hash(token), token_expires_at=current + timedelta(seconds=MAX_VISIT_SECONDS),
        started_at=current, last_seen_at=current, page=page,
        device=device_from_user_agent(user_agent), country_code=country,
        ip_masked=mask_ip(client_ip) if getattr(get_settings(), "traffic_store_masked_ip", False) else None,
        active_seconds=0, elapsed_seconds=0, client_active_seconds=0,
    )
    db.add(visit)
    _adjust_daily(db, visit, visits=1)
    db.commit()
    return {"ok": True, "visit_token": token, "heartbeat_interval_seconds": HEARTBEAT_SECONDS, "expires_in_seconds": MAX_VISIT_SECONDS}


def _visit_for_token(db, token, current):
    visit = db.query(TrafficVisit).filter_by(token_hash=_token_hash(token)).first()
    if visit is None or visit.token_expires_at is None or visit.token_expires_at <= current:
        raise HTTPException(404, "Traffic visit unavailable")
    return visit


def pulse(db, *, token, active_seconds=None, end=False, withdraw=False, current=None):
    current = _utc_naive(current) if current else now()
    # A compare-and-swap fence makes racing/replayed cumulative heartbeats harmless.
    for _attempt in range(3):
        visit = _visit_for_token(db, token, current)
        if withdraw:
            deleted = db.execute(delete(TrafficVisit).where(
                TrafficVisit.id == visit.id, TrafficVisit.revision == visit.revision,
            )).rowcount
            if not deleted:
                db.rollback()
                continue
            _adjust_daily(db, visit, visits=-1, active=-visit.active_seconds, elapsed=-visit.elapsed_seconds)
            db.commit()
            return {"ok": True, "withdrawn": True}
        if visit.ended_at is not None:
            return {"ok": True, "active_seconds": visit.active_seconds, "elapsed_seconds": visit.elapsed_seconds, "ended": True}
        reported = visit.client_active_seconds if active_seconds is None else active_seconds
        advanced = reported > visit.client_active_seconds
        if not advanced and not end:
            return {"ok": True, "active_seconds": visit.active_seconds, "elapsed_seconds": visit.elapsed_seconds, "ended": False}
        observed = max(0, min(MAX_VISIT_SECONDS, int((current - visit.started_at).total_seconds())))
        since_pulse = max(0, int((current - visit.last_seen_at).total_seconds()))
        increment = min(max(0, reported - visit.client_active_seconds), MAX_PULSE_SECONDS, since_pulse, max(0, observed - visit.active_seconds))
        elapsed = max(visit.elapsed_seconds, observed)
        values = {
            "client_active_seconds": max(visit.client_active_seconds, reported),
            "active_seconds": visit.active_seconds + increment,
            "elapsed_seconds": elapsed,
            "last_seen_at": max(visit.last_seen_at, current),
            "revision": visit.revision + 1,
        }
        if end:
            values["ended_at"] = current
        changed = db.execute(update(TrafficVisit).where(
            TrafficVisit.id == visit.id, TrafficVisit.revision == visit.revision,
        ).values(**values), execution_options={"synchronize_session": False}).rowcount
        if not changed:
            db.rollback()
            continue
        _adjust_daily(db, visit, active=increment, elapsed=elapsed - visit.elapsed_seconds)
        db.commit()
        return {"ok": True, "active_seconds": values["active_seconds"], "elapsed_seconds": elapsed, "ended": end}
    db.rollback()
    raise HTTPException(409, "Concurrent traffic update; retry later")


def cleanup(db, current=None):
    """Join the caller's transaction; retention is additive to existing cleanup."""
    current = _utc_naive(current) if current else now()
    cleared = db.query(TrafficVisit).filter(
        TrafficVisit.started_at < current - timedelta(days=MASK_DAYS), TrafficVisit.ip_masked.is_not(None),
    ).update({"ip_masked": None}, synchronize_session=False)
    db.query(TrafficVisit).filter(TrafficVisit.token_expires_at <= current).update(
        {"token_hash": None, "token_expires_at": None}, synchronize_session=False,
    )
    removed = db.query(TrafficVisit).filter(TrafficVisit.started_at < current - timedelta(days=DETAIL_DAYS)).delete(synchronize_session=False)
    aggregates = db.query(TrafficDaily).filter(TrafficDaily.day < (current - timedelta(days=AGGREGATE_DAYS)).date().isoformat()).delete(synchronize_session=False)
    return {"masked_ips_cleared": cleared, "visits_deleted": removed, "aggregate_rows_deleted": aggregates}


def _counts(visits=0, active=0, elapsed=0):
    return {"visits": visits, "active_seconds": active, "elapsed_seconds": elapsed}


def summarize(db, start_utc, end_utc, *, page=None, limit=25, offset=0, current=None):
    """UTC daily aggregates for [start,end), plus recent disposable visit detail."""
    current = _utc_naive(current) if current else now()
    start_utc, end_utc = _utc_naive(start_utc), _utc_naive(end_utc)
    if start_utc >= end_utc or end_utc - start_utc > timedelta(days=AGGREGATE_DAYS):
        raise ValueError("Choose a nonempty period of at most 90 days")
    if page is not None and page not in PAGES:
        raise ValueError("Unknown public page label")
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError("Invalid traffic pagination")
    first_day = max(start_utc.date().isoformat(), (current - timedelta(days=AGGREGATE_DAYS)).date().isoformat())
    last_day = (end_utc - timedelta(microseconds=1)).date().isoformat()
    query = db.query(TrafficDaily).filter(TrafficDaily.day >= first_day, TrafficDaily.day <= last_day, TrafficDaily.visits > 0)
    details = db.query(TrafficVisit).filter(
        TrafficVisit.started_at >= max(start_utc, current - timedelta(days=DETAIL_DAYS)), TrafficVisit.started_at < end_utc,
    )
    if page:
        query, details = query.filter_by(page=page), details.filter_by(page=page)
    totals, daily, devices, countries, pages = _counts(), {}, {}, {}, {}
    day = start_utc.date()
    while day.isoformat() <= last_day:
        daily[day.isoformat()] = _counts()
        day += timedelta(days=1)
    for row in query.all():
        for values in (totals, daily.setdefault(row.day, _counts()), devices.setdefault(row.device, _counts()), countries.setdefault(row.country_code, _counts()), pages.setdefault(row.page, _counts())):
            values["visits"] += row.visits
            values["active_seconds"] += row.active_seconds
            values["elapsed_seconds"] += row.elapsed_seconds
    totals["avg_active_seconds"] = round(totals["active_seconds"] / totals["visits"], 1) if totals["visits"] else 0
    totals["avg_elapsed_seconds"] = round(totals["elapsed_seconds"] / totals["visits"], 1) if totals["visits"] else 0
    total = details.count()
    items = details.order_by(TrafficVisit.started_at.desc(), TrafficVisit.id).offset(offset).limit(limit).all()
    return {
        "start_utc": start_utc.replace(tzinfo=UTC).isoformat(), "end_utc": end_utc.replace(tzinfo=UTC).isoformat(),
        "totals": totals,
        "daily": [{"day": day, **values} for day, values in sorted(daily.items())],
        "devices": [{"device": key, **values} for key, values in sorted(devices.items())],
        "countries": [{"country": key or None, **values} for key, values in sorted(countries.items())],
        "pages": [{"page": key, **values} for key, values in sorted(pages.items())],
        "total": total, "limit": limit, "offset": offset, "items": [{
            "id": row.id, "started_at": row.started_at.replace(tzinfo=UTC).isoformat(),
            "last_seen_at": row.last_seen_at.replace(tzinfo=UTC).isoformat(),
            "ended_at": row.ended_at.replace(tzinfo=UTC).isoformat() if row.ended_at else None,
            "page": row.page, "device": row.device, "country": row.country_code or None,
            "ip_masked": row.ip_masked if row.started_at >= current - timedelta(days=MASK_DAYS) else None,
            "active_seconds": row.active_seconds, "elapsed_seconds": row.elapsed_seconds,
        } for row in items],
        "country_lookup": country_status(),
        "retention": {"masked_ip_days": MASK_DAYS, "visit_days": DETAIL_DAYS, "aggregate_days": AGGREGATE_DAYS},
        "measurement": "Consent-based visits; tabs, reloads and bots may count separately. Active time is bounded visible-page time reported by the browser. Elapsed time is observed visit duration, not engagement. Country is an approximate local IP lookup; unknown remains unknown. Daily duration totals are attributed to the UTC visit-start day.",
    }
