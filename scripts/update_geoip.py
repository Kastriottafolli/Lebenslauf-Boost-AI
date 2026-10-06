"""Install DB-IP Country Lite locally; no visitor address leaves the app.

Requires attribution on result pages (CC BY 4.0): https://db-ip.com/db/lite.php
Run monthly inside the app container. An unsuccessful download leaves the
previous database intact. This file contains no account or access credentials.
"""

import argparse
import gzip
import hashlib
import io
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import httpx
import maxminddb


def install(destination, month=None):
    month = month or datetime.now(UTC).strftime('%Y-%m')
    parsed = datetime.strptime(month, '%Y-%m')
    if parsed.strftime('%Y-%m') != month:
        raise ValueError('Month must be YYYY-MM')
    url = f'https://download.db-ip.com/free/dbip-country-lite-{month}.mmdb.gz'
    data = bytearray()
    with httpx.stream('GET', url, timeout=60, follow_redirects=False, headers={
        'User-Agent': 'TafolliBoost/1.0 (https://tafolliboost.com; info@tafolli.net)',
    }) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            data.extend(chunk)
            if len(data) > 20 * 1024 * 1024:
                raise ValueError('Compressed database too large')
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
        decoded = stream.read(50 * 1024 * 1024 + 1)
    if len(decoded) > 50 * 1024 * 1024:
        raise ValueError('Country database too large')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.mmdb', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(decoded)
        with maxminddb.open_database(str(temporary)) as reader:
            if reader.metadata().database_type != 'DBIP-Country-Lite' or reader.get('8.8.8.8')['country']['iso_code'] != 'US':
                raise ValueError('Invalid country database')
        temporary.chmod(0o644)
        os.replace(temporary, destination)
        metadata = {'source': url, 'month': month, 'license': 'CC BY 4.0',
                    'attribution': 'IP Geolocation by DB-IP', 'link': 'https://db-ip.com',
                    'sha256': hashlib.sha256(decoded).hexdigest()}
        destination.with_suffix('.license.json').write_text(json.dumps(metadata, indent=2)+'\n')
        print('DB-IP Country Lite installed:', month, len(decoded), 'bytes')
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--month')
    args = parser.parse_args()
    install(args.destination, args.month)
