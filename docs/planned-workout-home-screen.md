# Intervals.icu workouts on the home screen

All valid cycling workouts synced for today's local date are offered in For You
and the `Intervals.icu` partner folder. Next Up selects the first workout.
Home-screen GETs only read the existing cache; the Android login trigger is
separate (#543). Running, TrainingPeaks and future-day cards are outside scope.

## Responses and downloads

The schedule, workout summary, Next Up and For You endpoints use existing
session/Bearer authentication and the selected profile in single-player mode.
They reuse stable player/event-scoped workout IDs and local-day schedule IDs.
For You returns one entry per workout, with the existing schedule ID, provider
and signed asset URL; an empty result retains the working `{}` fallback.

Cookie-free downloads use
`https://cdn.zwift.com/tp-workouts/intervalsicu/{workoutId}.zwo?token=...`.
The existing `cdn.zwift.com` DNS redirect must point to zoffline. Flask's existing
signing dependency grants access to one player/workout/source-file hash until
local-day expiry. Missing/invalid/expired grants return 403 without a login
redirect. Metadata removal, content/provider/date changes revoke access. Anyone
with a valid URL can download that file; access logs redact CDN query values.

The response supplies the required XML `uniqueId` matching the workout ID.
Only the response is normalized when needed; stored ZWO files, training targets
and the existing zfiles/manifest downloads are preserved. Duration/power zones
come from the ZWO and planned load from Intervals.icu metadata. Unknown fitness
values are not estimated. Invalid metadata/files and unsafe paths produce no card.

## Import and compatibility

All today's events are downloaded and XML-validated before any storage callback,
including paired events for repeat workouts. Duplicate event IDs collapse to one.
Reimport updates existing files/rows and removes only obsolete managed entries.
Download/XML errors and unexpected API payloads retain the previous collection;
a genuine empty calendar clears it. Other library files are preserved.

Collection metadata is replaced atomically. Legacy single entries remain readable,
and first-entry aliases retain the existing settings view. Completion removes
only an explicitly paired event. For collections, only a unique exact title on
the activity date forces pairing; ambiguous cases are left to Intervals. Legacy
single-entry date-based pairing remains compatible. A sync can reimport events.

## Verification

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
```

The 53 isolated tests use synthetic profiles and temporary storage without network
access. They cover response contracts, multi-workout import/reimport/completion,
failure retention, XML identity/source preservation, download grants, profile
isolation, authentication, date/DST filtering, read-only GETs and For You links.

Response references: [schedule/Next Up](https://github.com/zoffline/zwift-offline/pull/544#issuecomment-6257306924),
[cookie-free download](https://github.com/zoffline/zwift-offline/pull/544#issuecomment-6269590334),
[XML identity](https://github.com/zoffline/zwift-offline/pull/544#issuecomment-6273631903),
[For You](https://github.com/zoffline/zwift-offline/pull/544#issuecomment-6287951881).
The requester confirmed the multi-card flow at `07ca8b8`. Fatsbrown also
[verified three workouts](https://github.com/zoffline/zwift-offline/pull/544#issuecomment-6297182983)
on Windows/Zwift 1.124.0, including selection/start from For You, the partner
folder and Next Up. Subsequent import/lookup simplifications have regression coverage.
