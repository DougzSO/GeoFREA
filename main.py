"""main.py — GeoFREA entry point.

Loads config/parameters.json + config/settings.yaml, resolves which
countries to run (RunConfig.countries empty = every country present in
parameters.json), and runs the orchestrator's registered phases for
each. The orchestrator itself (src/geofrea/core/orchestrator.py) is
generic and does not need redesigning as phases are added.

data_acquisition -> data_quality_audit wiring (2026-08-25, see
DECISIONS.md same date - data_acquisition activation): the audit
PhaseSpec's `run` is now a per-context closure (_audit_run below), not
a functools.partial with a hardcoded AuditInputs() — it reads
context.prior_results["data_acquisition"].output at call time (a
partial can't do this: it binds `inputs` before any phase has run) and
converts it via geofrea.data_acquisition.adapter's
acquisition_result_to_audit_inputs(). When data_acquisition did not run
this pipeline (disabled in settings.yaml, standalone audit run),
_build_audit_inputs() falls back to AuditInputs() empty, unchanged from
the prior skeleton-stage behavior.

UnwiredPhasesError, which used to block enabling data_acquisition and
data_quality_audit together, was REMOVED this same stage (not relaxed
to a warning, not kept) — see DECISIONS.md 2026-08-25 for the full
rationale. Summary: its only justification was that audit would
silently run against a hardcoded-empty AuditInputs regardless of what
data_acquisition produced; now that the two are genuinely wired, that
is no longer true — layers without a real fetch yet correctly surface
as `None`/missing in the audit report (inspect_raster()/
inspect_vector_layer() already handle that gracefully), which is the
audit doing its job, not a misleading run.

grid_alignment wiring (2026-09-08, see DECISIONS.md same date - grid_
alignment orchestrator wiring): registered as the THIRD PhaseSpec, but
its `run` closure reads ONLY context.prior_results["data_acquisition"]
— never data_quality_audit's. This was a deliberate design decision
closed in an earlier stage of this same session (Passo 1 of the
grid_alignment port): grid_alignment must keep working with
data_quality_audit disabled in settings.yaml, paying at most a cold
clip-cache cost, never failing outright. List position (third, after
data_quality_audit) is about readable pipeline ordering only — it does
NOT imply a data dependency the same way data_acquisition ->
data_quality_audit's position does. Same per-context-closure pattern as
_audit_run below, not a functools.partial with eagerly-bound inputs —
that eager-binding shape is exactly what UnwiredPhasesError was
protecting against in 2026-08-25 (see that DECISIONS.md entry): a
partial can only bind inputs that already exist when
_build_phase_specs() runs, before ANY phase has executed, which is
correct for data_acquisition (no phase-specific inputs at all) but
would be wrong here — grid_alignment's inputs (AcquisitionResult) only
exist once the orchestrator has actually run that phase for this
country.

Usage:
    python main.py PRT              # one country, every phase in settings.yaml's target_phases
    python main.py PRT BRA IND      # several, one after the other
    python main.py BRA --phases grid_alignment --rerun grid_alignment
    python main.py                  # run.countries from settings.yaml, else every thesis country
"""

from __future__ import annotations

import json
import logging
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

from geofrea.climate_forcing.external_inputs import ExternalInputsReport, check_external_inputs
from geofrea.climate_forcing.pipeline import (
    ForcingSummary,
    HazardSummary,
    MapsSummary,
    build_forcing,
    build_hazard_context,
    build_maps,
)
from geofrea.core.config_loader import (
    load_audit_config,
    load_countries,
    load_experiments,
    load_parameters,
    load_settings,
    load_technologies,
)
from geofrea.core.geo_utils import load_mainland_boundary
from geofrea.core.orchestrator import (
    Orchestrator,
    PhaseContext,
    PhaseSpec,
    compute_dirty,
    compute_git_commit,
    compute_run_id,
)
from geofrea.core.paths import log_path, outputs_dir, phase_dir
from geofrea.core.production import (
    ConfigConsistencyError,
    ProductionRunError,
    audit_parameters,
    enforce_production,
    validate_registry,
    validate_run_technologies,
)
from geofrea.core.run_logging import configure_logging, render_run_table
from geofrea.core.scale import DEFAULT_SCALE, SCALES, active_scale, use_scale
from geofrea.core.schemas import ResolutionsConfig, SettingsFile
from geofrea.data_acquisition.adapter import acquisition_result_to_audit_inputs
from geofrea.data_acquisition.fetchers.wind import GWA_HEIGHTS_M, GWA_PRODUCTS
from geofrea.data_acquisition.phase import DataAcquisitionLayerFailedError, run_acquisition_phase
from geofrea.data_acquisition.schemas import AcquisitionResult, resolved_path
from geofrea.data_quality_audit.audit import run_audit_phase
from geofrea.data_quality_audit.schemas import AuditConfig, AuditInputs, AuditResult
from geofrea.grid_alignment.adapter import (
    GridAlignmentRequiresBordersError,
    acquisition_result_to_grid_alignment_inputs,
)
from geofrea.grid_alignment.alignment import run_grid_alignment_phase
from geofrea.grid_alignment.reference_grid import write_reference_grid_artifact
from geofrea.grid_alignment.schemas import GridAlignmentInputs, GridAlignmentResult
from geofrea.land_eligibility.pipeline import EligibilitySummary, build_eligibility
from geofrea.land_eligibility.scenarios import LAND_SCENARIOS
from geofrea.lcoe_modeling.convergence import ConvergenceSummary, build_convergence
from geofrea.lcoe_modeling.pipeline import LcoeSummary, build_lcoe
from geofrea.lcoe_modeling.table_schemas import LCOE_TABLE_SCHEMA_VERSION
from geofrea.overview.figures import OverviewSummary, build_overview
from geofrea.robustness_analysis.pipeline import ROW_MODELS, RobustnessSummary, build_robustness
from geofrea.robustness_analysis.table_schemas import ROBUSTNESS_TABLE_SCHEMA_VERSION
from geofrea.siting_layers.physical_layers import SitingLayersResult, build_physical_layers
from geofrea.technical_potential.maps import PotentialMapsSummary, build_potential_maps
from geofrea.technical_potential.pipeline import PotentialSummary, build_potential
from geofrea.technical_potential.table_schemas import POTENTIAL_TABLE_SCHEMA_VERSION

logger = logging.getLogger("geofrea.main")

REPO_ROOT = Path(__file__).resolve().parent

# Loaded before any geofrea.core.paths helper can run (those raise
# MissingPathEnvironmentError if their variable isn't set yet).
# override=False: a variable already set in the process environment
# wins over .env, so an operator can still override per-invocation.
load_dotenv(REPO_ROOT / ".env", override=False)

COUNTRIES_YAML = REPO_ROOT / "config" / "countries.yaml"
PARAMETERS_JSON = REPO_ROOT / "config" / "parameters.json"
SETTINGS_YAML = REPO_ROOT / "config" / "settings.yaml"
AUDIT_YAML = REPO_ROOT / "config" / "audit.yaml"
EXPERIMENTS_YAML = REPO_ROOT / "config" / "experiments.yaml"
TECHNOLOGIES_YAML = REPO_ROOT / "config" / "technologies.yaml"
POWER_CURVES_DIR = REPO_ROOT / "config" / "power_curves"
METHODOLOGY_MD = REPO_ROOT / "docs" / "METHODOLOGY.md"

_METHODOLOGY_VERSION_RE = re.compile(r"^\|\s*Version\s*\|\s*([0-9.]+)\s*\|\s*$", re.MULTILINE)


def _read_methodology_version(path: Path) -> str:
    """Parse the `| Version | x.y.z |` row from METHODOLOGY.md's header table."""
    match = _METHODOLOGY_VERSION_RE.search(path.read_text(encoding="utf-8"))
    if match is None:
        raise RuntimeError(f"Could not find a Version row in {path}.")
    return match.group(1)


def _register_json_artifact(
    context: PhaseContext, key: str, output: BaseModel, schema_version: str = "1.0"
) -> None:
    """Dump `output` as JSON and register it as the artifact identified by `key`.

    Each migrated phase's real outputs already exist on disk as
    individual rasters/vectors, written by that phase's own code
    (unchanged here). This JSON dump is a single, hashable, resumable
    artifact file representing the whole phase output for the artifact
    registry (METHODOLOGY A-02) — it does not replace or duplicate the
    underlying raster/vector writers.
    """
    artifact_dir = context.outputs_dir / context.country_code / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / f"{key}.json"
    path.write_text(output.model_dump_json(indent=2), encoding="utf-8")
    context.register_artifact(key, path, schema_version)


def _summarize_acquisition(output: AcquisitionResult) -> str:
    """F1 completion summary: layer counts by resolution_status (COMMAND ADJ-7 action 3)."""
    counts = Counter(layer.resolution_status for layer in output.layers)
    return ", ".join(f"{status}={count}" for status, count in sorted(counts.items()))


def _summarize_audit(output: AuditResult) -> str:
    """F1b completion summary: audited/not_audited counts, alerts named (COMMAND ADJ-7 action 3)."""
    n_layers = len(output.rasters) + len(output.vectors)
    n_not_audited = len(output.not_audited)
    n_audited = n_layers - n_not_audited
    alerts_part = f"; alerts: {output.alerts}" if output.alerts else "; no alerts"
    return f"{n_audited} audited, {n_not_audited} not_audited{alerts_part}"


def _summarize_grid_alignment(output: GridAlignmentResult) -> str:
    """F2a completion summary: raster dimensions and grid origin (COMMAND ADJ-7 action 3)."""
    meta = output.grid_metadata
    origin_x, origin_y = meta.transform[2], meta.transform[5]
    return (
        f"{meta.width}x{meta.height} px, resolution {meta.resolution_deg} deg, "
        f"origin ({origin_x:.4f}, {origin_y:.4f}), crs {meta.crs}"
    )


def _build_audit_inputs(context: PhaseContext) -> AuditInputs:
    """Build AuditInputs from data_acquisition's output, if it ran this pipeline.

    data_quality_audit can also run standalone (data_acquisition
    disabled in settings.yaml) — e.g. an ad hoc audit of manually
    placed local files. In that case there is nothing in
    context.prior_results to adapt, so this falls back to AuditInputs()
    empty, exactly as main.py behaved before data_acquisition had any
    real fetch logic.

    Args:
        context: The audit phase's PhaseContext, as passed by
            Orchestrator.run() — prior_results contains every
            successfully-completed earlier phase's PhaseResult
            (resumed-from-manifest or freshly run, no distinction here).

    Returns:
        Real AuditInputs adapted from data_acquisition's output, or
        AuditInputs() empty if data_acquisition did not run.
    """
    acquisition_result = context.prior_results.get("data_acquisition")
    if acquisition_result is None or acquisition_result.output is None:
        return AuditInputs()
    return acquisition_result_to_audit_inputs(acquisition_result.output)


_AUDIT_REPORT_SCHEMA_VERSION = "2.1"  # bumped 2026-09-22: AuditResult gained
# the required `not_audited` field (M-F1b-01, config/audit.yaml — see
# docs/phases/F1b_data_quality_audit.md D-F1b-002). Previous bump,
# 2026-09-21: VectorLayerSummary.status gained read_error/
# processing_error, replacing the single "error" value (see
# docs/phases/core.md). An old "2.0" (or "1.0") audit_report entry
# cannot be reconstructed into the current AuditResult schema, so a
# stale one must be rejected on resume (StaleManifestEntryError via
# produces_schema_versions below), not silently misvalidated.


def _audit_run(context: PhaseContext, audit_config: AuditConfig) -> AuditResult:
    result = run_audit_phase(
        context, inputs=_build_audit_inputs(context), audit_config=audit_config
    )
    _register_json_artifact(context, "audit_report", result, _AUDIT_REPORT_SCHEMA_VERSION)
    return result


def _build_grid_alignment_inputs(
    context: PhaseContext, resolutions: ResolutionsConfig, distance_cap_km: float
) -> GridAlignmentInputs:
    """Build GridAlignmentInputs from data_acquisition's output.

    No RuntimeError guard here (removed 2026-09-21, see docs/phases/
    core.md D-core-001): grid_alignment's PhaseSpec declares
    requires={"layer_registry"}, produced only by data_acquisition, so
    the orchestrator's graph validation and dependency-skip logic
    (Orchestrator.run()) already guarantee data_acquisition succeeded
    before this closure is ever called — the DAG covers what the
    RuntimeError used to guard against.

    Args:
        context: The grid_alignment phase's PhaseContext, as passed by
            Orchestrator.run().
        resolutions: settings.yaml's `geospatial.resolutions` (see
            docs/DECISIONS.md 2026-09-09, grid_alignment Passo 4 item 3).

    Returns:
        Real GridAlignmentInputs adapted from data_acquisition's output.

    Raises:
        GridAlignmentRequiresBordersError: If data_acquisition ran but
            its AcquisitionResult has no usable `borders` layer (see
            grid_alignment/adapter.py).
    """
    acquisition_output = context.prior_results["data_acquisition"].output
    return acquisition_result_to_grid_alignment_inputs(
        acquisition_output, resolutions, distance_cap_km
    )


_LAYER_REGISTRY_SCHEMA_VERSION = "1.1"  # bumped 2026-09-23: AcquiredLayer
# gained source_sha256/source_sha256_skipped_reason (docs/phases/core.md
# D-core-016, resolving OQ-024). Both are optional with a None default,
# so an existing "1.0" layer_registry.json still deserializes into the
# current AcquisitionResult without error — this bump does not reject
# old data on load, it only stops data_acquisition itself from being
# *resumed* against a "1.0"-recorded entry (StaleManifestEntryError,
# same mechanism as _AUDIT_REPORT_SCHEMA_VERSION above), forcing a real
# rerun next time so BRA/PRT/IND's existing manifests pick up real
# hashes instead of silently staying null forever.


def _data_acquisition_run(context: PhaseContext) -> AcquisitionResult:
    result = run_acquisition_phase(context)
    _register_json_artifact(context, "layer_registry", result, _LAYER_REGISTRY_SCHEMA_VERSION)
    failed_layer_names = [
        layer.layer_name for layer in result.layers if layer.resolution_status == "failed"
    ]
    if failed_layer_names:
        # Raised AFTER registering the artifact above: the orchestrator's
        # per-phase exception handling persists whatever's already
        # registered on the context before recording status="failed"
        # (see Orchestrator.run(), the except branch) — see
        # DataAcquisitionLayerFailedError's docstring for why this order
        # matters (A-02 registry vs. A-09 dependents-stop contract).
        raise DataAcquisitionLayerFailedError(context.country_code, failed_layer_names)
    return result


# GridAlignmentResult's raster fields registered individually (METHODOLOGY
# A-02, 2026-09-21 — see docs/phases/core.md D-core-003). All 11 fields,
# which real F1 data resolves for every country currently in scope (PRT,
# BRA; see docs/PROGRESS.json). The seismic hazard layer was removed
# entirely per METHODOLOGY S-08 (see docs/phases/core.md F6-2).
_ALIGNED_RASTER_LAYER_KEYS = (
    "elevation",
    "slope",
    "solar",
    "land_cover",
    "land_cover_counts",
    "slope_counts",
    "population",
    "roads",
    "grid",
    "lakes",
    "rivers",
    "roads_distance_capped",
    "grid_distance_capped",
    "rivers_distance_capped",
)


# Per-height wind layers (M-F2a-04): "<product>_<height>m" for every GWA product and height; each aligned
# raster is its own artifact "aligned/wind_<product>_<height>m".
_WIND_LAYER_KEYS = tuple(f"{p}_{h}m" for p in GWA_PRODUCTS for h in GWA_HEIGHTS_M)


def _register_aligned_rasters(context: PhaseContext, result: GridAlignmentResult) -> None:
    """Register each of grid_alignment's raster outputs as its own artifact.

    A layer that resolved to None (no source data for this country) is
    not registered — see _ALIGNED_RASTER_LAYER_KEYS' docstring note for
    why this is safe for PRT/BRA today, and the known limitation this
    creates for a future country missing one of these layers (recorded
    in docs/phases/core.md Known issues).
    """
    for layer_key in _ALIGNED_RASTER_LAYER_KEYS:
        path = getattr(result, layer_key)
        if path is not None:
            context.register_artifact(f"aligned/{layer_key}", path, "1.0")
    for wind_key, path in result.wind_layers.items():
        context.register_artifact(f"aligned/wind_{wind_key}", path, "1.0")
    # the grid definition, as its own artifact: F4 reads only the grid, so it requires this and not the aligned layers
    if (
        result.grid is not None
    ):  # absent only in a stub; the phase's `produces` makes a missing key fail loud
        grid_definition = write_reference_grid_artifact(
            result.grid,
            context.outputs_dir / context.country_code / "artifacts" / "reference_grid.json",
        )
        context.register_artifact("reference_grid", grid_definition, "1.0")


def _build_phase_specs(
    resolutions: ResolutionsConfig,
    distance_cap_km: float,
    audit_config: AuditConfig,
    technologies: tuple[str, ...] = (),
    production: bool = False,
    figures: str = "all",
    max_batch_gb: float | None = None,
) -> list[PhaseSpec]:
    """Registered phases, with their requires/produces artifact contracts.

    Execution order is no longer this list's order: the Orchestrator
    derives it from each PhaseSpec's requires/produces (METHODOLOGY
    A-01, docs/phases/core.md D-core-001). data_quality_audit and
    grid_alignment both require only "layer_registry" (data_acquisition's
    output) — neither requires the other's output, preserving the
    independence grid_alignment's own closure has always relied on (see
    _build_grid_alignment_inputs, which reads only
    context.prior_results["data_acquisition"]).

    grid_alignment registers one artifact per raster field
    ("aligned/<layer>", see _ALIGNED_RASTER_LAYER_KEYS) plus the
    "aligned_rasters" JSON summary of the whole GridAlignmentResult.
    data_acquisition and data_quality_audit still register only their
    own output-model summary ("layer_registry", "audit_report") — F1's
    AcquiredLayer entries have no per-layer content to hash beyond the
    resolved path itself (see OQ-024, docs/OPEN_QUESTIONS.md).

    Args:
        resolutions: settings.yaml's `geospatial.resolutions`, closed
            over by grid_alignment's run closure (2026-09-09, see
            docs/DECISIONS.md same date, grid_alignment Passo 4 item 3).
        audit_config: config/audit.yaml, closed over by
            data_quality_audit's run closure (M-F1b-01).
        technologies: settings.yaml's `run.technologies`, closed over by technical_potential
            (F5), whose `produces` names one artifact per technology and land scenario.
        production: whether this is a production run; F5 refuses a synthetic power curve in one.
        figures: settings.yaml's `figures` (A-08), closed over by potential_maps.
        max_batch_gb: settings.yaml's `memory.max_batch_gb` (A-10), closed over by lcoe_modeling; the phase raises
            if it is absent (no silent default).

    Returns:
        The registered PhaseSpecs.
    """

    def data_quality_audit_run(context: PhaseContext) -> AuditResult:
        return _audit_run(context, audit_config)

    def grid_alignment_run(context: PhaseContext) -> GridAlignmentResult:
        result = run_grid_alignment_phase(
            context, inputs=_build_grid_alignment_inputs(context, resolutions, distance_cap_km)
        )
        _register_json_artifact(context, "aligned_rasters", result)
        _register_aligned_rasters(context, result)
        return result

    def siting_layers_run(context: PhaseContext) -> SitingLayersResult:
        """F2b (H-4): cost-driver and resource layers in physical units, from the aligned rasters."""
        grid_output = context.prior_results["grid_alignment"].output
        layers = build_physical_layers(
            grid_output, phase_dir(context.country_code, "siting_layers", "artifacts")
        )
        result = SitingLayersResult(country_code=context.country_code, layers=layers)
        _register_json_artifact(context, "siting_layers", result)
        return result

    def land_eligibility_run(context: PhaseContext) -> EligibilitySummary:
        """F3: eligibility per technology, 0.05 degree cells, candidate tables (nominal land-availability parameters)."""
        acquisition = context.prior_results["data_acquisition"].output
        layers = {layer.layer_name: layer for layer in acquisition.layers}
        borders = resolved_path(layers.get("borders"))
        if borders is None:
            raise GridAlignmentRequiresBordersError(
                f"land_eligibility requires a resolved 'borders' layer for {context.country_code!r}"
            )
        result = build_eligibility(
            context.country_code,
            EXPERIMENTS_YAML,
            context.prior_results["grid_alignment"].output,
            context.prior_results["siting_layers"].output,
            load_mainland_boundary(borders),
            resolved_path(layers.get("protected")),
            resolved_path(layers.get("lakes")),
            resolved_path(layers.get("rivers")),
            resolved_path(layers.get("admin1")),
        )
        _register_json_artifact(context, "land_eligibility", result)
        return result

    def external_inputs_run(context: PhaseContext) -> ExternalInputsReport:
        """Check the CMIP6, ISIMIP3b and ERA5 files acquired by scripts (registry, existence, hashes)."""
        report = check_external_inputs(context.country_code, EXPERIMENTS_YAML)
        _register_json_artifact(context, "external_inputs", report)
        return report

    def climate_forcing_run(context: PhaseContext) -> ForcingSummary:
        """F4 (J-3): per-cell change factors for every member, the masked cell-members and members.yaml."""
        result = build_forcing(context.country_code, EXPERIMENTS_YAML)
        context.register_artifact("forcing", result.forcing, "1.0")
        context.register_artifact("forcing_masked", result.forcing_masked, "1.0")
        context.register_artifact("members", result.members, "1.0")
        return result

    def hazard_context_run(context: PhaseContext) -> HazardSummary:
        """F4 (J-4): hazard context indicators for the members that carry the hazard channel."""
        result = build_hazard_context(context.country_code, EXPERIMENTS_YAML)
        context.register_artifact("hazard_context", result.hazard_context, "1.0")
        return result

    def climate_maps_run(context: PhaseContext) -> MapsSummary:
        """F4 (J-5): one diagnostic map per member."""
        result = build_maps(context.country_code, figures)
        _register_json_artifact(context, "climate_maps", result)
        return result

    def technical_potential_run(context: PhaseContext) -> PotentialSummary:
        """F5: capacity, capacity factor and energy per cell, member and land scenario; fails loudly while parameters are absent."""
        result = build_potential(
            context.country_code,
            load_technologies(TECHNOLOGIES_YAML),
            context.require_country_params("technologies"),
            technologies,
            EXPERIMENTS_YAML,
            POWER_CURVES_DIR,
            audit_config=load_audit_config(AUDIT_YAML),
            production=production,
        )
        for tech, potential in result.technologies.items():
            for scenario, entry in potential.scenarios.items():
                context.register_artifact(
                    f"potential_{tech}__{scenario}", entry.path, POTENTIAL_TABLE_SCHEMA_VERSION
                )
            context.register_artifact(
                f"potential_aggregates_{tech}", potential.aggregates, POTENTIAL_TABLE_SCHEMA_VERSION
            )
        _register_json_artifact(context, "technical_potential", result)
        return result

    def lcoe_modeling_run(context: PhaseContext) -> LcoeSummary:
        """F6: LCOE summaries, design matrix and nominal supply curves per technology; fails loudly while parameters are absent."""
        if max_batch_gb is None:
            raise RuntimeError("lcoe_modeling needs settings.yaml memory.max_batch_gb (A-10)")
        sampler = load_experiments(EXPERIMENTS_YAML).sampler
        result = build_lcoe(
            context.country_code,
            load_technologies(TECHNOLOGIES_YAML),
            context.require_country_params("technologies"),
            technologies,
            sampler_seed=sampler.seed,
            sampler_size=sampler.initial_size,
            max_batch_gb=max_batch_gb,
            production=production,
        )
        for tech, entry in result.technologies.items():
            context.register_artifact(
                f"lcoe_summary_{tech}", entry.lcoe_summary, LCOE_TABLE_SCHEMA_VERSION
            )
            context.register_artifact(
                f"design_matrix_{tech}", entry.design_matrix, LCOE_TABLE_SCHEMA_VERSION
            )
            context.register_artifact(
                f"supply_curve_{tech}", entry.supply_curve, LCOE_TABLE_SCHEMA_VERSION
            )
            for scenario, path in entry.lcoe_nominal_scenarios.items():
                context.register_artifact(
                    f"lcoe_nominal_{tech}__{scenario}", path, LCOE_TABLE_SCHEMA_VERSION
                )
        _register_json_artifact(context, "lcoe_modeling", result)
        return result

    def sample_size_convergence_run(context: PhaseContext) -> ConvergenceSummary:
        """F6 support (U-04, D-F6-004): double the Latin hypercube size until the top-k sets agree; needs ranges and the author's values."""
        if max_batch_gb is None:
            raise RuntimeError(
                "sample_size_convergence needs settings.yaml memory.max_batch_gb (A-10)"
            )
        experiments = load_experiments(EXPERIMENTS_YAML)
        core = experiments.windows["core"]
        result = build_convergence(
            context.country_code,
            load_technologies(TECHNOLOGIES_YAML),
            context.require_country_params("technologies"),
            technologies,
            sampler=experiments.sampler,
            thresholds=experiments.thresholds,
            core_window=f"{core['start_year']}-{core['end_year']}",
            max_batch_gb=max_batch_gb,
        )
        for tech, entry in result.technologies.items():
            context.register_artifact(
                f"sample_size_convergence_{tech}", entry.table, LCOE_TABLE_SCHEMA_VERSION
            )
        _register_json_artifact(context, "sample_size_convergence", result)
        return result

    def robustness_analysis_run(context: PhaseContext) -> RobustnessSummary:
        """F7: regret, satisficing and the rankings over the F7 set; fails loudly while parameters or CF_min are absent."""
        if max_batch_gb is None:
            raise RuntimeError("robustness_analysis needs settings.yaml memory.max_batch_gb (A-10)")
        result = build_robustness(
            context.country_code,
            load_technologies(TECHNOLOGIES_YAML),
            context.require_country_params("technologies"),
            technologies,
            load_experiments(EXPERIMENTS_YAML),
            max_batch_gb=max_batch_gb,
            scale_id=active_scale().scale_id,
            production=production,
        )
        for tech, entry in result.technologies.items():
            for role, window in entry.windows.items():
                for kind, path in window.tables.items():
                    context.register_artifact(
                        f"{kind}_{tech}__{role}", path, ROBUSTNESS_TABLE_SCHEMA_VERSION
                    )
        _register_json_artifact(context, "robustness_analysis", result)
        return result

    def potential_maps_run(context: PhaseContext) -> PotentialMapsSummary:
        """F5 (D-F5-015): COG of potential density and capacity factor at m0 (central scenario) and the T-R1 figure."""
        result = build_potential_maps(context.country_code, technologies, figures)
        for key, path in result.rasters.items():
            context.register_artifact(key, path, "1.0")
        _register_json_artifact(context, "potential_maps", result)
        return result

    def overview_run(context: PhaseContext) -> OverviewSummary:
        """Overview figures and tables of the country's pipeline state (visual QC, no new result)."""
        result = build_overview(context.country_code, figures)
        _register_json_artifact(context, "overview", result)
        return result

    return [
        PhaseSpec(
            name="data_acquisition",
            output_model=AcquisitionResult,
            run=_data_acquisition_run,
            requires=frozenset(),
            produces=frozenset({"layer_registry"}),
            produces_schema_versions={"layer_registry": _LAYER_REGISTRY_SCHEMA_VERSION},
            summarize=_summarize_acquisition,
        ),
        PhaseSpec(
            name="data_quality_audit",
            output_model=AuditResult,
            run=data_quality_audit_run,
            requires=frozenset({"layer_registry"}),
            produces=frozenset({"audit_report"}),
            produces_schema_versions={"audit_report": _AUDIT_REPORT_SCHEMA_VERSION},
            summarize=_summarize_audit,
        ),
        PhaseSpec(
            name="grid_alignment",
            output_model=GridAlignmentResult,
            run=grid_alignment_run,
            requires=frozenset({"layer_registry"}),
            produces=frozenset({"aligned_rasters", "reference_grid"})
            | {f"aligned/{key}" for key in _ALIGNED_RASTER_LAYER_KEYS}
            | {f"aligned/wind_{key}" for key in _WIND_LAYER_KEYS},
            summarize=_summarize_grid_alignment,
        ),
        PhaseSpec(
            name="external_inputs",
            output_model=ExternalInputsReport,
            run=external_inputs_run,
            requires=frozenset(),
            produces=frozenset({"external_inputs"}),
            summarize=lambda out: (
                f"{out.cmip6_files} CMIP6, {out.isimip3b_files} ISIMIP3b, {out.era5_files} ERA5 files present and registered"
            ),
        ),
        PhaseSpec(
            name="siting_layers",
            output_model=SitingLayersResult,
            run=siting_layers_run,
            requires=frozenset(
                {"audit_report", "aligned/grid", "aligned/roads", "aligned/solar"}
                | {
                    f"aligned/wind_{product}_{h}m"
                    for product in ("weibull_a", "weibull_k", "air_density")
                    for h in (100, 150, 200)
                }
            ),
            produces=frozenset({"siting_layers"}),
            summarize=lambda out: f"{len(out.layers)} physical-unit layers",
        ),
        PhaseSpec(
            name="land_eligibility",
            output_model=EligibilitySummary,
            run=land_eligibility_run,
            requires=frozenset(
                {
                    "siting_layers",
                    "layer_registry",
                    "audit_report",
                    "aligned/land_cover_counts",
                    "aligned/slope_counts",
                    "aligned/population",
                    "aligned/grid",
                    "aligned/grid_distance_capped",
                    "aligned/roads_distance_capped",
                }
            ),
            produces=frozenset({"land_eligibility"}),
            summarize=lambda out: "; ".join(
                f"{t}: {s.n_candidates:,} candidate cells, {100 * s.eligible_share:.1f}% of the land eligible"
                for t, s in out.technologies.items()
            ),
        ),
        PhaseSpec(
            name="climate_forcing",
            output_model=ForcingSummary,
            run=climate_forcing_run,
            requires=frozenset({"reference_grid", "audit_report", "external_inputs"}),
            produces=frozenset({"forcing", "forcing_masked", "members"}),
            summarize=lambda out: (
                f"{out.n_cells} cells x {out.n_members} members = {out.n_rows} rows; "
                f"{out.n_masked_cell_members} masked cell-members"
            ),
        ),
        PhaseSpec(
            name="technical_potential",
            output_model=PotentialSummary,
            run=technical_potential_run,
            requires=frozenset({"land_eligibility", "forcing", "forcing_masked", "members"}),
            produces=frozenset({"technical_potential"})
            | {
                f"potential_{tech}__{scenario}"
                for tech in technologies
                for scenario in LAND_SCENARIOS
            }
            | {f"potential_aggregates_{tech}" for tech in technologies},
            summarize=lambda out: "; ".join(
                f"{t}: "
                + ", ".join(f"{s} {e.p_gw_reference:.3g} GW" for s, e in p.scenarios.items())
                for t, p in out.technologies.items()
            ),
        ),
        PhaseSpec(
            name="lcoe_modeling",
            output_model=LcoeSummary,
            run=lcoe_modeling_run,
            requires=frozenset({"land_eligibility", "forcing", "members"})
            | {
                f"potential_{tech}__{scenario}"
                for tech in technologies
                for scenario in LAND_SCENARIOS
            },
            produces=frozenset({"lcoe_modeling"})
            | {
                f"{kind}_{tech}"
                for tech in technologies
                for kind in ("lcoe_summary", "design_matrix", "supply_curve")
            }
            | {
                f"lcoe_nominal_{tech}__{scenario}"
                for tech in technologies
                for scenario in LAND_SCENARIOS[1:]
            },
            summarize=lambda out: "; ".join(
                f"{t}: {e.n_rows} cell-members, {e.n_samples} samples, "
                f"nominal LCOE at m0 median {e.lcoe_nominal_m0_median} USD/MWh"
                for t, e in out.technologies.items()
            ),
        ),
        PhaseSpec(
            name="sample_size_convergence",
            output_model=ConvergenceSummary,
            run=sample_size_convergence_run,
            requires=frozenset({"land_eligibility", "forcing", "members"})
            | {f"potential_{tech}__central" for tech in technologies},
            produces=frozenset({"sample_size_convergence"})
            | {f"sample_size_convergence_{tech}" for tech in technologies},
            summarize=lambda out: "; ".join(
                f"{t}: "
                + (
                    f"adopted {e.adopted_size} samples"
                    if e.converged
                    else f"NOT converged by {e.sizes[-1]} samples"
                )
                + f" (provisional MR, {e.n_cells} cells)"
                for t, e in out.technologies.items()
            ),
        ),
        PhaseSpec(
            name="robustness_analysis",
            output_model=RobustnessSummary,
            run=robustness_analysis_run,
            requires=frozenset({"land_eligibility", "forcing", "members", "hazard_context"})
            | {
                f"potential_{tech}__{scenario}"
                for tech in technologies
                for scenario in LAND_SCENARIOS
            }
            | {f"lcoe_summary_{tech}" for tech in technologies}
            | {
                f"lcoe_nominal_{tech}__{scenario}"
                for tech in technologies
                for scenario in LAND_SCENARIOS[1:]
            },
            produces=frozenset({"robustness_analysis"})
            | {
                f"{kind}_{tech}__{role}"
                for tech in technologies
                for role in ("core", "sensitivity")
                for kind in ROW_MODELS
            },
            summarize=lambda out: "; ".join(
                f"{t}: "
                + ", ".join(
                    f"{r} {w.n_f7_set} of {w.n_candidates} cells in the F7 set"
                    for r, w in e.windows.items()
                )
                + (f" ({len(e.skipped)} outputs skipped)" if e.skipped else "")
                for t, e in out.technologies.items()
            ),
        ),
        PhaseSpec(
            name="potential_maps",
            output_model=PotentialMapsSummary,
            run=potential_maps_run,
            requires=frozenset({f"potential_{tech}__central" for tech in technologies}),
            produces=frozenset({"potential_maps"})
            | {f"potential_density_{tech}" for tech in technologies}
            | {f"capacity_factor_{tech}" for tech in technologies},
            summarize=lambda out: f"{len(out.rasters)} rasters and {len(out.figures)} figures",
        ),
        PhaseSpec(
            name="hazard_context",
            output_model=HazardSummary,
            run=hazard_context_run,
            requires=frozenset({"members", "reference_grid"}),
            produces=frozenset({"hazard_context"}),
            summarize=lambda out: f"{out.n_cells} cells x {out.n_hazard_members} hazard members",
        ),
        PhaseSpec(
            name="climate_maps",
            output_model=MapsSummary,
            run=climate_maps_run,
            requires=frozenset({"forcing", "forcing_masked"}),
            produces=frozenset({"climate_maps"}),
            summarize=lambda out: f"{out.n_figures} figures",
        ),
        PhaseSpec(
            name="overview",
            output_model=OverviewSummary,
            run=overview_run,
            requires=frozenset(
                {
                    "aligned_rasters",
                    "siting_layers",
                    "land_eligibility",
                    "forcing",
                    "forcing_masked",
                    "hazard_context",
                }
            ),
            produces=frozenset({"overview"}),
            summarize=lambda out: f"{len(out.figures)} figures and 1 table",
        ),
    ]


def _resolved_config_json(
    settings: SettingsFile, parameters, scale: str = DEFAULT_SCALE.scale_id
) -> str:
    return json.dumps(
        {
            "settings": settings.model_dump(mode="json"),
            "parameters": parameters.model_dump(mode="json"),
            "scale": scale,
        },
        sort_keys=True,
    )


def run_geofrea(
    country_code: str,
    target_phases: list[str],
    rerun_phases: list[str],
    resolutions: ResolutionsConfig,
    distance_cap_km: float,
    audit_config: AuditConfig,
    run_id: str,
    dirty: bool,
    revalidate_phases: list[str] | None = None,
    technologies: tuple[str, ...] = (),
    production: bool = False,
    figures: str = "all",
    max_batch_gb: float | None = None,
    scale: str = DEFAULT_SCALE.scale_id,
):
    """`_run_geofrea` at the cell scale `scale` (`core.scale`: `0p05deg`, the default, or `0p1deg`; M-F3-06, V-07).

    The scale is the only difference between a run and its scale check: the same phases run, the cell size they read is the active scale,
    and the phases that depend on it write under `<phase>__<scale id>` with their own manifest (A-08).
    """
    with use_scale(scale):
        return _run_geofrea(
            country_code,
            target_phases,
            rerun_phases,
            resolutions,
            distance_cap_km,
            audit_config,
            run_id,
            dirty,
            revalidate_phases,
            technologies,
            production,
            figures,
            max_batch_gb,
        )


def _run_geofrea(
    country_code: str,
    target_phases: list[str],
    rerun_phases: list[str],
    resolutions: ResolutionsConfig,
    distance_cap_km: float,
    audit_config: AuditConfig,
    run_id: str,
    dirty: bool,
    revalidate_phases: list[str] | None = None,
    technologies: tuple[str, ...] = (),
    production: bool = False,
    figures: str = "all",
    max_batch_gb: float | None = None,
) -> tuple[bool, Orchestrator]:
    """Run the phases needed to satisfy target_phases for a single country.

    Args:
        country_code: ISO-3166-alpha-3 code, must be a key in parameters.json.
        target_phases: RunConfig.target_phases for this run.
        rerun_phases: RunConfig.rerun_phases for this run.
        distance_cap_km: settings.yaml's `geospatial.distance_cap_km`, the `distance_capped` flag
            threshold (OQ-040), threaded to grid_alignment.
        resolutions: settings.yaml's `geospatial.resolutions`, threaded
            through to grid_alignment's PhaseSpec (see
            _build_phase_specs()).
        audit_config: config/audit.yaml, threaded through to
            data_quality_audit's PhaseSpec (see _build_phase_specs()).
        run_id: This run's identifier (see
            geofrea.core.orchestrator.compute_run_id).
        dirty: Whether the working tree has uncommitted changes (see
            geofrea.core.orchestrator.compute_dirty).
        technologies: settings.yaml's `run.technologies`, threaded to technical_potential.
        production: Whether this is a production run, threaded to technical_potential.
        figures: settings.yaml's `figures`, threaded to potential_maps.
        max_batch_gb: settings.yaml's `memory.max_batch_gb`, threaded to lcoe_modeling.

    Returns:
        A tuple: (True if every one of target_phases ended "success",
        False if any ended "failed" or "skipped_upstream_failed" —
        main()'s exit code is derived from this; see module-level Usage
        note), and the Orchestrator instance, whose `.manifest` and the
        returned `results` together give main() everything the
        end-of-run table (COMMAND ADJ-7 action 6) needs.
    """
    # Console: INFO and up, compact. File: everything any geofrea.*
    # module logs (DEBUG and up), including phase-lifecycle and progress
    # lines from orchestrator.py and from individual phase modules — see
    # geofrea.core.run_logging's module docstring for why this replaced
    # logging.basicConfig() + a FileHandler attached only to this
    # module's own logger (which never received other modules' records).
    log_file_path = log_path(country_code, run_id)
    file_handler = configure_logging(log_file_path)
    logger.info("Starting run for %s with run_id %s", country_code, run_id)

    parameters = load_parameters(PARAMETERS_JSON)
    # None is valid: a country present in countries.yaml but not yet in
    # parameters.json can still run phases that read no CountryParams
    # field (data_acquisition, grid_alignment). A phase that does need a
    # field fails loud via PhaseContext.require_country_params() instead
    # of every country needing full economic parameters up front.
    country_params = parameters.countries.get(country_code)

    orchestrator = Orchestrator(
        outputs_dir=outputs_dir(),
        country_code=country_code,
        country_params=country_params,
        target_phases=target_phases,
        rerun_phases=rerun_phases,
        run_id=run_id,
        methodology_version=_read_methodology_version(METHODOLOGY_MD),
        dirty=dirty,
        prune_unregistered=True,
        revalidate_phases=revalidate_phases or [],
    )

    orchestrator.record_seed("sampler", load_experiments(EXPERIMENTS_YAML).sampler.seed)
    results = orchestrator.run(
        _build_phase_specs(
            resolutions,
            distance_cap_km,
            audit_config,
            technologies,
            production,
            figures,
            max_batch_gb,
        )
    )
    ok = all(results[name].status == "success" for name in target_phases)
    if not ok:
        logger.error(
            "Run incomplete for %s: %s",
            country_code,
            {
                name: results[name].status
                for name in target_phases
                if results[name].status != "success"
            },
        )
    else:
        logger.info("Run completed for %s.", country_code)

    logging.getLogger("geofrea").removeHandler(file_handler)
    file_handler.close()
    return ok, orchestrator, results


def _parse_args(argv: list[str]):
    import argparse

    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="Run the GeoFREA pipeline: every phase a country needs, in dependency order.",
    )
    parser.add_argument(
        "countries",
        nargs="*",
        metavar="ISO3",
        help="country codes to run (e.g. PRT BRA IND); default: run.countries in settings.yaml, else every thesis country",
    )
    parser.add_argument(
        "--phases",
        help="comma-separated target phases (default: run.target_phases in settings.yaml); upstream phases are added automatically",
    )
    parser.add_argument(
        "--production",
        action="store_true",
        help="production run: refuse to start if a consumed parameter is a proxy or an uncertain parameter lacks a value or range",
    )
    parser.add_argument(
        "--revalidate",
        help="comma-separated phases whose stale_upstream entry is declared still valid because their current inputs are unchanged "
        "(the orchestrator checks that their required artifacts exist and records the lineage); used once after a contract change",
    )
    parser.add_argument(
        "--scale",
        choices=sorted(SCALES),
        default=DEFAULT_SCALE.scale_id,
        help="cell size of the run: 0p05deg (default, S-06) or 0p1deg, the scale check of V-07 (same code, files under <phase>__0p1deg)",
    )
    parser.add_argument(
        "--rerun",
        help="comma-separated phases to execute again even if the manifest records success (default: run.rerun_phases)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or [])
    settings = load_settings(SETTINGS_YAML)
    parameters = load_parameters(PARAMETERS_JSON)
    audit_config = load_audit_config(AUDIT_YAML)
    technologies = load_technologies(TECHNOLOGIES_YAML)
    experiments = load_experiments(EXPERIMENTS_YAML)
    try:
        validate_run_technologies(settings.run.technologies, technologies)
        validate_registry(technologies, experiments)
    except ConfigConsistencyError as exc:
        logger.error("%s", exc)
        return 1

    # "Known" is defined by countries.yaml (A-05's single source of
    # country-specific mappings), not parameters.json: a country can be
    # wired for data_acquisition/grid_alignment before its economics are
    # researched (see CountryParamsRequiredError). Empty run.countries
    # still means "every country parameters.json currently has", per
    # settings.yaml's own comment — that default is about scope, not a
    # requirement every country must satisfy.
    countries_config = load_countries(COUNTRIES_YAML)
    # A synthetic country (countries.yaml's synthetic_fixture_root, A-06/
    # D-core-017/D-core-018/OQ-032 verdict) is a test fixture, never a
    # thesis country — it must never enter the default "every country
    # parameters.json has" expansion below, only an explicit
    # settings.run.countries listing naming it (which a real run never
    # does; only a test/CI job targeting the fixture itself would). This
    # is the separation OQ-032's verdict requires enforced at the point
    # where "every country" would otherwise silently include it.
    default_countries = [
        c
        for c in parameters.countries
        if not countries_config.get(c, {}).get("synthetic_fixture_root")
    ]
    countries = [c.upper() for c in args.countries] or settings.run.countries or default_countries
    unknown = [c for c in countries if c not in countries_config]
    if unknown:
        logger.error(
            "Requested countries %s are not present in countries.yaml (known: %s).",
            unknown,
            sorted(
                c for c in countries_config if not countries_config[c].get("synthetic_fixture_root")
            ),
        )
        return 1
    target_phases = (
        [p.strip() for p in args.phases.split(",") if p.strip()]
        if args.phases
        else settings.run.target_phases
    )
    rerun_phases = (
        [p.strip() for p in args.rerun.split(",") if p.strip()]
        if args.rerun
        else settings.run.rerun_phases
    )
    revalidate_phases = (
        [p.strip() for p in args.revalidate.split(",") if p.strip()] if args.revalidate else []
    )

    parameter_audit = audit_parameters(
        parameters, technologies, countries, settings.run.technologies
    )
    for finding in parameter_audit.warnings:
        logger.warning("parameter contract: %s", finding)
    if args.production:
        try:
            enforce_production(parameter_audit)
        except ProductionRunError as exc:
            logger.error("%s", exc)
            return 1
    else:
        for finding in parameter_audit.errors:
            logger.warning("parameter contract (blocks a production run): %s", finding)

    methodology_version = _read_methodology_version(METHODOLOGY_MD)
    git_commit = compute_git_commit(REPO_ROOT)
    dirty = compute_dirty(REPO_ROOT)
    run_id = compute_run_id(
        _resolved_config_json(settings, parameters, args.scale), methodology_version, git_commit
    )

    all_ok = True
    table_rows: list[dict] = []
    for country_code in countries:
        ok, orchestrator, results = run_geofrea(
            country_code,
            target_phases,
            rerun_phases,
            settings.geospatial.resolutions,
            settings.geospatial.distance_cap_km,
            audit_config,
            run_id,
            dirty,
            revalidate_phases,
            tuple(settings.run.technologies),
            args.production,
            settings.figures,
            settings.memory.max_batch_gb,
            args.scale,
        )
        all_ok = all_ok and ok
        for phase_name, result in results.items():
            elapsed_s = (
                datetime.fromisoformat(result.finished_at)
                - datetime.fromisoformat(result.started_at)
            ).total_seconds()
            artifact_count = sum(
                1 for entry in orchestrator.manifest.artifacts.values() if entry.phase == phase_name
            )
            table_rows.append(
                {
                    "country": country_code,
                    "phase": phase_name,
                    "status": result.status,
                    "elapsed_s": elapsed_s,
                    "artifact_count": artifact_count,
                }
            )

    # One table, phase x status x elapsed time x artifact count per
    # country, plus the run id — COMMAND ADJ-7 action 6. Logged (not
    # print()ed) so it lands in both the console and the run's log file.
    logger.info("Run summary:\n%s", render_run_table(table_rows, run_id))

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
