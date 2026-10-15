# Planned workout cards on game home: investigation draft

## Confirmed behavior

An Android Zwift client successfully imports today's Intervals.icu workout and
can select it in the workout menu. It does not show that workout on game home.
The automatic import at game login is addressed separately in
https://github.com/zoffline/zwift-offline/pull/543 and was tested successfully
in the physical Android app.

Requests observed from the Android client, without query parameters or personal
data:

- `GET /api/workout/schedule/list`
- `GET /api/head-unit-bff/game-home`
- `GET /api/head-unit-bff/carousels/for-you`
- `GET /api/head-unit-bff/crm`

Currently `api_empty_arrays` handles the schedule endpoint; the generic
`api_head_unit_bff` handler handles the home routes. They return empty JSON arrays
for the relevant requests even when the workout exists as a `.zwo`, is indexed
in `Zfile`, has a `workouts.files` manifest entry, and has provider metadata.

The community client Sauce for Zwift also identifies the schedule endpoint as
the list of third-party scheduled workouts:
https://github.com/SauceLLC/sauce4zwift/blob/b590c6c6e226aee3380e6cf88d86cd8c1bf3f1b1/src/stats.mjs#L1236
That establishes the endpoint's role, not its response fields or the required
game-home card format.

## Reproduction

Install the normal project dependencies and run:

```sh
python tests/test_planned_workout_home_screen.py
```

The test copies the server module into a temporary directory and links only
read-only assets. Its storage, SQLite database and synthetic profile are separate
from the normal `storage` directory. It needs neither an Intervals account nor
network access.

The two control tests confirm the workout is available to the game and the
observed endpoints respond. Two `expectedFailure` tests reproduce the missing
schedule and home data. They are minimum regression checks, not response-schema
tests, and must be replaced or expanded when a verified contract is available.

## What is still required

This draft does **not** implement or claim a working home-screen card. A
sanitized reference response or maintainer-confirmed schema is required before
changing the runtime endpoints. The available setup uses zoffline only; it has
no online Zwift account from which to obtain a reference.

Useful reference material would cover:

1. The schedule response for one third-party workout planned for today.
2. The corresponding `game-home` and `carousels/for-you` responses, including
   which route actually supplies or references the card.
3. How the scheduled workout identifies its workout definition and asset, and
   how the client launches it. A manifest GUID must not simply be assumed to be
   a workout UUID or a schedule ID.
4. Date/time, sport, completion, artwork and provider fields that the client
   requires, including request parameters relevant to selecting those results.

Reference fixtures must use synthetic names and identifiers and contain no
tokens, cookies, API keys, account details or private training/health data.

## Implementation acceptance criteria

- Keep this work independent of the timing of the Intervals import.
- Derive the card from the authenticated player's selected provider and
  existing workout state. Protect the new player-specific responses with the
  existing JWT/session authentication instead of exposing them publicly.
- Use verified schedule/card/asset identifiers and response shapes; cover them
  with synthetic contract fixtures.
- Resolve the card to the same available workout the game can download.
- Handle local planned dates, missing files, stale metadata, completed workouts,
  multiple workouts and sport filtering according to the verified contract.
- Preserve behavior for profiles without a provider and avoid cross-player
  data exposure or provider changes.
- Keep API/network synchronization out of the home-screen GET handlers.
- Validate the card and its launch action in the actual Android client before
  marking the implementation ready for review.

No runtime routes, profile data, authentication behavior, production deployment
or CI configuration are changed by this investigation draft.
