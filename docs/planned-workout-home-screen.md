# Intervals.icu workouts on the home screen

All valid cycling workouts synced for today's local date appear in For You and
the `Intervals.icu` partner folder. Next Up selects the first workout. Home-screen
GETs only read the cache; the Android login trigger remains separate (#543).
Running, TrainingPeaks and future-day cards are outside scope.

## Storage and downloads

Workouts are stored once in `storage/tp-workouts/intervalsicu/{workoutId}.zwo`,
without adding them to zfiles or the custom-workout manifest. Each imported event
gets a random UUIDv4, persisted in that profile's metadata and reused on reimport
and restart. The cached XML supplies that UUID as its required `uniqueId`; names,
descriptions and training targets retain their original Unicode/content.

The authenticated schedule, summary, Next Up and For You endpoints reuse those
IDs and the same CDN URL. For You returns a list, including `[]` when empty.
Single-player mode retains its selected anonymous profile.

`https://cdn.zwift.com/tp-workouts/intervalsicu/{workoutId}.zwo` serves the cached
file without a login cookie or token, following the native downloader's behavior.
The normal `cdn.zwift.com` DNS redirect must point to zoffline. **Anyone who knows
the URL can download the workout.** The URL has no automatic expiry and can appear
in normal access logs. Random IDs prevent deriving it from player/event IDs; they
do not provide per-user download authorization. Removing the file revokes the URL.

## Import, cleanup and compatibility

All today's events are downloaded and XML-validated before any storage callback,
including paired events for repeat workouts. Event IDs are deduplicated. Cache
files and metadata are published atomically; provider/download errors retain the
previous collection. A genuine empty calendar clears that profile's cache.
Reimport removes files for events no longer present; completion removes only an
explicitly paired event. Provider changes also clear that profile's cache.
Other profiles' files and unrelated custom workouts remain untouched.

Legacy metadata remains readable for status/pairing. The next successful sync
creates the new cache and retires the former managed zfiles/manifest copies;
a failed download leaves them in place. Legacy manifest entries are marked deleted
so clients can retire old copies. First-entry metadata aliases preserve the
existing settings view. Ambiguous activity pairing is left to Intervals.icu.
A later sync can reimport an event; a previously removed event gets a new UUID.

## Verification

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
```

The isolated tests use synthetic profiles and temporary storage without network
access. They cover response contracts, random/persisted IDs, unsigned downloads,
profile isolation and cleanup, reimport/completion, migration, atomic publication
failures, Unicode/targets, date/DST filtering and read-only GETs.

References: [schedule/Next Up](https://github.com/zoffline/zwift-offline/pull/544#issuecomment-6257306924),
[cookie-free downloads](https://github.com/zoffline/zwift-offline/pull/544#issuecomment-6269590334),
[XML identity](https://github.com/zoffline/zwift-offline/pull/544#issuecomment-6273631903),
[For You](https://github.com/zoffline/zwift-offline/pull/544#issuecomment-6287951881),
[storage simplification](https://github.com/zoffline/zwift-offline/pull/544#issuecomment-6362438696).
The requester and fatsbrown previously verified the native multi-card flow;
fatsbrown tested three workouts on Windows/Zwift 1.124.0. This storage revision
has automated coverage and still needs a native migration/display recheck.
