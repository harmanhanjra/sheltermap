# sheltermap — Housing Access Explorer

Offline, stdlib-only Python tool that generates an **open dataset** of shelter and
affordable-housing resources by city, with search, attribute filtering, and
capacity stats. Built for communities that need to locate and compare shelter
capacity, accessibility info, and emergency resources — no server, no API key,
no dependencies.

```
$ python sheltermap.py --city berlin --filter type=emergency --search wheelchair
```

## Features

- **Bundled datasets** (Berlin, Delhi) + load your own JSON or CSV via `--data`
- **Search** across every field: `--search wheelchair`
- **Filter** with repeatable `field=value` predicates: `--filter type=emergency --filter access=wheelchair`
- **Stats**: total capacity, capacity by type, wheelchair-accessible count
- **Open dataset format**: `sheltermap-open-dataset/v1` (JSON) or plain CSV
- **Validation**: every record checked for required fields, valid types, non-negative capacity

## Usage

```
python sheltermap.py --list-cities                 # see bundled cities
python sheltermap.py --city berlin                 # full dataset as JSON
python sheltermap.py --city berlin --format csv    # as CSV
python sheltermap.py --city delhi --stats          # capacity stats
python sheltermap.py --data mycity.json --out mycity.csv --format csv
```

Exit code `1` on bad data or unknown city, so it's safe to script around.

## Dataset format

```json
{
  "format": "sheltermap-open-dataset/v1",
  "city": "berlin",
  "record_count": 6,
  "records": [
    {
      "name": "Berlin Emergency Shelter Mitte",
      "type": "emergency",          // emergency | registry | transitional | subsidized
      "capacity": 120,
      "access": "wheelchair, interpreter",
      "contact": "mitte-shelter@example.org",
      "address": "Sample Str. 1, 10115 Berlin"
    }
  ]
}
```

Bundled datasets ship with `example.org` contacts — swap in real data via `--data`
or a PR. Adding a city is one JSON file in `data/`.

## Development

```
python -m unittest test_sheltermap -v
```

20 tests covering validation, search, filtering, stats, and the CLI.

## License

MIT
