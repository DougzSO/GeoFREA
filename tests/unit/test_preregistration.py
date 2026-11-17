"""The pre-registered subset, its digest and the guard of F6 and F7 (DEC-081 item g, COMMAND 155B).

The tag `prereg-v1` is created once by the author (COMMAND 162T). These tests never create it in this repository: they build a temporary git
repository with an annotated tag whose message is the one `scripts/preregistration_digest.py` prints, and a copy of `config/` that they alter.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from geofrea.core import preregistration as prereg
from geofrea.core.config_fingerprint import CONFIG_FILES, TURBINES, DiskConfigSource
from geofrea.core.config_loader import load_parameters
from geofrea.core.orchestrator import Orchestrator, PhaseSpec

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG = REPO_ROOT / "config"
REBASELINE = REPO_ROOT / "scripts" / "rebaseline_config_fingerprint.py"
COUNTRIES = ["PRT", "IND", "BRA"]
_GIT = ["git", "-c", "user.name=test", "-c", "user.email=test@example.org", "-c", "commit.gpgsign=false", "-c", "tag.gpgSign=false"]


def _source(config_dir: Path) -> DiskConfigSource:
    return DiskConfigSource({k: config_dir / name for k, name in CONFIG_FILES.items()}, config_dir / TURBINES)


@pytest.fixture
def config_copy(tmp_path):
    target = tmp_path / "config"
    shutil.copytree(CONFIG, target)
    return target


def _git(repo: Path, *args: str, stdin: str | None = None) -> None:
    subprocess.run([*_GIT, "-C", str(repo), *args], input=stdin, text=True, check=True, capture_output=True)


def _repo(tmp_path: Path, config_dir: Path | None, *, annotated: bool = True) -> Path:
    """A temporary git repository with one commit and, when `config_dir` is given, the tag `prereg-v1` carrying the digest of that config."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "README").write_text("x", encoding="utf-8")
    _git(repo, "add", "README")
    _git(repo, "commit", "-q", "-m", "first")
    if config_dir is not None:
        message = prereg.tag_message(prereg.live_digests(COUNTRIES, _source(config_dir)))
        if annotated:
            _git(repo, "tag", "-a", prereg.TAG_NAME, "-F", "-", stdin=message)
        else:
            _git(repo, "tag", prereg.TAG_NAME)
    return repo


def _edit(config_dir: Path, name: str, old: str, new: str) -> None:
    path = config_dir / name
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, (name, old, text.count(old))
    path.write_text(text.replace(old, new), encoding="utf-8")


def _change_prt_solar_top_k(config_dir: Path) -> None:
    """PRT solar `top_k_percent` from its registered 10 to 20: a value of the subset is changed after the tag."""
    text = (config_dir / "parameters.json").read_text(encoding="utf-8")
    i = text.index('"top_k_percent"')  # the first one is PRT solar
    j = text.index('"value": 10', i)
    assert j - i < 200, "the first value after the key is the one of PRT solar"
    (config_dir / "parameters.json").write_text(text[:j] + '"value": 20' + text[j + len('"value": 10') :], encoding="utf-8")


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int


def _phase(name: str, calls: list[str]) -> PhaseSpec:
    def run(context):
        calls.append(name)
        return _Out(value=1)

    return PhaseSpec(name=name, output_model=_Out, run=run)


def _orchestrator(tmp_path: Path, iso: str, phase: str, config_dir: Path, repo: Path) -> Orchestrator:
    source = _source(config_dir)
    params = load_parameters(CONFIG / "parameters.json").countries.get(iso)
    return Orchestrator(
        outputs_dir=tmp_path / "outputs",
        country_code=iso,
        country_params=params,
        target_phases=[phase],
        rerun_phases=[],
        run_id="run-1",
        methodology_version="test-1.0.0",
        dirty=False,
        preregistration_guard=lambda _name: prereg.verify(iso, source, repo),
    )


# --- the five cases of COMMAND 155B -------------------------------------------------------------------------------


@pytest.mark.unit
def test_a_subset_equal_to_the_tag_passes_and_the_manifest_records_both_digests(tmp_path, config_copy):
    repo = _repo(tmp_path, config_copy)
    calls: list[str] = []
    orchestrator = _orchestrator(tmp_path, "PRT", "robustness_analysis", config_copy, repo)

    orchestrator.run([_phase("robustness_analysis", calls)])

    assert calls == ["robustness_analysis"]
    live = prereg.live_digests(["PRT"], _source(config_copy)).countries["PRT"]
    record = orchestrator.manifest.preregistration
    assert record is not None and (record.digest_live, record.digest_tag) == (live, live)
    on_disk = json.loads(orchestrator.manifest_path.read_text(encoding="utf-8"))
    assert on_disk["preregistration"] == {"digest_live": live, "digest_tag": live}


@pytest.mark.unit
def test_a_subset_changed_after_the_tag_makes_f7_refuse_and_names_the_key(tmp_path, config_copy):
    repo = _repo(tmp_path, config_copy)
    _change_prt_solar_top_k(config_copy)
    calls: list[str] = []
    orchestrator = _orchestrator(tmp_path, "PRT", "robustness_analysis", config_copy, repo)

    orchestrator.run([_phase("robustness_analysis", calls)])

    assert calls == []  # the phase did not run
    entry = orchestrator.manifest.phases["robustness_analysis"]
    assert entry.status == "failed"
    assert "parameters:countries.PRT.technologies.*.top_k_percent" in (entry.error or "")
    assert orchestrator.manifest.preregistration is None


@pytest.mark.unit
def test_the_rebaseline_script_refuses_a_changed_subset_when_the_tag_exists(tmp_path, config_copy):
    repo = _repo(tmp_path, config_copy)
    _change_prt_solar_top_k(config_copy)

    done = subprocess.run(
        [sys.executable, str(REBASELINE), "--change", "scope-127-f2a-f3", "--countries", "PRT", "--repo", str(repo), "--config-dir", str(config_copy)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode == 1
    assert "REFUSED" in done.stdout and "differs from the tag prereg-v1" in done.stdout
    assert "top_k_percent" in done.stdout


@pytest.mark.unit
def test_without_the_tag_the_rebaseline_has_no_subset_check_and_with_an_equal_subset_it_has_no_conflict(tmp_path, config_copy):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    without = _repo(tmp_path / "a", None)
    assert prereg.tag_conflict(COUNTRIES, _source(config_copy), without) is None
    with_tag = _repo(tmp_path / "b", config_copy)
    assert prereg.tag_conflict(COUNTRIES, _source(config_copy), with_tag) == []


@pytest.mark.unit
def test_real_data_without_the_tag_makes_f7_refuse(tmp_path, config_copy):
    repo = _repo(tmp_path, None)
    calls: list[str] = []
    orchestrator = _orchestrator(tmp_path, "PRT", "robustness_analysis", config_copy, repo)

    orchestrator.run([_phase("robustness_analysis", calls)])

    assert calls == []
    entry = orchestrator.manifest.phases["robustness_analysis"]
    assert entry.status == "failed" and "prereg-v1" in (entry.error or "") and "does not exist" in (entry.error or "")


@pytest.mark.unit
def test_synthetic_true_passes_without_the_tag_and_records_nothing(tmp_path, config_copy):
    repo = _repo(tmp_path, None)
    calls: list[str] = []
    orchestrator = _orchestrator(tmp_path, "ZZZ", "robustness_analysis", config_copy, repo)

    orchestrator.run([_phase("robustness_analysis", calls)])

    assert calls == ["robustness_analysis"]
    assert orchestrator.manifest.phases["robustness_analysis"].status == "success"
    assert orchestrator.manifest.preregistration is None


# --- the rest of the contract ---------------------------------------------------------------------------------------


@pytest.mark.unit
def test_the_guard_covers_f6_and_f7_and_no_other_phase(tmp_path, config_copy):
    repo = _repo(tmp_path, None)  # no tag: a guarded phase is refused, an unguarded one runs
    for phase, refused in (("lcoe_modeling", True), ("sample_size_convergence", True), ("technical_potential", False)):
        calls: list[str] = []
        (tmp_path / phase).mkdir()
        orchestrator = _orchestrator(tmp_path / phase, "PRT", phase, config_copy, repo)
        orchestrator.run([_phase(phase, calls)])
        assert (calls == []) is refused, phase


@pytest.mark.unit
def test_a_lightweight_tag_is_refused_because_it_carries_no_digest(tmp_path, config_copy):
    repo = _repo(tmp_path, config_copy, annotated=False)
    with pytest.raises(prereg.PreregistrationError, match="lightweight"):
        prereg.verify("PRT", _source(config_copy), repo)


@pytest.mark.unit
def test_a_country_the_tag_does_not_list_is_refused(tmp_path, config_copy):
    repo = _repo(tmp_path, config_copy)
    _git(repo, "tag", "-d", prereg.TAG_NAME)
    message = prereg.tag_message(prereg.live_digests(["PRT"], _source(config_copy)))
    _git(repo, "tag", "-a", prereg.TAG_NAME, "-F", "-", stdin=message)
    with pytest.raises(prereg.PreregistrationError, match="does not register IND"):
        prereg.verify("IND", _source(config_copy), repo)


@pytest.mark.unit
def test_the_message_of_the_tag_round_trips():
    digests = prereg.live_digests(COUNTRIES, _source(CONFIG))
    parsed = prereg.parse_tag_message(prereg.tag_message(digests))
    assert parsed.subset_version == prereg.SUBSET_VERSION
    assert parsed.aggregate == digests.aggregate
    assert parsed.countries == digests.countries
    assert parsed.keys == digests.keys
    assert prereg.aggregate_digest(parsed.countries) == digests.aggregate


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "old", "new", "moves"),
    [
        ("experiments.yaml", "  outcome_threshold: 0.20\n", "  outcome_threshold: 0.25\n", True),
        ("experiments.yaml", "    outcome_threshold: [0.10, 0.30]", "    outcome_threshold: [0.10, 0.35]", True),
        ("experiments.yaml", "    sensitivity_lambda: 0.10", "    sensitivity_lambda: 0.15", True),
        ("experiments.yaml", "    start_year: 2071", "    start_year: 2072", True),
        ("experiments.yaml", "  regret_quantile: 0  #", "  regret_quantile: 0.01  #", True),
        ("experiments.yaml", "  bootstrap_replicates: 200", "  bootstrap_replicates: 300", False),  # not in the subset
    ],
)
def test_the_subset_moves_with_a_registered_key_and_not_with_another(config_copy, name, old, new, moves):
    text = (config_copy / name).read_text(encoding="utf-8")
    if text.count(old) != 1:  # a key the file does not hold in that form: the case is about the others
        pytest.skip(f"{old!r} is not unique in {name}")
    before = prereg.live_digests(["PRT"], _source(config_copy)).aggregate
    _edit(config_copy, name, old, new)
    after = prereg.live_digests(["PRT"], _source(config_copy)).aggregate
    assert (before != after) is moves


@pytest.mark.unit
def test_the_parameter_sensitivities_and_the_discount_rate_range_are_in_the_subset(config_copy):
    """`transmission_loss_per_km_sensitivity`, `hot_zone_sensitivity`, `poi_sensitivity_threshold_kv` and the range of `discount_rate` (DEC-081 item d)."""
    keys = prereg.subset_values("PRT", _source(config_copy))
    names = " ".join(keys)
    for needed in ("hot_zone_sensitivity", "transmission_loss_per_km_sensitivity", "poi_sensitivity_threshold_kv", "discount_rate.range", "national_targets.PRT"):
        assert needed in names, needed
    assert "land_availability" not in names and "external_validation" not in names  # the excluded ones
    base = prereg.live_digests(["PRT"], _source(config_copy)).aggregate
    data = json.loads((config_copy / "parameters.json").read_text(encoding="utf-8"))
    data["countries"]["PRT"]["connection"]["transmission_loss_per_km_sensitivity"]["value"] = 0.00045
    (config_copy / "parameters.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    assert prereg.live_digests(["PRT"], _source(config_copy)).aggregate != base


@pytest.mark.unit
def test_a_value_outside_the_subset_does_not_move_the_digest(config_copy):
    before = prereg.live_digests(COUNTRIES, _source(config_copy)).aggregate
    text = (config_copy / "parameters.json").read_text(encoding="utf-8")
    i = text.index('"capex_usd_per_kw"')
    j = text.index('"note": "', i) + len('"note": "')
    (config_copy / "parameters.json").write_text(text[:j] + "changed note. " + text[j:], encoding="utf-8")
    assert prereg.live_digests(COUNTRIES, _source(config_copy)).aggregate == before


@pytest.mark.unit
def test_a_test_fixture_country_is_synthetic_and_a_real_one_is_not():
    source = _source(CONFIG)
    assert prereg.is_synthetic("ZZZ", source)
    assert not any(prereg.is_synthetic(iso, source) for iso in COUNTRIES)
    assert set(prereg.registered_countries(source)) == set(COUNTRIES)
    assert "ZZZ" not in prereg.registered_countries(source)


@pytest.mark.unit
def test_if_the_tag_prereg_v1_exists_in_this_repository_its_digest_is_the_live_one():
    """The tag is created at COMMAND 162T; until then this test is skipped. After it, a change of the subset fails here (the CI fetches tags)."""
    source = _source(CONFIG)
    conflict = prereg.tag_conflict(prereg.registered_countries(source), source, REPO_ROOT)
    if conflict is None:
        pytest.skip("the tag prereg-v1 does not exist yet (COMMAND 162T)")
    assert conflict == [], "the pre-registered subset differs from the tag prereg-v1: " + "; ".join(conflict)


@pytest.mark.unit
def test_the_digest_script_prints_the_message_and_creates_nothing(tmp_path):
    before = subprocess.run(["git", "-C", str(REPO_ROOT), "tag", "-l", prereg.TAG_NAME], capture_output=True, text=True, check=True).stdout
    done = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "preregistration_digest.py"), "--countries", "PRT"], capture_output=True, text=True, check=False
    )
    after = subprocess.run(["git", "-C", str(REPO_ROOT), "tag", "-l", prereg.TAG_NAME], capture_output=True, text=True, check=True).stdout
    assert done.returncode == 0 and "prereg-v1\nsubset_version: 1\naggregate: " in done.stdout
    assert before == after
