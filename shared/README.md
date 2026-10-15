# shared

Test fixtures used by more than one platform.

- `schedules.json`: example schedules in the JSON format every platform reads
  and writes. Parsed by androidlib's Kotlin tests, the Flutter app's Dart tests
  and blocklib's Python tests, so the three can't drift apart.
