## ADDED Requirements

### Requirement: CLI fetch-history command

The system SHALL provide a `timesfm-meteo fetch-history` subcommand that fetches daily historical temperatures for a given location and date range, using Postgres as a cache layer and Open-Meteo as the upstream source.

#### Scenario: Required arguments accepted

- **WHEN** the user runs `timesfm-meteo fetch-history --latitude 25.05 --longitude 121.57 --years 2`
- **THEN** the command SHALL parse latitude, longitude, and a 2-year range and proceed to the fetch flow

#### Scenario: Mutually exclusive date arguments

- **WHEN** the user provides both `--years` and `--start-date` in the same invocation
- **THEN** the command SHALL exit with a non-zero status and print an error explaining that the two options are mutually exclusive

#### Scenario: Missing date arguments

- **WHEN** the user provides neither `--years` nor `--start-date`
- **THEN** the command SHALL exit with a non-zero status and print an error message listing the required options

### Requirement: Coordinate validation

The system SHALL reject latitude or longitude values outside their valid geographic ranges before any database or API call is made.

#### Scenario: Out-of-range latitude

- **WHEN** the user runs the command with `--latitude 95.0`
- **THEN** the command SHALL exit with a non-zero status and print an error stating the latitude is out of range, without contacting Postgres or Open-Meteo

#### Scenario: Out-of-range longitude

- **WHEN** the user runs the command with `--longitude 200.0`
- **THEN** the command SHALL exit with a non-zero status and print an error stating the longitude is out of range, without contacting Postgres or Open-Meteo

### Requirement: Cache-aware fetch flow

The system SHALL query Postgres for the requested location and date range first, fetch only missing dates from Open-Meteo, persist any newly fetched rows, and return the merged time series ordered by date.

#### Scenario: Full cache hit

- **WHEN** Postgres already contains every date in the requested range for the given coordinates
- **THEN** the command SHALL return the data from Postgres only and SHALL NOT issue any HTTP request to Open-Meteo

#### Scenario: Partial cache miss

- **WHEN** Postgres is missing one or more dates in the requested range
- **THEN** the command SHALL fetch the contiguous span covering all missing dates from Open-Meteo, upsert the fetched rows into Postgres, and return the merged result

#### Scenario: Empty cache

- **WHEN** Postgres contains no rows for the given coordinates and range
- **THEN** the command SHALL fetch the full requested range from Open-Meteo and upsert the rows into Postgres before returning

### Requirement: Schema bootstrap on every invocation

The system SHALL ensure the `daily_temperatures` table exists before reading or writing, by issuing the schema DDL idempotently at the start of each invocation.

#### Scenario: First run on fresh database

- **WHEN** the user runs the command against a Postgres instance where `daily_temperatures` does not yet exist
- **THEN** the command SHALL create the table and then continue with the fetch flow

#### Scenario: Subsequent run

- **WHEN** the table already exists
- **THEN** the schema bootstrap SHALL succeed without error and SHALL NOT alter existing data

### Requirement: Database configuration is mandatory

The system SHALL require `DATABASE_URL` to be configured and SHALL NOT fall back to an API-only mode when the database is unavailable.

#### Scenario: Missing DATABASE_URL

- **WHEN** the user runs the command without `DATABASE_URL` set in the environment
- **THEN** the command SHALL exit with a non-zero status and print an error message instructing the user to set `DATABASE_URL` in `.env`, without attempting any API call

#### Scenario: Database connection failure

- **WHEN** `DATABASE_URL` is set but Postgres is unreachable
- **THEN** the command SHALL exit with a non-zero status and print an error describing the connection failure, without attempting any API call

### Requirement: Result output

The system SHALL emit fetched results to stdout in a stable, line-oriented format and a fetch summary to stderr.

#### Scenario: Successful fetch output

- **WHEN** the fetch flow completes successfully
- **THEN** stdout SHALL contain one line per date in the format `YYYY-MM-DD<TAB><temperature_max><TAB><temperature_min>` ordered by date ascending
- **AND** stderr SHALL contain a single summary line indicating the count of cached rows, fetched rows, and total rows

#### Scenario: Empty result

- **WHEN** the requested range yields zero rows
- **THEN** stdout SHALL be empty
- **AND** stderr SHALL contain a summary line showing `cached=0 fetched=0 total=0`
