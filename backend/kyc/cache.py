"""Lightweight database cache backend.

Drop-in replacement for ``django.core.cache.backends.db.DatabaseCache`` that
removes its two main sources of overhead:

* The stock backend runs ``SELECT COUNT(*)`` over the whole cache table on
  EVERY write (to enforce ``MAX_ENTRIES`` culling) — a full scan that gets
  slower as the table grows — plus a SELECT and an INSERT/UPDATE. This
  backend does a single indexed upsert instead.
* Expired rows are only removed lazily on reads there, so the table grows
  without bound. Here a cheap indexed ``DELETE ... WHERE expires < now``
  runs at most once per process every ``CLEANUP_INTERVAL`` seconds.

Only the hot methods (``get``/``set``/``delete``/``clear``) are overridden;
everything else (``get_many``, ``incr``, ``has_key``, ...) is inherited from
``BaseCache`` and built on top of these. The table schema is the one created
by ``manage.py createcachetable`` (primary key on ``cache_key``, index on
``expires``), so switching backends requires no migration.
"""

import base64
import pickle
import time
from datetime import UTC, datetime

from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.core.cache.backends.db import BaseDatabaseCache
from django.db import DatabaseError, connections, router
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now as tz_now

# At most one expired-row sweep per process per interval. The DELETE is
# indexed on `expires` and normally affects zero rows, so it is cheap even
# when it runs.
CLEANUP_INTERVAL = 300

_last_cleanup = 0.0


class LightweightDatabaseCache(BaseDatabaseCache):
    pickle_protocol = pickle.HIGHEST_PROTOCOL

    # -- helpers ---------------------------------------------------------

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
        if isinstance(value, datetime):  # Postgres returns datetime objects.
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value
        parsed = parse_datetime(str(value))  # SQLite returns ISO strings.
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

    # -- read path -------------------------------------------------------

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
            # Expired: leave the row for the periodic sweep rather than
            # paying a write on every miss.
            return default
        return self._decode(value)

    # -- write path ------------------------------------------------------

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
                if connection.vendor == "sqlite":
                    # Atomic upsert on the primary key.
                    cursor.execute(
                        f"INSERT OR REPLACE INTO {table} "
                        f"({cols[0]}, {cols[1]}, {cols[2]}) VALUES (%s, %s, %s)",
                        [key, encoded, exp],
                    )
                else:
                    cursor.execute(
                        f"INSERT INTO {table} ({cols[0]}, {cols[1]}, {cols[2]}) "
                        f"VALUES (%s, %s, %s) ON CONFLICT ({cols[0]}) DO UPDATE SET "
                        f"{cols[1]} = EXCLUDED.{cols[1]}, {cols[2]} = EXCLUDED.{cols[2]}",
                        [key, encoded, exp],
                    )
        except DatabaseError:
            # Match the stock backend: writes fail silently (thread safety).
            return False
        return True

    # -- delete path -----------------------------------------------------

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
