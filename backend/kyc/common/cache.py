"""Lightweight database cache backend."""

import base64
import pickle
import time
from datetime import UTC, datetime

from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.core.cache.backends.db import BaseDatabaseCache
from django.db import DatabaseError, connections, router, transaction
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now as tz_now

CLEANUP_INTERVAL = 300

_last_cleanup = 0.0


class LightweightDatabaseCache(BaseDatabaseCache):
    pickle_protocol = pickle.HIGHEST_PROTOCOL

    def _connection(self, write=False):
        alias = (
            router.db_for_write(self.cache_model_class)
            if write
            else router.db_for_read(self.cache_model_class)
        )
        return connections[alias]

    @staticmethod
    def _to_datetime(value):
        """Normalise a raw `expires` column value to an aware datetime."""
        if isinstance(value, datetime):
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value
        parsed = parse_datetime(str(value))
        if parsed is None:
            raise ValueError(f"Unparseable cache expiry: {value!r}")
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed

    def _encode(self, value):
        return base64.b64encode(pickle.dumps(value, self.pickle_protocol)).decode("latin1")

    def _decode(self, raw):
        return pickle.loads(base64.b64decode(raw.encode()))

    def _expiry(self, timeout):
        if timeout is None:
            exp = datetime.max
        else:
            tz = UTC if settings.USE_TZ else None
            exp = datetime.fromtimestamp(timeout, tz=tz)
        return exp.replace(microsecond=0)

    def _maybe_cleanup(self, cursor, quote_name, table, connection):
        global _last_cleanup
        now = time.monotonic()
        if now - _last_cleanup < CLEANUP_INTERVAL:
            return
        _last_cleanup = now
        cursor.execute(
            f"DELETE FROM {table} WHERE {quote_name('expires')} < %s",
            [connection.ops.adapt_datetimefield_value(tz_now())],
        )

    def get(self, key, default=None, version=None):
        key = self.make_and_validate_key(key, version=version)
        connection = self._connection()
        quote_name = connection.ops.quote_name
        table = quote_name(self._table)

        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {quote_name('value')}, {quote_name('expires')} "
                f"FROM {table} WHERE {quote_name('cache_key')} = %s",
                [key],
            )
            row = cursor.fetchone()

        if row is None:
            return default
        value, expires = row
        if self._to_datetime(expires) < tz_now():
            return default
        return self._decode(value)

    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        key = self.make_and_validate_key(key, version=version)
        timeout = self.get_backend_timeout(timeout)
        connection = self._connection(write=True)
        quote_name = connection.ops.quote_name
        table = quote_name(self._table)
        exp = connection.ops.adapt_datetimefield_value(self._expiry(timeout))
        encoded = self._encode(value)
        cols = (quote_name("cache_key"), quote_name("value"), quote_name("expires"))

        try:
            with connection.cursor() as cursor:
                self._maybe_cleanup(cursor, quote_name, table, connection)
                cursor.execute(
                    f"INSERT INTO {table} ({cols[0]}, {cols[1]}, {cols[2]}) "
                    f"VALUES (%s, %s, %s) ON CONFLICT ({cols[0]}) DO UPDATE SET "
                    f"{cols[1]} = EXCLUDED.{cols[1]}, {cols[2]} = EXCLUDED.{cols[2]}",
                    [key, encoded, exp],
                )
        except DatabaseError:
            return False
        return True

    def add(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        """Set ``key`` only if absent (or expired); True if stored."""
        key = self.make_and_validate_key(key, version=version)
        timeout = self.get_backend_timeout(timeout)
        connection = self._connection(write=True)
        quote_name = connection.ops.quote_name
        table = quote_name(self._table)
        exp = connection.ops.adapt_datetimefield_value(self._expiry(timeout))
        now = connection.ops.adapt_datetimefield_value(tz_now())
        encoded = self._encode(value)
        cols = (quote_name("cache_key"), quote_name("value"), quote_name("expires"))

        try:
            with connection.cursor() as cursor:
                self._maybe_cleanup(cursor, quote_name, table, connection)
                cursor.execute(
                    f"INSERT INTO {table} ({cols[0]}, {cols[1]}, {cols[2]}) "
                    f"VALUES (%s, %s, %s) ON CONFLICT ({cols[0]}) DO UPDATE SET "
                    f"{cols[1]} = EXCLUDED.{cols[1]}, {cols[2]} = EXCLUDED.{cols[2]} "
                    f"WHERE {table}.{quote_name('expires')} < %s",
                    [key, encoded, exp, now],
                )
                inserted = bool(cursor.rowcount)
        except DatabaseError:
            return False
        return inserted

    def touch(self, key, timeout=DEFAULT_TIMEOUT, version=None):
        """Extend ``key``'s expiry; True if the key existed."""
        key = self.make_and_validate_key(key, version=version)
        timeout = self.get_backend_timeout(timeout)
        connection = self._connection(write=True)
        quote_name = connection.ops.quote_name
        table = quote_name(self._table)
        exp = connection.ops.adapt_datetimefield_value(self._expiry(timeout))

        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {table} SET {quote_name('expires')} = %s "
                f"WHERE {quote_name('cache_key')} = %s",
                [exp, key],
            )
            return bool(cursor.rowcount)

    def incr(self, key, delta=1, version=None):
        """Atomically increment an integer-valued key; return the new value."""
        key = self.make_and_validate_key(key, version=version)
        connection = self._connection(write=True)
        quote_name = connection.ops.quote_name
        table = quote_name(self._table)

        with transaction.atomic(using=connection.alias):
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT {quote_name('value')} FROM {table} "
                    f"WHERE {quote_name('cache_key')} = %s "
                    f"AND {quote_name('expires')} >= %s FOR UPDATE",
                    [key, connection.ops.adapt_datetimefield_value(tz_now())],
                )
                row = cursor.fetchone()
                if row is None:
                    raise ValueError(f"Key '{key}' not found")
                current = self._decode(row[0])
                if isinstance(current, bool) or not isinstance(current, int):
                    raise ValueError(f"Key '{key}' is not an integer")
                new_value = current + delta
                cursor.execute(
                    f"UPDATE {table} SET {quote_name('value')} = %s "
                    f"WHERE {quote_name('cache_key')} = %s",
                    [self._encode(new_value), key],
                )
        return new_value

    def delete(self, key, version=None):
        key = self.make_and_validate_key(key, version=version)
        connection = self._connection(write=True)
        quote_name = connection.ops.quote_name
        table = quote_name(self._table)
        with connection.cursor() as cursor:
            cursor.execute(
                f"DELETE FROM {table} WHERE {quote_name('cache_key')} = %s",
                [key],
            )
            return bool(cursor.rowcount)

    def clear(self):
        connection = self._connection(write=True)
        quote_name = connection.ops.quote_name
        with connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {quote_name(self._table)}")
