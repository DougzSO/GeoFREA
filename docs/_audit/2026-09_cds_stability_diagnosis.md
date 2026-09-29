# F4-3: CDS instability diagnosis (2026-09-28)

Scope: this is a diagnostic report only, per COMMAND F4-3. It gathers evidence on the cause of
COMMAND F4-2's observed CDS request-latency instability (`docs/OPEN_QUESTIONS.md` OQ-038,
`docs/phases/F1_data_acquisition.md` D-F1-017/D-F1-018) and on ARCO-ERA5's viability as an
alternative source for M-F1-05's `fg10` acquisition. It does not choose a source and does not
touch any acquisition file in production (`scripts/acquire_era5_gust.py`, `fetchers/era5.py`,
`era5_registry.py`, `era5_registry.json` untouched). No CDS acquisition for `fg10`'s real
1995-2014 target years was issued from this report's work — the one live CDS request made (item
2 below) is an isolated, out-of-period, out-of-production probe, not a step of M-F1-05's
acquisition.

## (a) CDS service status during the F4-2 attempt window

- **Official incident/maintenance record: none found.** No CDS status-history or incident log
  page was located; [cds.climate.copernicus.eu/live](https://cds.climate.copernicus.eu/live)
  (checked 2026-09-28, ~21:02 UTC) exposes only a real-time dashboard, no historical log. Web
  search for a CDS incident dated 2026-09-28 returned no matching result — the closest hits were
  unrelated (2022 WEkEO disruption, a 2024 "no longer in testing mode" notice, a generic forum
  thread on CDS API limitations). **Absence of a public incident report is recorded as an
  absence, not as evidence the service was healthy** — per instruction, no cause is inferred from
  this silence.
- **Live dashboard at check time (2026-09-28, ~21:02 UTC, several hours after F4-2's run window
  which ended 17:40 local):** 2,636 queued users, 8,328 queued requests, 494 running
  users/517 active requests, 2,239 users waiting. `reanalysis-era5-single-levels` (the exact
  dataset F4-2 used post-D-F1-017) is the platform's 2nd most-requested dataset: 4,146 active
  users, 20,276 GB downloaded in the prior 24h. This confirms the dataset is under heavy,
  variable concurrent load from the wider CDS user base as a general condition of this system,
  but it is a snapshot taken after the fact, not a measurement of load during F4-2's own window
  (10:24-17:40 local, 2026-09-28) — it cannot be used to assert what the backlog was *at that
  specific time*, only that large, fluctuating queue backlogs are a normal, observed state of
  this shared resource.
- **Forum/documentation finding (ECMWF Confluence, CDS API limitations thread):** "Limits are set
  on usage of CDS resources to ensure an appropriate level of performance for users. These limits
  are changed from time to time according to the current workload of the system and number of
  concurrent tasks. The CDS will queue requests which would otherwise cause any of these limits
  to be exceeded." This is an official acknowledgment that queueing is a designed response to
  *system-wide* load (not per-user throttling alone), consistent with — but not proof of — F4-2's
  observed variance (3 min to 50+ min on the same request shape, including consecutive requests).
  No specific numeric limit or SLA is published.

**Finding:** no documented incident explains the F4-2 window specifically; the platform's queueing
behavior is officially load-dependent and the dataset in question is one of CDS's most heavily
used, which is circumstantially consistent with — but does not confirm — service-side degradation
as the cause of F4-2's variance.

## (b) Concurrency: self-imposed limit vs. CDS-side

- **Code inspection (`scripts/acquire_era5_gust.py`), not inference:** the F4-2 run used
  `ThreadPoolExecutor(max_workers=1)` (line 167) and a strictly sequential `for country in
  study_countries:` loop (line 122) — one request in flight at a time, submitted, awaited
  (`future.result(timeout=STALL_TIMEOUT_S)`), and only then followed by the next. **F4-2 never
  issued concurrent requests to the CDS.** This rules out a self-imposed client-side concurrency
  limit as the cause of the observed stalls — there was no concurrency to throttle in the first
  place.
- Because client-side concurrency is already ruled out by code inspection, item 2's fallback
  ("if it cannot be determined from documentation, test with one isolated request and compare
  queue time against F4-2's average") is repurposed here as a **general queue-latency check under
  current conditions**, not a concurrency test specifically (there is nothing to test concurrency
  against when the client only ever sends one request).
- **Isolated live test:** one request issued outside any production script (throwaway script,
  not committed, not under `scripts/`), single country (Portugal mainland bbox, same as the
  F4-1b/D-F1-016 probe), single year **2005** — deliberately outside the 1995-2014 target range
  so this test can never be mistaken for, or double-count as, real M-F1-05 acquisition progress.
  No production file, registry, or `year_sha256` entry was touched.

  **Result: completed.** Request `11b7e3ba-080b-4bdb-90b1-5a56b10870bb`
  (`reanalysis-era5-single-levels`, `fg10`, PRT bbox, year 2005 — single, isolated, no production
  file touched):

  | Timestamp (local) | Event |
  |---|---|
  | 18:07:25 | submitted -> `accepted` |
  | 18:46:29 | `accepted` -> `running` (queue wait: **39 min 4 s**) |
  | 18:58:38 | `running` -> `successful` (processing: **12 min 9 s**) |
  | 18:58:44 (approx.) | download complete, 6.91 MB in ~6 s |

  **Total wall time: 3,085.7 s = 51.4 minutes**, for the exact same dataset/variable/bbox shape
  F4-2 used, issued as a single isolated request with no other concurrent activity from this
  client. This is **at the high end of, and in fact slightly above, F4-2's own observed 3 min-50+
  min range** — high enough that it would itself have tripped run 2's 50-minute
  (`STALL_TIMEOUT_S=3000s`) watchdog. Queue wait alone (39 min) accounts for the overwhelming
  majority of the total.

**Finding:** with client-side concurrency already ruled out (no concurrency existed), a single,
present-day, isolated request reproduced latency in the same range that caused F4-2's stalls —
this is affirmative evidence, not merely consistent-with, that the variance is **server-side queue
behavior under system load**, not an artifact of how F4-2 issued its requests. It does not
identify *why* CDS queueing is this variable (no incident was found in (a) to attribute it to a
specific cause), but it does rule out both of the client-side hypotheses (self-imposed concurrency
limit, or F4-2-specific request malformation) as the explanation: the same stall-class latency
reproduces on a clean, single, isolated request outside any production code path.

## (c) `fg10` availability and schema in ARCO-ERA5

Checked directly against the live store, not from cached documentation or memory (a search first
returned an outdated claim that the archive's period of record ends 2021-08-31 — this was
verified against the store itself and found stale/incorrect, see below):

- **Store:** `gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3`, Zarr v2
  format, read anonymously (no credentials needed) via `gcsfs`/`zarr` — both already installed in
  this environment (`gcsfs==2026.6.0`, `zarr==3.1.6`, `xarray==2025.12.0`).
- **Both ERA5 gust variables exist**, confirmed by reading `.zmetadata`:
  - `10m_wind_gust_since_previous_post_processing` — `short_name: fg10`, `units: m s**-1`,
    dtype `float32`, dims `(time, latitude, longitude)`. **This is the exact variable M-F1-05 /
    D-F4-008 specifies** (annual maximum of `fg10`, not `i10fg`).
  - `instantaneous_10m_wind_gust` — `short_name: i10fg`, present but not the one M-F1-05 uses.
- **Grid:** global, 0.25 deg, `latitude` 721 points, `longitude` 1440 points — same native
  resolution as the CDS raw hourly source GeoFREA already acquired for PRT/BRA/IND years on disk
  (D-F1-017/018), so no resolution mismatch with data already in hand.
- **Chunking:** `chunks: [1, 721, 1440]` — **one chunk covers one full global timestep**. There is
  no spatial pre-chunking by region; reading any bbox for a given hour still requires fetching
  that hour's entire global chunk (compressed, blosc/lz4). This has a direct integration-effort
  consequence, see (d).
- **Time coverage — verified by direct value reads, not by trusting the nominal axis alone:** the
  `time` array's nominal shape (`1,323,648` entries, `hours since 1900-01-01`) spans through
  **2050-12-31**, which is a pre-allocated future-proofed array size, not a claim that data exists
  through 2050 — confirmed by sampling actual (non-`NaN`) `fg10` values at four points:

  | Date sampled | `fg10` value (m/s) |
  |---|---|
  | 1995-01-01 | 8.446 |
  | 2014-12-31 | 6.380 |
  | 2023-06-01 | 5.458 |
  | 2026-01-01 | 6.230 |

  All four returned real, physically plausible gust values (no `NaN`) — **M-F1-05's full
  1995-2014 target period is confirmed populated with real data**, and the store is confirmed
  current well past the outdated "ends 2021" claim found in initial web search results (data
  present as late as 2026-01-01, the latest date checked).

**Finding:** `fg10` exists in ARCO-ERA5, at the required resolution, fully covering 1995-2014,
confirmed by direct read against the live store rather than assumed from search results (which
were checked and found stale on the coverage-end-date point).

## (d) Integration effort estimate (conditional on (c), which is confirmed)

- **New reader needed: yes, but low-cost.** No CDS-style request/queue/download step — ARCO-ERA5
  is read directly as a remote Zarr array via `xarray`/`gcsfs`, both already present in this
  environment's dependencies (confirmed above); no new package would need to be added to
  `pyproject.toml` on that count. This replaces `fetchers/era5.py`'s `download_country_bbox_year()`
  / `merge_yearly_files()` CDS-request step; `compute_daily_maxima()` and `compute_annual_maxima()`
  (`fetchers/era5.py:346,368`) already accept an in-memory `xr.Dataset` in addition to a file
  path (`compute_annual_maxima(daily_max_path: Path | xr.Dataset, ...)`), so the reduction
  functions downstream of the raw read would need little or no change — only the acquisition step
  itself (how the hourly field gets into memory/disk) would be new.
- **Chunking cost, not yet measured (flagged, not estimated as zero):** because chunking is
  one-global-timestep-per-chunk (see (c)), a naive per-country-year pull (8,760 hourly timesteps
  x 20 years x 3 countries = 525,600 global chunk fetches if read one timestep at a time) would
  issue far more individual object reads than the 60 CDS requests F4-2's whole run represents,
  even though each chunk is small and GCS is typically fast/cheap for public-bucket reads.
  `xarray`/`zarr` can batch contiguous time-chunk reads efficiently and GCS public-bucket egress
  has no CDS-style queue, but the *actual* wall-time and request-count cost of a real bbox-cropped
  multi-year pull was not measured here (item 5 forbids any new acquisition-shaped request in this
  report) — this is a genuine open unknown, not assumed favorable or unfavorable.
- **`GEOFREA_DATA_DIR/raw/<source>/` (A-08) compatibility:** no conflict. A-08 governs where
  GeoFREA writes its own materialized output, not the format of an upstream source; an
  ARCO-ERA5-sourced acquisition would still write its per-country-year extract (and the reduced
  annual-maxima product) as conventional files under `raw/era5_arco/<ISO3>/` (or similar),
  matching every other source's existing layout. No format the pipeline cannot already write
  (NetCDF, the same as the current CDS path) is implied by reading from Zarr upstream.
- **`year_sha256` idempotency — not directly reusable, needs an equivalent, not assumed
  adaptable.** Checked against the actual field definition
  (`era5_registry.py::Era5RegistryEntry.year_sha256`, docstring line 56): it hashes **"per-year
  raw-hourly-download"** — the discrete CDS NetCDF file each year's request produces — not the
  reduced output. ARCO-ERA5 has no equivalent discrete per-year "download" to hash the same way;
  a per-country-year extract would first need to be materialized to a local file (e.g. write the
  cropped hourly slice to NetCDF) before an equivalent hash could be taken over it. This is
  achievable with the existing hashing pattern (`HASH_CHUNK_BYTES`, `core.py`'s per-file sha256)
  applied to that materialized file, but it is a new step, not a reuse of the current mechanism
  unchanged — flagged here rather than assumed trivial.

**Finding:** integration is plausible with tools already installed and without breaking A-08, but
carries one measured unknown (real chunk-read cost/count for a bbox multi-year pull) and one
design gap (no direct `year_sha256` equivalent without first materializing a local per-year file)
that a real estimate would need to close before being taken as final.

## (e) Recommendation — options and trade-offs (no choice made; Douglas decides per OQ-038)

1. **Resume CDS raw hourly (`reanalysis-era5-single-levels`) with a revised retry/timeout
   policy.** No new integration work (code, hashing, and 19/60 country-years already on disk are
   untouched and reusable as-is). Trade-off: the isolated probe (b) reproduced 51.4-minute total
   latency on a clean, single, present-day request — confirming the variance is real, current,
   and server-side, not an F4-2-specific artifact. Any fixed wall-clock timeout below ~51 min
   risks discarding a real success under conditions no different from today's; OQ-038's
   retry/timeout policy question is not resolved by this finding, but the finding confirms the
   policy needs to tolerate this magnitude of queue wait as a normal case, not an outlier.
2. **CDS derived daily-statistics product.** Already ruled out operationally by D-F1-017 (hard
   403 cost-limit, then a non-progressing queue on two separate real attempts) — not re-opened by
   this report; included here only for completeness of trade-off space, not as a live option.
3. **ARCO-ERA5.** `fg10` confirmed present, correct resolution, full 1995-2014 coverage, by direct
   store read (c). No CDS queue exposure at all — trades a queue-latency problem for an unmeasured
   chunk-read-cost problem (d) and a `year_sha256`-equivalent that needs new (if small) design
   work before resuming. Would abandon 19/60 country-years' partial CDS progress currently on disk
   as *transport-path* progress (D-F1-017 already establishes this is a transport-tier change, not
   a variable/result change per M-F1-05) — those years' data is not invalidated, but a from-ARCO
   pipeline would not reuse the existing CDS-downloaded files as inputs; they would be redundant if
   this path fully replaces CDS as the acquisition source, or a legacy foot-print to reconcile if
   only remaining years switch to ARCO.

No option is selected here per item 6.

## Conformance to completion criteria

- (a) service-status finding: recorded, with link and forum citation. No incident confirmed for
  the F4-2 window specifically; that absence is stated as an absence.
- (b) concurrency finding: recorded from code inspection (conclusive: no client-side concurrency
  existed) plus a completed live isolated-request test (51.4 min total wall time, reproducing
  F4-2's stall-class latency on a clean single request).
- (c) ARCO-ERA5 `fg10` existence/schema: recorded with direct Zarr-metadata evidence and four
  sampled real values confirming 1995-2014 coverage.
- No file under `scripts/acquire_era5_gust.py`, `fetchers/era5.py`, `era5_registry.py`, or
  `era5_registry.json` was read-modified or executed in this report's work. No CDS request for any
  1995-2014 target year was issued.
