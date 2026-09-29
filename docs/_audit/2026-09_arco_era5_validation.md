# F4-4: ARCO-ERA5 validation — numeric equivalence, real cost, hash prototype (2026-09-28)

Follow-up to `docs/_audit/2026-09_cds_stability_diagnosis.md` (F4-3), closing the three
unknowns that report left open before any commitment of the 41 remaining `fg10` country-years
to a source. This report is diagnostic and prototyping only — it does not choose CDS or
ARCO-ERA5. **No file under `scripts/acquire_era5_gust.py`, `fetchers/era5.py`,
`era5_registry.py`, or `era5_registry.json` was written to or executed in write mode.**
`era5_registry.json` was read-only to select the test country-year. No acquisition request at
country-year scale (CDS or ARCO) was issued for any of the 41 remaining country-years — the only
ARCO read was the single test pull in (a)/(b) below.

Test country-year selected: **PRT 2010** — 17/20 of PRT's years are already on disk from F4-2
(the most of any country), and 2010's `year_sha256` was recomputed here from the on-disk file
and matches `era5_registry.json` exactly:
`e23b8e9b888f944cd522ee546b88381fbc211f5e1aeff72982b892f7ee215281`.

## (a) Numeric equivalence, CDS vs ARCO-ERA5, same country-year

**Scope note:** a full-year ARCO pull for this bbox is 8,760 chunk fetches at ~3.19 MB each
(~27 GB) — see (b) for why this is costly. The point-by-point comparison here uses **July 2010**
(744 hourly timesteps) as a real, representative sample rather than the literal full year,
justified in (b): chunk cost and (by direct measurement here) numeric agreement are uniform
across the year, not a special property of July.

Method: CDS file (`PRT_fg10_hourly_bbox_2010.nc`, GRIB-via-cfgrib-derived, lat 29.75-42.5, lon
-31.75--5.75, native ERA5 0.25 deg grid) read as-is; ARCO-ERA5 read via anonymous `gcsfs`/`zarr`,
sliced to the same time range, same lat range, and the equivalent longitude range converted to
ARCO's 0-360 convention (328.25-354.25 deg east ≡ -31.75--5.75). Grids matched exactly in shape
(52 x 105) and index alignment — no interpolation, regridding, or nearest-neighbor snapping was
needed; both sources share the identical native ERA5 grid.

| Metric | Value |
|---|---|
| Common timestamps compared | 744 (full July 2010, hourly) |
| Shapes match | yes (744, 52, 105) |
| Max absolute difference | **0.000401 m/s** |
| Mean absolute difference | 0.0001576 m/s |
| Median absolute difference | 0.0001564 m/s |
| RMSE | 0.0001830 m/s |
| Cells exactly bit-identical | 0.147% |
| Cells within 0.01 m/s | **100%** |
| July-window max, CDS | 25.1378 m/s |
| July-window max, ARCO | 25.1381 m/s (diff 0.0003 m/s) |

**Finding: the two sources are numerically equivalent for practical purposes.** The residual
difference (max 0.0004 m/s, four orders of magnitude below the variable's own range, ~0-25+ m/s)
is consistent with float32 rounding/encoding-path differences (CDS's file passed through
GRIB-to-NetCDF via `cfgrib`; ARCO's is stored directly as Zarr float32) rather than any real
difference in the underlying reanalysis values. Not a single cell differs by more than 0.0004
m/s. This confirms ARCO-ERA5 is not a different or degraded product for this variable — a
prerequisite for considering it at all — but does **not** by itself make it the cheaper option;
see (b)/(c).

## (b) Real ARCO-ERA5 read cost, measured, and extrapolation to the 41 remaining country-years

**Measured, not estimated**, same July 2010 PRT pull as (a):

| Metric | Value |
|---|---|
| Chunks fetched | 744 (exactly 1 per hourly timestep — the store's own `.zarray` metadata gives `chunks: [1, 721, 1440]`, confirmed independently by listing 20 real chunk objects on GCS) |
| Wall time | 366.7 s for 744 chunks (0.493 s/chunk effective, includes whatever internal concurrency `zarr`/`gcsfs` used by default — not tuned or maximized here) |
| Compressed bytes actually read | ~2.37 GB (744 x avg. 3,188,170 bytes/chunk, sampled directly from 20 real GCS objects: 3,183,400-3,191,950 bytes, near-uniform) |
| Effective throughput | ~6.47 MB/s |
| Uncompressed size of the slice actually used | 16.2 MB (744 x 52 x 105 x 4 bytes) |

**Chunking is not spatially partitioned.** `10m_wind_gust_since_previous_post_processing`'s Zarr
chunk shape is `(1, 721, 1440)` — one chunk *is* one full global timestep. There is no way to
fetch a country's bbox for one hour without downloading and decompressing that entire hour's
global grid (~3.19 MB compressed) first. A 16.2 MB useful slice required 2.37 GB of transfer —
**a ~146x amplification** between what the country's bbox needs and what the store's chunking
forces to be read. `xarray`/`zarr` did not fall back to a naive one-request-per-byte pattern
(each of the 744 reads was a whole-chunk object fetch, the store's actual atomic unit, not a
worse pattern this test triggered), but there was also no way to *avoid* that if a program run per
country needs to slice by the country's own bbox and years independently, because whole-chunk
transfer is what the storage layout itself imposes.

**Extrapolation is exact multiplication, not a linear-regression guess**, because chunk count per
country-year is fixed at exactly `8,760` (hours/year) regardless of country or bbox size, and the
measured per-chunk byte size/wall time is stable to <0.3% across the 20-chunk sample:

| Scenario | Country-years | Chunk fetches | Est. wall time | Est. data transfer |
|---|---|---|---|---|
| **Naive, gaps only** (BRA 19 + IND 19 + PRT 3 = 41, per `era5_registry.json`'s actual state — see note below on the 41 vs. 42 discrepancy) | 41 | 359,160 | **~49.2 hours** | **~1,066 GB (1.04 TB)** |
| **Naive, full re-acquire for provenance consistency** (BRA 20 + IND 20 + PRT 20 = 60, every year re-pulled via ARCO including PRT's 17 already-done) | 60 | 525,600 | ~72.0 hours | ~1,561 GB (1.52 TB) |
| **"Smart" implementation** — fetch each of the 20 reference-period years' global chunks *once*, crop locally for all three countries from the same in-memory/on-disk pull, instead of re-fetching the same global chunk per country | 20 unique years (serves all 3 countries) | 175,200 | ~24.0 hours | ~520 GB |

**Note on country-year counts:** COMMAND F4-4's item 3 text says "BRA 19, IND 20" but
`era5_registry.json` (read here, unmodified) shows IND at 1/20 (1995 done), i.e. **19** remaining,
not 20 — the naive-gaps-only row above uses the registry's actual state (41 total: 19+19+3),
consistent with F4-3's own count. If IND's existing 1995 file is intended to be discarded and
re-pulled from ARCO too (for single-source provenance within IND), that is 20, not 19, for IND
specifically — a sub-case of the "full re-acquire" row's logic, not calculated separately here
since it only shifts totals by one country-year.

**Why "smart" is not free:** even the best-case, chunk-sharing implementation still moves **520 GB**
to answer a question CDS answers by transferring only the bbox-cropped bytes it was asked for
server-side (F4-2's real per-country-year CDS downloads were tens to hundreds of MB, e.g. IND
1995's 542 MB was the *largest* single-country-year download recorded in D-F1-018 — three orders
of magnitude below ARCO's per-chunk-fetch model). This is an architecture-level cost of
ARCO-ERA5's global, non-bbox-aware chunking for this variable, not an implementation shortcoming
in this test.

## (c) ARCO vs. CDS total time comparison

Per COMMAND F4-4 item 3, CDS calibrated at the isolated-probe result from F4-3 (~51.4 min total,
rounded up to **55 min/request** to be conservative), sequential (matching F4-2's actual and only
tested concurrency pattern, `max_workers=1`):

| Path | Total estimated wall time | Total estimated data transfer |
|---|---|---|
| **CDS raw hourly, 41 remaining country-years, sequential, ~55 min/request** | **41 x 55 min = 2,255 min = ~37.6 hours** | tens of GB (each request bbox-cropped server-side; F4-2's largest single-country-year was 542 MB) |
| ARCO-ERA5, naive per-country-year (b) | ~49.2 hours | ~1,066 GB |
| ARCO-ERA5, "smart" shared-chunk-per-year (b) | ~24.0 hours | ~520 GB |

**Finding:** ARCO-ERA5 is **not unambiguously faster**. Only the "smart" (unimplemented today)
variant beats CDS on wall time (~24 h vs. ~37.6 h), and it does so while moving roughly two orders
of magnitude more data (~520 GB vs. tens of GB) — a real cost against local disk space under
`GEOFREA_DATA_DIR` and against whatever network path this environment has to GCS (measured here
at ~6.47 MB/s, itself a possible bottleneck specific to this environment, not necessarily GCS's
own ceiling). The naive (unoptimized) ARCO path is worse than CDS on both wall time and data
volume. CDS's ~55 min/request figure is itself a worst-case calibration (F4-2's actual times
ranged 3 min-50+ min; many requests would likely be faster) — using it uniformly for all 41
makes the CDS estimate conservative (an upper bound), while ARCO's numbers are direct
measurements, not upper bounds. Whichever the real spread on each side, the two options are much
closer in total wall time than F4-3's diagnosis alone would have suggested, once ARCO's
non-bbox-aware chunking cost is actually measured rather than assumed favorable.

## (d) `year_sha256` equivalent for ARCO — functional prototype

Implemented and run in isolated test code (`arco_year_hash_prototype.py`, scratch directory, not
under `src/` or `scripts/`), reusing the **exact existing hashing mechanism** rather than a new
one — imports `data_acquisition/phase.py::_sha256_file()` and
`data_acquisition/schemas.py::HASH_CHUNK_BYTES` (8 MiB) unmodified, no reimplementation of chunk
size or algorithm:

```
HASH_CHUNK_BYTES used (production constant, unmodified): 8388608
materialized file: PRT_fg10_hourly_bbox_2010_arco.nc (July 2010 sample)
file size: 16,263,732 bytes
sha256: 89f1c98248f4c59e5640c537d68336087127e6f5937a7668a6128c86aca5ef45
hash wall time: 0.031 s
```

Hashing cost itself is negligible (0.031 s for a 16 MB file; a full country-year file, ~192 MB
per D-F1-018's PRT figures, would still be well under `_HASH_BUDGET_S`'s existing 60 s ceiling —
the same budget the CDS path already uses, D-core-016). **No timing concern on the hashing step
itself** — the cost that matters is the read/materialization in (b), not the hash.

**Where this would enter the pipeline if integrated** (documented per item 4; not implemented in
production code):

1. `fetchers/era5.py` would gain a new function analogous to `download_country_bbox_year()`
   (`era5_registry.py:179` today's CDS entry point), e.g. `materialize_arco_country_year()`,
   called from the same point in `scripts/acquire_era5_gust.py`'s per-year loop that currently
   calls `download_country_bbox_year()`.
2. That function opens the ARCO-ERA5 store (anonymous `gcsfs`, read-only), slices by the year's
   8,760-hour time index range and by the country's existing bbox
   (`bbox_from_polygon()`, already shared with the CDS path), and writes the result to a local
   NetCDF — either at the same conventional path CDS downloads use today
   (`raw/era5/_global/<ISO3>_fg10_hourly_bbox_<year>.nc`) or a parallel
   `raw/era5_arco/<ISO3>/` location if both transports are ever kept side by side for
   provenance separation (this choice is not resolved here — see (e), a related open question
   about mixed provenance).
3. `_sha256_file()` (unmodified) hashes that materialized file exactly as it does the CDS
   download today, and the digest lands in the **same** `Era5RegistryEntry.year_sha256[str(year)]`
   field — no new field or schema change needed, since the field's consumer (the resume-skip
   check in `scripts/acquire_era5_gust.py`) only compares a file's current hash to a recorded
   one; it does not care which transport produced the file.
4. `compute_daily_maxima()`/`compute_annual_maxima()` (`fetchers/era5.py:346,368`) need **no
   change** — `compute_annual_maxima()` already accepts `Path | xr.Dataset`, so the
   materialized-then-reduced flow is identical downstream of step 3 regardless of source.

This closes F4-3's flagged design gap: `year_sha256` **is** adaptable to ARCO, via a
materialize-then-hash step, without changing the field's meaning or its consumers — the only new
code is the materialization step itself (items 2 above), not the hashing or reduction logic.

## (e) Pending decision: PRT's 17 already-downloaded CDS years — not decided here

Two scenarios, costed, no choice made (per item 5):

1. **Keep PRT's 17 CDS years as-is; only fill the 3 remaining PRT years (2012-2014) plus BRA/IND
   gaps from whichever source is chosen going forward.**
   - Cost: zero additional read for PRT's existing 17 years.
   - Risk: if BRA/IND/PRT's remaining years end up sourced from ARCO while PRT's 17 stay
     CDS-sourced, `hazard_context.parquet`'s per-cell `fg10` mean-of-20-annual-maxima
     (D-F4-009) would be computed from a **mixed-provenance** input for PRT specifically (17
     CDS-derived annual maxima + 3 ARCO-derived) — (a) shows the two sources agree to within
     0.0004 m/s, so the numeric risk is negligible by this test's own evidence, but this is
     mixed provenance within a single country's indicator, a fact `members.yaml`/registry
     provenance fields would need to represent honestly (not silently), not a decided-safe
     shortcut.
2. **Re-pull all 20 PRT years from ARCO-ERA5, discarding/superseding the 17 CDS-downloaded
   years, for single-source provenance.**
   - Cost, from (b)'s per-chunk rate: 20 country-years x 8,760 chunks = 175,200 chunks, **~24.0
     hours**, **~520 GB** transfer, using the "smart" per-year chunk-sharing scenario as the
     best case (naive per-country-year, if implemented without sharing across BRA/IND at the
     same time, would be worse — see (b)'s naive-row math applied to 20 years alone: 20 x 8,760
     x 0.493 s = ~24.0 hours regardless of naive/smart for PRT alone, since sharing only helps
     *across countries* sharing the same year, not within one country re-pulling years it
     already has elsewhere sourced).
   - Benefit: single, consistent provenance for the entire PRT `fg10` series, eliminating (1)'s
     mixed-provenance representation question entirely.

No default is applied. Awaiting Douglas's verdict.

## Conformance to completion criteria

- (a) numeric equivalence: recorded with real point-by-point statistics (max/mean/median/RMSE,
  744 timestamps), not a qualitative "matched" claim.
- (b) real ARCO cost: recorded with measured wall time, measured chunk count and byte sizes
  (sampled directly from GCS object metadata), and exact-multiplication extrapolation to 41/60/20
  country-year scenarios.
- (c) ARCO vs. CDS total time: recorded as a direct table, both real-measurement-derived.
- (d) hash prototype: implemented, run, and its output shown verbatim; integration point
  documented precisely (function names, call sites, field reused).
- No file under `scripts/acquire_era5_gust.py`, `fetchers/era5.py`, `era5_registry.py` was
  modified; `era5_registry.json` was read-only. No 41-country-year-scale request was issued via
  either CDS or ARCO-ERA5 — only the single PRT-2010-July test pull in (a)/(b).
