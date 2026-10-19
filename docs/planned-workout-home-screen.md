# Intervals workouts on the home screen

The schedule/Next Up response structure comes from
[the online reference](https://github.com/zoffline/zwift-offline/pull/544#issuecomment-6257306924).
[Native-client testing](https://github.com/zoffline/zwift-offline/pull/544#issuecomment-6269590334)
established that the For You response must be an object and the CDN downloader
cannot rely on a game login cookie. A subsequent
[client log](https://github.com/zoffline/zwift-offline/pull/544#issuecomment-6273631903)
identified the required ZWO `uniqueId` field.

## Behavior

- `/api/workout/schedule/list` returns every valid cycling workout synced for
  today's local date, with separate stable workout/schedule IDs.
- `/api/workout/workouts/{workoutId}` returns its summary.
- `/api/head-unit-bff/game-home` returns the reference's single `nextUp` selection.
- These API responses retain existing session/Bearer authentication. Single-player
  mode retains its selected anonymous profile.
- `/api/head-unit-bff/carousels/for-you` returns `{}` so the client can display
  scheduled workouts in For You. This is the manually verified home-screen path;
  the separate Next Up card has not been independently verified.
- The original zfiles/manifest library remains available. Home-screen GETs do not
  synchronize, change state or create extra copies.

The CDN URL is
`https://cdn.zwift.com/tp-workouts/intervalsicu/{workoutId}.zwo?token=...`.
The normal zoffline DNS redirect for `cdn.zwift.com` must point to this server.
The download needs no game cookie. Its private signed grant authorizes one
player/workout/source-file SHA-256 until the advertised local-day expiry. Missing,
modified or expired grants return 403 without a login redirect. Removed metadata,
changed source bytes, provider changes and stale dates invalidate the grant.
Anyone possessing a still-valid URL can download that one file; its UUID alone
cannot authorize a download. CDN query values are redacted from the access logger.
Signing uses itsdangerous, already required by Flask.

The response supplies `uniqueId` matching the advertised workout ID. If the source
already has that identity its bytes are served directly; otherwise only the
in-memory response is normalized. The stored ZWO, workout targets and original
library download remain unchanged.

## Import and metadata

All today's workout events are downloaded and XML-checked before updating the
managed cache, including already paired events for repeat workouts. Duplicate
event IDs collapse to one. Reimport updates existing files/rows and removes only
obsolete Intervals-managed filenames; other library files are preserved. A failed
download or unexpected API response retains the previous collection. A genuine
empty calendar still clears the provider's old managed cache.

Collection metadata is replaced atomically and retains first-entry aliases for
the existing settings view. Original single-entry metadata remains readable.
An explicitly paired upload removes only that event. With collection metadata,
only a unique exact workout title on the activity date forces a pairing; ambiguous
cases are left to Intervals without removing entries. Legacy single metadata keeps
its prior date-based behavior. A later sync can reimport all today's events.

Only today's cycling entries are advertised. Running, manual, TrainingPeaks and
future-date cards are outside this change. The server's local timezone determines
the day; DST windows use real local midnights. Missing/invalid metadata or files,
unsafe filenames and symlinks do not produce cards. Duration/zones derive from the
ZWO and planned load from provider metadata. Unknown power/load/difficulty is not
replaced by a fitness estimate. The Android login trigger remains separate (#543).

## Validation

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
```

The 51 tests cover the reference contract, multiple workouts and stable reimports,
legacy metadata, per-event completion, failure retention, manual-file preservation,
XML identity/source preservation, signed cookie-free downloads, expiry/revocation,
player/workout scope, log masking, dates/DST and read-only GETs. Integration tests
use the normal dependencies, synthetic profiles and temporary storage; they need
no network or production data. The test-only Werkzeug version shim accommodates
the repository's existing Flask/Werkzeug dependency combination.

The requester confirmed successful native Zwift testing at commit `6c37f9b`.
Final review additionally corrected the required XML identity and malformed-response
handling, with focused automated regression coverage on the final PR source.
