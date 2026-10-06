"""Explicit UTC calendar ranges shared by administrative reports."""
from datetime import datetime, time, timedelta

from fastapi import HTTPException


def date_range(current, days=30, start=None, end=None):
    if (start is None) != (end is None):
        raise HTTPException(422, 'Bitte Anfang und Ende des Zeitraums angeben / supply both dates')
    if start is not None:
        try:
            first = datetime.strptime(start, '%Y-%m-%d').date()
            last = datetime.strptime(end, '%Y-%m-%d').date()
            if first.isoformat() != start or last.isoformat() != end:
                raise ValueError('Date format')
        except (TypeError, ValueError):
            raise HTTPException(422, 'Datum prüfen / check date') from None
    else:
        last = current.date()
        first = last - timedelta(days=days - 1)
    length = (last - first).days + 1
    if length < 1 or length > 366:
        raise HTTPException(422, 'Zeitraum muss zwischen 1 und 366 Tagen liegen / invalid range')
    try:
        exclusive_end = datetime.combine(last + timedelta(days=1), time.min)
    except OverflowError:
        raise HTTPException(422, 'Datum außerhalb des unterstützten Bereichs / date out of range') from None
    return datetime.combine(first, time.min), exclusive_end, {
        'start': first.isoformat(), 'end': last.isoformat(), 'days': length, 'timezone': 'UTC',
    }
