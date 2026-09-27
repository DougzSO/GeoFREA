# CRAEI ISIMIP3b climate reuse decision (ADJ-6)

Read-only audit against `CRAEI_BASELINE_DIR` (`C:\Users\User\Desktop\DOUGLAS\DOUTORADO\PHD RELATED WORKS\CLIMATE RISK FRAMEWORK\CRAEI`) and its data directories (`paths.local.yaml`). No file copied, no config or code edited. Executed 2026-09-27 in the main session.

**Corrected 2026-09-27 (ADJ-7), same day.** The original pass (§3, §4) imprecisely described the mixed-product and model-set questions in broader terms than METHODOLOGY actually supports — corrections are marked inline under "Corrected 2026-09-27 (ADJ-7)" headers; §7 and the "Added" subsections under §5 and §4 are new. No text was deleted outright; imprecise conclusions are struck by the corrected passages that immediately follow them.

## 1. Inventory of CRAEI's climate archive

Two locations, per CRAEI's `config/paths.local.yaml`:

- **Global raw cache** (`isimip_global_cache_dir`, `D:\Douglas\OUTROS\CRAEI_isimip_raw_cache`): 189 files, **347 GB** total. Permanent cache of the full-globe ISIMIP3b decadal NetCDF files as downloaded from `files.isimip.org`, kept per CRAEI's D26 decision (ample space on that drive) so re-cropping never re-downloads. Not natively country-cropped; GeoFREA would need to run its own crop step against these to use them directly, or use the per-country crops below.
- **Per-country crops** (`data_root/raw/climate/isimip3b`, on `C:`): 177 files on disk, **15 GB** total (manifest.json registers 171 of them with sha256; 6 are newer than the manifest's last write, see below). One merged NetCDF file per `model/experiment/variable/country` (already concatenated across the source's decadal chunks, not left as separate decade files).

Countries covered: **BRA, IND, PRT** (all three of GeoFREA's S-01 scope) — every present model/experiment/variable combination has all three, no partial country coverage.

Per-model file counts and volume (crops):

| Model | Files | Size |
|---|---|---|
| gfdl-esm4 | 33 | 2.94 GB |
| ipsl-cm6a-lr | 33 | 3.02 GB |
| mpi-esm1-2-hr | 36 | 3.23 GB |
| mri-esm2-0 | 36 | 3.22 GB |
| ukesm1-0-ll | 36 | 3.25 GB |

### Acquisition pipeline and the three storage locations

CRAEI's climate acquisition uses three distinct locations, confirmed against `config/paths.local.yaml` and, for staging, the live directory contents:

- **`C:` — `data/raw/climate/isimip3b/{model}/{scenario}/{variable}/`.** The final per-country crops (BRA, IND, PRT): already cut to each country's bbox and to the required years. Small, ~25-165 MB each. This is the product the rest of CRAEI's pipeline (and any GeoFREA reuse) actually consumes — it is what §1's 15 GB / 177-file count above describes.
- **`D:` — `Douglas/OUTROS/CRAEI_isimip_raw_cache/ISIMIP3b/...`.** The permanent cache of raw ISIMIP3b global files: full worldwide grid, not cropped, 1-2 GB each. Downloaded once and reused to crop any country without re-downloading. Lives on the external Seagate drive because the files are large and there is no need to keep them on the SSD once cropped. This is §1's 347 GB / 189-file global cache.
- **`C:` — `AppData/Local/CRAEI_staging`.** A temporary SSD staging area where an in-progress download is written live, so a multi-hour download never writes directly to the `D:` drive. Only after the file is validated does it move to the `D:` cache. **Confirmed live during this audit** (2026-09-27, ~18:25-18:28): two `.part` files for `ukesm1-0-ll historical tasmin` (the historical/global/daily 1991-2000 and 2001-2010 decadal chunks, ~2.1 GB and ~1.1 GB respectively, still being written) — this is the same `ukesm1-0-ll/historical/tasmin` combination §1 lists as missing from the per-country crops for all three countries, corroborating that acquisition is actively closing that exact gap right now.

Flow: **download global file → validate (h5py) → write to staging (SSD) → crop all 3 countries from the staged file → promote the file once to the permanent `D:` cache.** The crop step runs against the staged copy, not the final `D:` location, so the three countries' crops are produced together from a single staged download before that download is archived.

Expected full matrix is 5 models x 4 experiments x 3 variables x 3 countries = 180 files. **171 present, 9 missing** (manifest-registered; 6 additional files exist on disk unregistered — acquisition is actively in progress, see note below):

- `gfdl-esm4/ssp126/tasmax` — all 3 countries
- `ipsl-cm6a-lr/ssp585/pr` — all 3 countries
- `ukesm1-0-ll/historical/tasmin` — all 3 countries

**Acquisition is not finished and not frozen.** Manifest `registered_at` timestamps range from 2026-09-18T02:36 to **2026-09-27T15:25** (today) — i.e., newer than CRAEI's own `PROGRESS.json` (`updated: 2026-09-20`, C12 noted `in_progress`, "18/60 jobs" at that time). The archive is materially more complete now (171/180 var-experiment-country combinations) than CRAEI's last written status record reflects. This audit reports the file system as found; it does not update CRAEI's `PROGRESS.json` (out of scope, CRAEI is read-only to GeoFREA).

## 2. Variable-by-variable comparison against M-F1-04 / M-F1-05

M-F1-04 requires: monthly `rsds`, `tas`, `sfcWind` (historical + 3 SSPs) and daily `tasmax`, `pr` (historical reference + both windows). M-F1-05 requires ERA5 gust reanalysis.

| Variable | Required by | Present in CRAEI? |
|---|---|---|
| `rsds` | M-F1-04 (monthly, resource channel) | **Absent.** Zero references anywhere in CRAEI's config, code, or data. |
| `tas` | M-F1-04 (monthly, resource channel) | **Absent.** CRAEI has `tasmax`/`tasmin` only; plain `tas` does not exist in its dataset list, code, or on disk. |
| `sfcWind` | M-F1-04 (monthly, resource channel) | **Absent.** Zero references anywhere in CRAEI. |
| `tasmax` | M-F1-04 (daily, hazard channel) | **Present** — daily, ISIMIP3b bias-adjusted, 5 models, all 4 experiments (1 combination x 3 countries still downloading, see §1). |
| `pr` | M-F1-04 (daily, hazard channel) | **Present** — daily, ISIMIP3b bias-adjusted, 5 models, all 4 experiments (1 combination x 3 countries still downloading). |
| ERA5 gust | M-F1-05 | **Absent.** No ERA5 product of any kind in CRAEI's datasets, config, or data directories. |

CRAEI additionally carries `tasmin` (all 5 models, all 4 experiments, near-complete), which M-F1-04 does not require — it exists in CRAEI only to support Hargreaves PET (CRAEI's own hazard method), not a GeoFREA requirement.

**Plain statement:** CRAEI's archive satisfies zero of M-F1-04's three monthly resource-channel variables and zero of M-F1-05. It satisfies both of M-F1-04's daily hazard-channel variables in file terms (product caveat below), modulo the model-experiment-country cells still in flight (§7).

### Corrected 2026-09-27 (ADJ-7): what each variable actually computes

The original §3 below stated the mixed-product question in terms of "hazard-channel change factors" for `tasmax`/`pr`. **No such quantity exists in METHODOLOGY** — this was an imprecision, corrected here per action 1 of ADJ-7. Per-variable mapping to the item that actually consumes it:

| Variable | Channel | Consuming item | Quantity computed | Type |
|---|---|---|---|---|
| `rsds` | Resource (C1) | M-F4-03 | `delta_rsds = mean_window(rsds) / mean_ref(rsds)` | Ratio (multiplicative) |
| `sfcWind` | Resource (C1) | M-F4-03 | `delta_wind = mean_window(sfcWind) / mean_ref(sfcWind)` | Ratio (multiplicative) |
| `tas` | Resource (C1) | M-F4-03 | `dT = mean_window(tas) - mean_ref(tas)` | Difference (additive, K) |
| `tasmax` | Hazard (C2, extreme heat) | M-F4-05 | Per-cell, per-member context indicator (e.g., threshold-exceedance count/index) | Absolute value, not a ratio or difference against the reference period |
| `pr` | Hazard (C3, extreme precipitation) | M-F4-05 | Per-cell, per-member context indicator | Absolute value, not a ratio or difference against the reference period |

M-F4-03's formula list is explicit and closed: `delta_rsds`, `delta_wind`, `dT` — three resource-channel variables only. **No change factor is computed from `tasmax` or `pr`.** M-F4-06 confirms this at the output level: `forcing.parquet` carries exactly `cell_id`, `member`, `delta_rsds`, `dT`, `delta_wind` — no `tasmax`/`pr`-derived field. `tasmax` and `pr` instead feed M-F4-05's hazard indicators, written to the separate `hazard_context.parquet`, and M-F4-05 states plainly these are context indicators that "never enter regret or satisficing" unless OQ-007 resolves toward a Tier 1/2 loss function.

## 3. Product comparison: ISIMIP3b bias-adjusted vs. raw CMIP6 from the CDS

**ISIMIP3b** (CRAEI's product): daily `tasmax`, `tasmin`, `pr`, statistically bias-adjusted by the ISIMIP team against the **W5E5 v2.0** reanalysis using ISIMIP3BASD v2.5.0 (Lange 2019; Frieler et al. 2021). Every model's historical run is corrected to match observed climatology over the same reference period, so absolute thresholds and cross-model comparisons are meaningful without further work. Source: CRAEI's `docs/METHODS_SPEC.md`.

**Raw CMIP6 from the Copernicus CDS** (what M-F1-04 specifies): direct GCM output, **not** bias-adjusted against any reanalysis. Each model carries its own bias relative to observations, uncorrected.

### Corrected 2026-09-27 (ADJ-7): the mixed-product question, restated in its real scope

The resource channel (`rsds`, `sfcWind`, `tas`, M-F4-03) and the hazard channel (`tasmax`, `pr`, M-F4-05) are structurally different kinds of quantity, and the bias-adjustment question does not weigh on them the same way:

- **Resource channel — ratio/difference of the same product.** `delta_rsds`, `delta_wind`, and `dT` are each computed from one product's own `mean_window` and `mean_ref`. A uniform bias-adjustment applied identically to both periods of the same variable cancels to first order in a ratio or a difference. **Whether this product is bias-adjusted or raw matters little for the resource channel's own internal consistency** — a change factor from raw CDS CMIP6 is not, on that account, inferior to one from a bias-adjusted product, provided the same product is used for `mean_window` and `mean_ref` within a given model.
- **Hazard channel — an absolute value, not a ratio or a difference.** M-F4-05's context indicators are per-cell, per-member absolute quantities (e.g., a threshold-exceedance count on `tasmax`, an extreme-precipitation index on `pr`), not expressed relative to a reference period the way M-F4-03's change factors are. For an absolute physical threshold (e.g., "days above 35°C") to be meaningful, the underlying temperature values must themselves be realistic — this is exactly what bias-adjustment against an observational reference (W5E5) buys, and exactly what raw, uncorrected GCM output does not have. **Correction against observation is what makes the hazard channel's absolute threshold meaningful; it is not optional in the way it is for the resource channel's ratios.**

This reverses the original framing: it is **not** that resource and hazard channels are symmetric candidates for either product with a residual "channel consistency" concern between them. It is that the hazard channel specifically needs bias-adjustment (which is what CRAEI's ISIMIP3b archive already provides) and the resource channel does not strictly need it (bias cancels in its ratio/difference formulation) — so using bias-adjusted ISIMIP3b for the hazard channel and raw CDS CMIP6 for the resource channel is not an inconsistency to justify; if anything, it is closer to the technically correct pairing than using the same product for both would be.

**Does anything in METHODOLOGY compare a resource-channel value against a hazard-channel value directly?** No such quantity was found. M-F4-06's two outputs are kept separate (`forcing.parquet` for `delta_rsds`/`dT`/`delta_wind`; `hazard_context.parquet` for the hazard indicators) and nothing in F4-F7 combines a resource-channel number and a hazard-channel number into one computed quantity. The only place the two appear together is **T-R10** ("Hazard context exposure of nominal and robust top-k cells by SSP", `docs/METHODOLOGY.md` line 398): this is a report of which cells the resource-channel-driven ranking (LCOE/regret, itself downstream of `delta_rsds`/`dT`/`delta_wind` via F5-F7) selected, cross-tabulated against those same cells' hazard exposure. It is a side-by-side juxtaposition of two independently computed quantities for the same cells, never an arithmetic combination of the two into a single value. **Remaining question:** whether a *product* mismatch between the two channels is acceptable given the two are never arithmetically mixed — only read side by side in T-R10 — is restated as OQ-034 below, now scoped to this narrower concern plus the window problem in §5.

## 4. Model set vs. S-04

S-04: "CMIP6 GCM ensemble, minimum GFDL-ESM4 and MIROC6, target four to six models selected by protocol M-F4-02."

CRAEI's five models (its own ISIMIP3b "primary GCM" set, chosen for CRAEI's own reasons — see its `docs/METHODS_SPEC.md`): **GFDL-ESM4, IPSL-CM6A-LR, MPI-ESM1-2-HR, MRI-ESM2-0, UKESM1-0-LL.**

| S-04 requirement | In CRAEI's set? |
|---|---|
| GFDL-ESM4 (minimum) | Yes |
| MIROC6 (minimum) | **No** |

### Corrected 2026-09-27 (ADJ-7): the original §4 conflated two separate questions

S-04 states a requirement on "the CMIP6 GCM ensemble" without naming a channel. M-F4-02's selection protocol (criterion 1: "availability of all M-F1-04 variables for all experiments with one common realization") is written against **all of M-F1-04's variables together** — `rsds`, `tas`, `sfcWind` (resource) and `tasmax`, `pr` (hazard) — which is itself only satisfiable if a single source provides every variable per model. CRAEI provides two of the five. No wording in S-04, M-F4-01, or M-F4-02 restricts S-04's model-set requirement to the resource channel specifically, and none of M-F4-01 through M-F4-05 states that the resource and hazard channels must be sourced from the same product. What is actually true:

- The resource channel is sourced from the **CDS**, which is a live, open-ended CMIP6 archive — **MIROC6 is available there** for `rsds`/`tas`/`sfcWind`, so S-04's minimum is satisfiable for the resource channel regardless of what CRAEI holds. This audit did not need to check CRAEI for this, and finding MIROC6 absent from CRAEI is not evidence it is unmet for the resource channel.
- What CRAEI **cannot** provide is **MIROC6 in the hazard channel** (`tasmax`/`pr`, ISIMIP3b), because ISIMIP3b's own primary 5-model set (which CRAEI adopted wholesale) does not include MIROC6 at all — this is a property of the ISIMIP3b product, not a CRAEI acquisition gap that more downloading would close.

**Revised divergence cost:** none for the resource channel (S-04's minimum is satisfiable from the CDS independent of CRAEI). The actual, narrower cost is that reusing CRAEI's archive for the hazard channel means the hazard channel's model set is capped at CRAEI's 5 models, with no MIROC6 hazard indicator obtainable from that archive at all — MIROC6 is not in ISIMIP3b's primary set, so acquiring it for the hazard channel would mean a different bias-adjustment product (not ISIMIP3b) for that one model, or accepting a hazard channel with no MIROC6 member. This is restated as OQ-035 below, split from the resource-channel question this section originally (incorrectly) implied was also blocked.

### Added 2026-09-27 (ADJ-7, action 5): what "member" means if the two channels have different model sets

M-F4-01 defines `m = (gcm, ssp, window)`. Nothing in M-F4-01 through M-F4-05 ties this triple to one channel only — `forcing.parquet` (resource) and `hazard_context.parquet` (hazard) are both described as per-member outputs (M-F4-05: "computed as per-cell context indicators **per member**"; M-F4-06: `forcing.parquet` keyed by `cell_id`, `member`). So the member axis is shared vocabulary across both parquets, not a resource-only concept.

But a hazard indicator is computed from `tasmax`/`pr`, and that data is inherently per-model (CRAEI's own files are organized `model/experiment/variable/country` — there is no scenario-only, model-independent `tasmax`/`pr` series). **A hazard indicator is therefore necessarily attached to a member by `(gcm, ssp)` as a pair, the same as the resource channel — it cannot be attached by scenario alone**, because the underlying daily data it is computed from does not exist independent of a specific GCM.

The consequence, if the two channels' model sets diverge (§4: resource channel can include MIROC6 via the CDS, hazard channel cannot, if sourced from CRAEI's ISIMIP3b archive): **some members will have a `forcing.parquet` row with no corresponding `hazard_context.parquet` row** (any member whose `gcm` is MIROC6), and the reverse is not possible under this reuse option (CRAEI's 5 models are a subset of whatever set M-F4-02 selects for the resource channel, if M-F4-02 includes MIROC6 there). M-F4-05 already tolerates hazard indicators being partial/context-only (never entering regret or satisficing), so a member with no hazard row is not obviously a contract violation — but nothing in F4's contract (`docs/phases/F4_climate_forcing.md`) currently states whether `hazard_context.parquet` is expected to cover every member in `members.yaml`/`forcing.parquet`, or may have gaps for members the hazard channel's source product does not support. **This must be encoded in the F4 implementation** (task J-1's actual work) — specifically, `members.yaml`'s resolved member list either includes a hazard-availability flag per member, or the hazard channel's member subset is documented as a strict subset of the resource channel's, established before J-1 writes the schema rather than discovered during it.

## 5. Temporal windows vs. S-05

S-05: reference climatology 1995-2014; core window 2041-2070; sensitivity window 2071-2100.

Confirmed by reading file metadata directly (not CRAEI's config) on `gfdl-esm4` historical/ssp585 `tasmax` for BRA, IND, PRT:

| CRAEI file | Time span (file, read directly) |
|---|---|
| historical | 1984-01-01 to 2014-12-31 |
| ssp585 (future) | 2041-01-01 to 2070-12-31 |

| S-05 window | CRAEI coverage | Gap |
|---|---|---|
| Reference 1995-2014 | Contained inside CRAEI's 1984-2014 historical span | None — CRAEI's span fully covers the reference period (and more, 1984-1994 unused). |
| Core future 2041-2070 | Exact match | None. |
| Sensitivity future 2071-2100 | **Not present.** CRAEI's `config/datasets.yaml` `periods.future`/`download_years.future` are both hard-coded to 2041-2070; CRAEI has no acquisition target for 2071-2100 at all. | **Full gap** — GeoFREA's S-05 sensitivity window would need a separate download regardless of any reuse decision for the core window. |

### Added 2026-09-27 (ADJ-7, action 3): does ISIMIP3b publish 2071-2100 for these five models, and what would acquiring it cost?

**Yes.** CRAEI's own `docs/DECISIONS.md` (line 68) records, from when CRAEI inspected the source files: "ssp126/ssp370/ssp585 (all 5 models): file span 2015-2100, needed 2041-2070 — OK." ISIMIP3b's future-scenario files for all 5 of CRAEI's models span the full 2015-2100 period; CRAEI simply never downloaded the decadal chunks past 2070. Confirmed independently by listing `CRAEI_isimip_raw_cache`: only the `2041_2050`, `2051_2060`, `2061_2070` decadal files exist per model/scenario/variable; no `2071_2080`/`2081_2090`/`2091_2100` file exists anywhere in the cache.

**Cost, at CRAEI's own observed rate.** CRAEI measured `files.isimip.org` at **1.05 MB/s single-stream** (`docs/DECISIONS.md`, COMANDO 12 rework), confirmed server-side-throttled (a different host on the same connection transferred ~2-3x faster). Global decadal files for a given model/scenario/variable observed in the cache average ~2.08 GB each (measured directly: 30 decade-files for `2061_2070`, 2 variables x 5 models x 3 SSPs, averaged ~2.04 GB/file). For GeoFREA's two hazard-channel variables (`tasmax`, `pr`) only, across 5 models x 3 SSPs (2071-2100 has no historical experiment) x 3 decades:

- Volume: 5 models x 3 SSPs x 2 vars x 3 decades x ~2.04 GB/file ≈ **183 GB**.
- Time at 1.05 MB/s single-stream: 183 GB / 1.05 MB/s ≈ 174,300 s ≈ **~48 hours (~2 days)**, global download only — before any local crop, which does not add meaningfully to this figure (crop is CPU/IO-bound locally, not network-bound).
- If CRAEI's third variable (`tasmin`, not required by M-F1-04) is also wanted for parity with the existing archive: ≈ **274 GB**, ≈ **~73 hours (~3 days)**.

This is a download CRAEI has never attempted for this period, so no in-progress figure exists to check it against — the estimate above is derived entirely from CRAEI's own historical decade-file sizes and its own measured throughput, not from a new probe of `files.isimip.org`.

**Feeds back into OQ-034 (§ below):** M-F7-07's H1 explicitly repeats its SSP-pair comparison "for the 2071-2100 window as sensitivity." If the hazard channel's core window (2041-2070) comes from CRAEI's ISIMIP3b archive and the sensitivity window (2071-2100) is acquired separately — from ISIMIP3b again (same product, just the missing decades, per the cost above) or from a different source — the product-consistency question is no longer only a cross-channel one (§3): it becomes a **within-hazard-channel, within-test** question, since H1 compares the same hazard variable's rankings across the two windows in the same statistical test. Acquiring the missing decades from ISIMIP3b itself (the ~183 GB option above) avoids this by construction, since it is the same product as the core window; sourcing 2071-2100 from anywhere else would not.

## 6. Decision package (not a decision)

Three options found; costs and commitments only, no recommendation.

| Option | What it means | CDS download volume | CDS request count (rough) | What it commits the thesis to |
|---|---|---|---|---|
| **A — Reuse CRAEI's ISIMIP3b archive for the hazard channel (tasmax, pr); download the resource channel (rsds, tas, sfcWind) fresh from the CDS** | Hazard channel: 0 new download for the core window (subject to the 2 remaining model-experiment cells, §7). Resource channel: monthly rsds/tas/sfcWind, historical+3 SSPs, for whichever model set M-F4-02 selects, 3 countries. Sensitivity window (2071-2100): ~183 GB / ~2 days more from ISIMIP3b itself if kept same-product with the core window (§5), regardless of this option. | Monthly data only — roughly 1/30th the per-timestep volume of CRAEI's daily crops. Extrapolating from CRAEI's ~15 GB for 2 daily variables x ~57/60 combos: **rough estimate 2-5 GB** for 3 monthly variables x 4 experiments x 5 models x 3 countries. | 3 vars x 4 experiments x 5 models x 3 countries = **~180 requests** (or ~216 at 6 models) if the CDS is queried the same way CRAEI queried ISIMIP (one request per variable-experiment-model-country). | **(Corrected 2026-09-27, ADJ-7)** Does *not* commit to an inconsistency needing justification the way originally stated — §3's corrected analysis finds the hazard channel specifically needs bias-adjustment (which CRAEI provides) while the resource channel's ratio/difference formulation does not strictly need it, so this pairing is not an ad hoc mismatch. What it does commit to: (1) MIROC6 has no hazard-channel member obtainable from CRAEI's archive (§4, OQ-035); (2) the 2071-2100 sensitivity window, if drawn from ISIMIP3b too (§5), costs ~183 GB / ~2 days more, separate from this decision; if drawn from elsewhere, M-F7-07's H1 test would compare two windows of the same hazard variable from two different products within one test (§5, folded into OQ-034). |
| **B — Download everything from the CDS; use CRAEI only as code reference (per A-11), never its data** | Full M-F1-04 matrix (3 monthly + 2 daily variables) built fresh, one consistent raw-CMIP6 product for both channels, no mixed-product question. | All 5 variables x 4 experiments x model set x 3 countries, both windows. Daily variables dominate volume (CRAEI's 15 GB for 2 daily vars over one window pair is the closest comparable); adding the 2071-2100 window roughly doubles the future-period daily volume. **Rough estimate 25-35 GB** (15-20 GB daily analog to CRAEI's crops, plus ~2071-2100, plus a few GB monthly). | 5 vars x 4 experiments x 5-6 models x 3 countries = **~300-360 requests**, plus however many additional requests the 2071-2100 window needs if the CDS's CMIP6 catalog does not return both future windows in one experiment-level request. | No product mismatch, no A-11 adaptation debt beyond code. Loses the ~171 files and multi-day acquisition CRAEI has already run — this volume and request count would be paid again from zero, including the same slow-origin-server problem CRAEI documented (`files.isimip.org` ~1 MB/s) if the CDS turns out to have comparable throughput. Fully independent of CRAEI's model-selection precedent, so MIROC6 (S-04) is not a special case to solve. |
| **C — Reuse CRAEI's archive for the hazard channel now (as in A), and re-derive the same variables from the CDS later only if M-F4-05's C2/C3 loss-function work (OQ-007) needs a product consistent with a CDS-sourced C1** | Defers the mixed-product question until it is known whether C2/C3 actually enter F5/F6 quantitatively (OQ-007 gates this) or stay as context indicators (M-F4-05), in which case the mixed-product concern may never materialize for anything that enters regret or satisficing. | Same as A now (2-5 GB); a second, later, unbounded cost only if OQ-007 resolves toward quantitative C2/C3 use and the reviewer requires single-product consistency at that point. | Same as A now; unknown/deferred later cost. | Commits to revisiting this decision after OQ-007 resolves rather than closing it now — an explicit, recorded deferral rather than a silent one. |

Volume and request-count figures above are order-of-magnitude estimates from CRAEI's own observed file sizes and request pattern (one request per variable-experiment-model-country), not CDS API documentation figures — no CDS request has been made or inspected as part of this audit (read-only, F-3 not started).

## 7. CRAEI completion state at time of writing (added 2026-09-27, ADJ-7, action 7)

CRAEI's climate acquisition is still running. Re-inventoried at the time of this correction (2026-09-27, ~21:25 UTC, six hours after the original audit's 15:25 snapshot):

- **174 of 180** model x experiment x variable x country combinations now registered in the manifest (up from 171/180 at the original audit). The `ukesm1-0-ll/historical/tasmin` gap the original audit flagged as missing has closed for all 3 countries in the interim — confirming §1's "staging area live" observation was acquisition genuinely in progress, not stalled.
- **6 combinations remain missing** (2 model-experiment-variable cells x 3 countries each): `gfdl-esm4/ssp126/tasmax` and `ipsl-cm6a-lr/ssp585/pr`. Both are M-F1-04-relevant (unlike the `tasmin` gap that just closed, which GeoFREA does not need).
- **What remains is a crop, not a download, for both.** Checked directly against the `D:` global raw cache: the global decadal files for both remaining combinations (`gfdl-esm4` ssp126 tasmax 2041-2050/2051-2060/2061-2070; `ipsl-cm6a-lr` ssp585 pr 2041-2050/2051-2060/2061-2070) **already exist in full** in `CRAEI_isimip_raw_cache`. No further network download is needed for these two combinations — only CRAEI's local crop-to-country step, which is fast (minutes, not the hours/days a fresh global download takes).
- The staging area (`AppData/Local/CRAEI_staging`) is, as of this check, still writing the `ukesm1-0-ll historical tasmin` decadal files that just completed registration, or has moved on to the next queued job — the exact next job was not confirmed (would require re-polling staging, out of scope for a point-in-time audit).

**What this means for F-3 planning:** the archive will very likely be functionally complete for M-F1-04's daily hazard-channel variables (`tasmax`, `pr`, all 5 models, all 4 experiments, all 3 countries) within the time it takes CRAEI to run two local crop operations — not within the multi-day network-bound timeline the original audit's "acquisition in progress" framing might suggest for the remaining gap specifically. The multi-day timeline in §5's cost estimates concerns the *2071-2100 window*, which CRAEI has not started at all (§5), not the two combinations remaining from the core-window matrix.

## Open questions raised (rewritten 2026-09-27, ADJ-7)

Two entries in `docs/OPEN_QUESTIONS.md`, rewritten from their original (broader/imprecise) form to the scope actions 1-5 established (no resolution proposed either way):

- **OQ-034** (was: mixed-product question, resource vs. hazard channel) — **now scoped to**: (a) whether a hazard-channel absolute threshold indicator (tasmax/pr, needs bias-adjustment to be meaningful, §3) may legitimately use a different product than the resource-channel ratio/difference change factors (rsds/tas/sfcWind, does not strictly need bias-adjustment, §3) given the two are never arithmetically combined and only appear side by side in T-R10; and (b) whether the hazard channel's core window (2041-2070, from CRAEI's ISIMIP3b) and its sensitivity window (2071-2100, not yet acquired by anyone) must be the same product, since M-F7-07's H1 test compares the two windows directly (§5) — a genuine within-hazard-channel, within-test product-consistency question, not merely a cross-channel one.
- **OQ-035** (was: single model-set question) — **split into two** per action 4: (a) confirmed *not* a problem — S-04's MIROC6 minimum is satisfiable for the resource channel from the CDS regardless of CRAEI (MIROC6 is a live CDS-available CMIP6 model; CRAEI's absence of it is a property of ISIMIP3b's primary set, not a resource-channel constraint); (b) the real open question — whether the hazard channel may have no MIROC6 member at all (since ISIMIP3b's primary set excludes it entirely) while the resource channel does, and, per action 5, whether M-F4-01's member axis and the F4 outputs (`forcing.parquet`, `hazard_context.parquet`, `members.yaml`) are meant to tolerate a member with a resource row and no hazard row — undecided in the current F4 contract (`docs/phases/F4_climate_forcing.md`, conformance table still empty) and needed before J-1.

## Scope notes

- No file was copied out of `CRAEI_BASELINE_DIR` or its data directories.
- No file under `config/` or `src/` was edited.
- No commit was made.
- This audit does not update CRAEI's own `PROGRESS.json`, `DECISIONS.md`, or manifest — those are CRAEI's records, out of scope for a GeoFREA-side read-only audit.
- No CDS or ISIMIP download was made or initiated as part of this correction (ADJ-7); the §5 cost estimate for 2071-2100 is derived entirely from CRAEI's own already-recorded file sizes and throughput measurements.
