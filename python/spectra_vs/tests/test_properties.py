"""Property tests for the kernel invariants the project states everywhere and tests by example.

Run from the repository root:

    python python/spectra_vs/tests/test_properties.py

WHY THIS FILE EXISTS. Every invariant below is asserted in prose in docs/kernel/slice-spec.md
and pinned in the per-stage suites against one or two hand-built fixtures. A fixture proves
that the implementation is right ON THAT FIXTURE. These tests generate the inputs instead,
from a fixed seed, so that a mutation which happens to leave the hand-built cell alone still
turns a named test red.

THE FIVE INVARIANTS, and what a failure of each would mean:

  1. CONTAINMENT. `P_min` is a subset of `P_max` in both facts and instances, always. A
     failure means the upper side of the bracket lost something the lower side derived, so
     the pair is not a bracket at all and `goal not in fix(P_max, S)` stops implying
     `goal not in fix(P_min, S)` - ROBUST would no longer be conservative.

  2. MONOTONICITY OF BLINDNESS. Deleting more records never shrinks the licensed set. A
     failure means less telemetry bought MORE confidence somewhere, which would let an
     attacker improve a verdict by deleting records. This is the direction the whole
     completeness axis rests on.

  3. DETERMINISM UNDER PERMUTATION. Permuting the order of input events changes no artifact.
     A failure means a hash in a certificate depends on the order a reader happened to feed
     records in, and the independent checker could not reproduce it.

  4. THE TWO-SIDED BRACKET ORDERS. For the same cut, derivable in the lower program implies
     derivable in the upper one. A failure means the witness direction of the bracket is
     broken: an attack visible in the observed program would vanish from the licensed one.

  5. THE SEQ FEASIBILITY FUNCTION. `ground.seq_feasible` must reduce exactly to
     `left < right <= left + within` on observed points and must be true for intervals
     exactly when SOME placement satisfies that. Admitting a combination impossible for
     every placement is the defect INC-0010 recorded, so this one is checked exhaustively
     against a brute-force reference rather than sampled.

HOW THEY ARE GENERATED. Every generator is driven by `random.Random(SEED)` with SEED a fixed
constant below. No wall clock, no environment, no unseeded randomness. Each case is entered
with `subTest` carrying the exact input, so a failure names the reproducer rather than the
iteration number.
"""

from __future__ import annotations

import pathlib
import random
import sys
import types
import unittest
from typing import Final

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_core" / "src"))
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_vs" / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from spectra_core import canon, ids, model  # noqa: E402
from spectra_core.ids import EventId, RecordId, SourceId  # noqa: E402
from spectra_core.model import CanonicalEvent, IntegrityClass  # noqa: E402
from spectra_vs import calibrate, degrade, envelope, gen, liveness, temporal  # noqa: E402
from spectra_vs.ground import seq_feasible  # noqa: E402
from spectra_vs.reach import ReachProgram, admissible_cut_masks, reach  # noqa: E402

import fixture  # noqa: E402
import vs_fixtures  # noqa: E402

#: The one seed every generator in this file is derived from. It is a constant so that a
#: failing case is reproducible by rerunning the file, and it is printed with every failure.
SEED: Final[int] = 20260923

SECOND: Final[int] = 1_000_000_000
RULES_TOML: Final[pathlib.Path] = _REPO_ROOT / "config" / "vs" / "rules.toml"


def _seeded(label: str) -> random.Random:
    """One generator per property, so that adding a case to one does not reshuffle another."""
    return random.Random(f"{SEED}:{label}")


# ---------------------------------------------------------------------------
# 1. CONTAINMENT: P_min is a subset of P_max, at every completeness level
# ---------------------------------------------------------------------------

#: The declared sources of the `vs-01-token-pivot` family and their integrity classes, as
#: `fixture.liveness` declares them. Kept here as data because the generator has to produce
#: a timeline for every declared source, including the one that never emits.
_DECLARED_SOURCES: Final[tuple[tuple[str, str], ...]] = (
    ("edr_host", "none"),
    ("gw_access", "sequenced"),
    ("iam_audit", "chained"),
    ("idp_auth", "chained"),
    ("net_flow", "none"),
    ("res_access", "none"),
)


def _templates() -> tuple[tuple[str, str, dict[str, model.Entity]], ...]:
    """The record shapes the shipped rule table can bind, with their entity roles.

    The shapes are the fixture's; only which of them occur and when is generated. Inventing
    new predicates would test the generator rather than the stage.
    """
    e = fixture.ENTITIES
    return (
        ("idp_auth", "idp.refresh_exchange", {"credential": e["token"], "principal": e["mallory"]}),
        ("gw_access", "gw.request", {"principal": e["mallory"], "service": e["gateway"]}),
        ("res_access", "res.read", {"principal": e["mallory"], "resource": e["doc1"]}),
        ("res_access", "res.read", {"principal": e["mallory"], "resource": e["doc2"]}),
        ("res_access", "res.read", {"principal": e["mallory"], "resource": e["doc3"]}),
        ("res_access", "res.export", {"principal": e["mallory"], "resource": e["export"]}),
        ("net_flow", "net.connection", {"principal": e["alice"], "service": e["gateway"]}),
        ("iam_audit", "iam.approval_granted", {"principal": e["mallory"], "role": e["admin_role"]}),
        ("iam_audit", "iam.role_assumed", {"principal": e["mallory"], "role": e["admin_role"]}),
    )


def _generated_bundle(
    rng: random.Random, keep: float
) -> tuple[tuple[model.CanonicalEvent, ...], tuple[object, ...], tuple[str, ...]]:
    """A bundle keeping each record shape with probability `keep`, at generated instants.

    `keep` stands in for a completeness level: a bundle at keep=1.0 is the calibrated cell
    and one at keep=0.3 has lost most of the chain. The third member is a printable
    description of the draw, which is what a failing subTest carries.
    """
    drawn: list[tuple[str, str, dict[str, model.Entity], int]] = []
    for source, event_type, roles in _templates():
        if rng.random() > keep:
            continue
        offset = rng.randrange(0, 360)
        drawn.append((source, event_type, roles, fixture.EPOCH_NS + offset * SECOND))
    drawn.sort(key=lambda item: (item[0], item[3], item[1]))

    seq_of: dict[str, int] = {}
    emissions = []
    label: list[str] = []
    for source, event_type, roles, t_ns in drawn:
        seq = seq_of.get(source, 0)
        seq_of[source] = seq + 1
        emissions.append(fixture.make_event(source, seq, event_type, t_ns, roles))
        label.append(f"{source}/{event_type}@+{(t_ns - fixture.EPOCH_NS) // SECOND}s")

    events = tuple(sorted((em.event for em in emissions), key=lambda ev: ev.sort_key()))
    bindings = tuple(
        sorted((b for em in emissions for b in em.bindings), key=lambda b: b.sort_key())
    )
    return events, bindings, tuple(label)


def _generated_view(
    rng: random.Random, blindness: float
) -> tuple[envelope.LivenessView, tuple[str, ...]]:
    """A liveness timeline per declared source: a partition of the span into LIVE/BLIND runs.

    The partition is contiguous and covers the whole span, which is what S7 emits. Only the
    cut points and the verdicts are generated, so every view here is one S7 could have
    written.
    """
    span0, span1 = fixture.SPAN_T0_NS, fixture.SPAN_T1_NS
    timelines: list[envelope.SourceLiveness] = []
    label: list[str] = []
    for name, integrity in _DECLARED_SOURCES:
        cuts = sorted(rng.sample(range(1, 40), rng.randrange(0, 4)))
        bounds = [span0] + [span0 + (span1 - span0) * c // 40 for c in cuts] + [span1]
        intervals: list[envelope.LivenessInterval] = []
        marks: list[str] = []
        for low, high in zip(bounds, bounds[1:]):
            if low >= high:
                continue
            blind = rng.random() < blindness
            intervals.append(
                envelope.LivenessInterval(
                    low,
                    high,
                    model.LivenessVerdict.BLIND if blind else model.LivenessVerdict.LIVE,
                    "B_GAP_EXCEEDS_THRESHOLD" if blind else "L_CALIBRATED_OK",
                )
            )
            marks.append("B" if blind else "L")
        timelines.append(
            envelope.SourceLiveness(
                source_id=SourceId.of(name),
                integrity_class=model.IntegrityClass(integrity),
                intervals=tuple(intervals),
            )
        )
        label.append(f"{name}={''.join(marks)}")
    view = envelope.LivenessView(
        tuple(sorted(timelines, key=lambda s: canon.byte_order_key(str(s.source_id))))
    )
    return view, tuple(label)


class TestContainment(unittest.TestCase):
    """`P_min` is a subset of `P_max` in both facts and instances, at every completeness.

    S9 asserts this privately before returning, so a violation would surface as a
    `SchemaError` out of `envelope.envelope`. That is exactly why it is re-checked here on
    the returned objects as well: an assertion that is only ever exercised on one fixture
    is an assertion nobody has tested, and a future refactor that returns `P_min` from a
    different engine than the one it checked would pass the private check and fail here.

    A failure means the bracket is not a bracket. `goal not in fix(P_max, S)` would stop
    implying `goal not in fix(P_min, S)`, so a ROBUST verdict would no longer be sound.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.table = fixture.rule_table(RULES_TOML)
        cls.entities = fixture.entity_universe()

    def test_p_min_is_a_subset_of_p_max_over_generated_cells(self) -> None:
        rng = _seeded("containment")
        strictly_larger = 0
        cases = 0
        for index in range(240):
            keep = (1.0, 0.85, 0.6, 0.35)[index % 4]
            blindness = (0.0, 0.25, 0.5, 0.75, 1.0)[index % 5]
            events, bindings, bundle_label = _generated_bundle(rng, keep)
            view, view_label = _generated_view(rng, blindness)
            description = (
                f"seed={SEED} case={index} keep={keep} blindness={blindness} "
                f"bundle={bundle_label} view={view_label}"
            )
            with self.subTest(case=description):
                result = envelope.envelope(
                    self.table, events, bindings, view, self.entities
                )
                upper_facts = {str(f.fact_key) for f in result.p_max.facts}
                upper_instances = {str(i.instance_id) for i in result.p_max.instances}
                missing_facts = sorted(
                    str(f.fact_key)
                    for f in result.p_min.facts
                    if str(f.fact_key) not in upper_facts
                )
                missing_instances = sorted(
                    str(i.instance_id)
                    for i in result.p_min.instances
                    if str(i.instance_id) not in upper_instances
                )
                self.assertEqual(missing_facts, [], f"facts lost from PMax; {description}")
                self.assertEqual(
                    missing_instances, [], f"instances lost from PMax; {description}"
                )
                upper_axioms = set(map(str, result.p_max.axioms))
                self.assertTrue(
                    {str(a) for a in result.p_min.axioms} <= upper_axioms,
                    f"axioms lost from PMax; {description}",
                )
                self.assertEqual(result.p_min.licences, (), description)
                cases += 1
                if len(upper_instances) > len(result.p_min.instances):
                    strictly_larger += 1
        self.assertEqual(cases, 240)
        # Containment is trivially true when the two programs are equal, so the generated
        # population has to contain cells where the envelope actually admitted something.
        self.assertGreater(strictly_larger, 20, f"seed={SEED}: the draw admitted no silent work")


# ---------------------------------------------------------------------------
# 2. MONOTONICITY OF BLINDNESS: deleting records never shrinks the licensed set
# ---------------------------------------------------------------------------

_MONO_EPOCH: Final[int] = 1_707_004_800_000_000_000
_MONO_PERIOD: Final[int] = 10 * SECOND
_MONO_COUNT: Final[int] = 240
_MONO_SPAN_T1: Final[int] = _MONO_EPOCH + _MONO_COUNT * _MONO_PERIOD
_MONO_SOURCES: Final[tuple[str, ...]] = ("gw_access", "iam_audit", "res_access")
_MONO_PHASES: Final[tuple[calibrate.Phase, ...]] = (
    calibrate.Phase("steady", _MONO_EPOCH, _MONO_EPOCH + 100_000 * SECOND),
)
_MONO_GENERATOR_HASH: Final[str] = canon.hash_ref("gencfg", b"spectra.vs.properties")
_MONO_CALIBRATION_BUNDLE: Final[str] = canon.hash_ref("bundle", b"the calibration run")
_MONO_ANALYSIS_BUNDLE: Final[str] = canon.hash_ref("bundle", b"the run under analysis")


def _event_payload(source: str, seq: int, t_ns: int, event_type: str) -> bytes:
    """The event-id preimage, in the field order `CanonicalEvent.identity_bytes` uses."""
    return b"".join(
        (
            canon.pairs(()),
            canon.utf8_text(event_type),
            canon.u32(seq),
            canon.ascii_text("src:" + source),
            canon.i64(t_ns),
        )
    )


def _raw_stream(rng: random.Random) -> tuple[gen.RawEvent, ...]:
    """One seeded raw stream: three sources, dense `seq`, jittered instants.

    The jitter matters. A perfectly periodic stream makes every surviving gap a multiple of
    the period, which lands the gap-versus-threshold test on exact ties; a generated offset
    inside the period puts the comparison on both sides of the threshold instead.
    """
    records: list[gen.RawEvent] = []
    for name in _MONO_SOURCES:
        instant = _MONO_EPOCH
        for seq in range(_MONO_COUNT):
            records.append(
                gen.RawEvent(
                    source_id=SourceId.of(name),
                    seq=seq,
                    t_evt_ns=instant,
                    event_type=f"{name}.tick",
                )
            )
            instant += _MONO_PERIOD + rng.randrange(-2, 3) * (SECOND // 2)
    return tuple(sorted(records, key=lambda r: r.sort_key()))


def _canonical_by_key(raw: tuple[gen.RawEvent, ...]) -> dict[tuple[str, int], CanonicalEvent]:
    """Every raw record as the canonical event S4 would seal, keyed by `(source, seq)`.

    Built once over the UNDEGRADED stream and then filtered, which is what delete-only
    degradation means: a survivor is octet-identical to the record the generator emitted,
    including its sequence number.
    """
    table: dict[tuple[str, int], CanonicalEvent] = {}
    for record in raw:
        payload = _event_payload(str(record.source_id)[4:], record.seq, record.t_evt_ns, record.event_type)
        table[(str(record.source_id), record.seq)] = CanonicalEvent(
            event_id=EventId.mint(payload),
            record_id=RecordId.mint(payload),
            source_id=record.source_id,
            seq=record.seq,
            event_type=record.event_type,
            t_evt_ns=record.t_evt_ns,
            t_ing_ns=record.t_evt_ns,
        )
    return table


def _mono_config() -> liveness.LivenessConfig:
    """The shipped configuration with `m_min` at 2, the smallest value the ladder admits.

    `m_min` is 2 rather than the shipped 3 because an elementary interval between two
    consecutive record instants brackets exactly two records by construction, so m_min=3
    would send every window to R9 and make the property vacuously true.
    """
    return liveness.LivenessConfig(
        quantile_num=95,
        quantile_den=100,
        slack_num=3,
        slack_den=2,
        k_tail=5,
        n_floor=30,
        m_min=2,
        mcs_exact_cap=64,
    )


def _mono_profile(by_key: dict[tuple[str, int], CanonicalEvent]) -> calibrate.SourceProfile:
    """A profile built from a SEPARATE pass over the undegraded stream, as S6 requires.

    No threshold in this file is derived from the bundle under analysis: F4 SELF does not
    exist, and a test that manufactured one would be testing a mode the ladder forbids.
    """
    by_source = []
    for name in _MONO_SOURCES:
        source_id = SourceId.of(name)
        events = tuple(by_key[(str(source_id), seq)] for seq in range(_MONO_COUNT))
        by_source.append((source_id, IntegrityClass.NONE, events))
    return calibrate.build_profile(
        scenario_family="spectra-vs-properties",
        events_by_source=tuple(by_source),
        phases=_MONO_PHASES,
        excluded=(),
        quantile_levels=("95/100",),
        generator_config_hash=_MONO_GENERATOR_HASH,
        reference_bundle_hash=_MONO_CALIBRATION_BUNDLE,
        reference_run_manifest_hash=canon.hash_ref("manifest", b"calibration"),
        calibration_seed=1000007,
    )


def _mono_binding_context() -> liveness.BindingContext:
    return liveness.BindingContext(
        bundle_hash=_MONO_ANALYSIS_BUNDLE,
        seed=4242,
        generator_config_hash=_MONO_GENERATOR_HASH,
        scenario_family="spectra-vs-properties",
        excluded_intervals_hash=calibrate.excluded_intervals_hash(()),
    )


def _mono_document(
    survivors: frozenset[tuple[str, int]],
    by_key: dict[tuple[str, int], CanonicalEvent],
    profile: calibrate.SourceProfile,
) -> liveness.LivenessDocument:
    sources = []
    for name in _MONO_SOURCES:
        source_id = SourceId.of(name)
        events = tuple(
            by_key[key]
            for key in sorted(survivors)
            if key[0] == str(source_id)
        )
        sources.append(
            liveness.SourceInput(
                source_id=source_id, integrity_class=IntegrityClass.NONE, events=events
            )
        )
    return liveness.build_liveness_document(
        config=_mono_config(),
        sources=tuple(sources),
        phases=_MONO_PHASES,
        scenario_t0_ns=_MONO_EPOCH,
        scenario_t1_ns=_MONO_SPAN_T1,
        profile=profile,
        binding_context=_mono_binding_context(),
    )


def _licensed_region(
    document: liveness.LivenessDocument, source_id: str
) -> tuple[tuple[int, int], ...]:
    """The maximal non-LIVE runs of one source: exactly the region S9 may mint licences over.

    This is the licensed SET, not a summary of it. A BLIND run and a SUPPRESSED run are both
    licensable, so both count; the partition by reason is an accounting question and is not
    what monotonicity is about.
    """
    return tuple(
        (interval.t0_ns, interval.t1_ns)
        for interval in liveness.maximal_non_live_runs(document, source_id)
    )


def _covers(outer: tuple[tuple[int, int], ...], inner: tuple[tuple[int, int], ...]) -> tuple[int, int] | None:
    """The first sub-interval of `inner` that `outer` does not cover, or None. O(n+m)."""
    for low, high in inner:
        cursor = low
        for o_low, o_high in outer:
            if o_high <= cursor:
                continue
            if o_low > cursor:
                break
            cursor = o_high
            if cursor >= high:
                break
        if cursor < high:
            return (cursor, high)
    return None


class TestMonotonicityOfBlindness(unittest.TestCase):
    """Deleting more records never shrinks the licensed set.

    The ladder is built by `degrade.degrade` with the parent chained at every step, so the
    deletion sets are NESTED by construction and the only thing that varies between cells is
    how much telemetry survives. Each cell is then classified by `build_liveness_document`
    against the SAME profile, computed once from the undegraded stream.

    A failure here would be a real defect and a serious one: it would mean that deleting
    records made a source look MORE live, so an attacker could buy a stronger verdict by
    destroying evidence. Do not weaken this test to make it pass.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = _raw_stream(_seeded("monotonicity.stream"))
        cls.by_key = _canonical_by_key(cls.raw)
        cls.profile = _mono_profile(cls.by_key)
        cls.ladders = []
        for ladder_index, seed in enumerate((918273645, 271828182, 161803398)):
            levels = (100, 95, 90, 80, 70, 55, 40, 25)
            cells = []
            parent: degrade.DegradationResult | None = None
            for level in levels:
                result = degrade.degrade(
                    cls.raw, degrade.Completeness.percent(level), seed, parent=parent
                )
                parent = result
                survivors = frozenset(
                    (str(r.source_id), r.seq) for r in result.raw
                )
                cells.append((level, survivors, _mono_document(survivors, cls.by_key, cls.profile)))
            cls.ladders.append((ladder_index, seed, tuple(cells)))

    def test_the_deletion_sets_nest_down_the_ladder(self) -> None:
        """The premise of the property. Without nesting the cells differ by WHICH records
        survived as well as by how many, and no comparison between them means anything."""
        for ladder_index, seed, cells in self.ladders:
            for (upper_level, upper, _), (lower_level, lower, _) in zip(cells, cells[1:]):
                description = f"seed={SEED} dseed={seed} ladder={ladder_index} c={upper_level}->{lower_level}"
                with self.subTest(case=description):
                    self.assertTrue(lower <= upper, description)

    def test_the_licensed_region_never_shrinks_as_completeness_falls(self) -> None:
        """Set containment, not volume: an instant licensable at a higher completeness must
        still be licensable at a lower one. This is the strong form; the volume test below
        is its corollary and is kept because it is the number the premium is computed from."""
        for ladder_index, seed, cells in self.ladders:
            for (upper_level, _, upper_doc), (lower_level, _, lower_doc) in zip(cells, cells[1:]):
                for name in _MONO_SOURCES:
                    higher = _licensed_region(upper_doc, name)
                    lower = _licensed_region(lower_doc, name)
                    description = (
                        f"seed={SEED} dseed={seed} ladder={ladder_index} source={name} "
                        f"c={upper_level}->{lower_level}"
                    )
                    with self.subTest(case=description):
                        uncovered = _covers(lower, higher)
                        self.assertIsNone(
                            uncovered,
                            f"{description}: [{uncovered}] was licensable at c={upper_level} "
                            f"and is not at c={lower_level}; licensed region "
                            f"{higher} shrank to {lower}",
                        )

    def test_the_licensed_volume_never_shrinks_as_completeness_falls(self) -> None:
        """The published accounting, read from the artifact's own members rather than
        recomputed: blind volume by reason plus suppressed volume is the non-LIVE volume."""
        for ladder_index, seed, cells in self.ladders:
            for (upper_level, _, upper_doc), (lower_level, _, lower_doc) in zip(cells, cells[1:]):
                for name in _MONO_SOURCES:
                    higher = _published_non_live_volume(upper_doc, name)
                    lower = _published_non_live_volume(lower_doc, name)
                    description = (
                        f"seed={SEED} dseed={seed} ladder={ladder_index} source={name} "
                        f"c={upper_level}->{lower_level} volume {higher}->{lower}"
                    )
                    with self.subTest(case=description):
                        self.assertGreaterEqual(lower, higher, description)

    def test_the_ladder_actually_moves(self) -> None:
        """Monotonicity is trivially satisfied by a ladder where nothing ever changes, so the
        generated population is required to contain a strict increase."""
        strict = 0
        for _, _, cells in self.ladders:
            for (_, _, upper_doc), (_, _, lower_doc) in zip(cells, cells[1:]):
                for name in _MONO_SOURCES:
                    if _published_non_live_volume(lower_doc, name) > _published_non_live_volume(
                        upper_doc, name
                    ):
                        strict += 1
        self.assertGreater(strict, 30, f"seed={SEED}: the ladder never lost anything")


def _published_non_live_volume(document: liveness.LivenessDocument, source_id: str) -> int:
    entry = document.source(source_id)
    assert entry is not None
    return sum(value for _, value in entry.blind_volume_ns_by_reason) + entry.suppressed_volume_ns


# ---------------------------------------------------------------------------
# 3. DETERMINISM UNDER PERMUTATION
# ---------------------------------------------------------------------------


def _temporal_event(source: str, seq: int, t_ns: int) -> types.SimpleNamespace:
    """The four members the temporal pass reads from a canonical event."""
    return types.SimpleNamespace(
        event_id=f"ev:{source}-{seq:04d}",
        source_id=f"src:{source}",
        seq=seq,
        t_evt_ns=t_ns,
    )


def _temporal_stream(rng: random.Random) -> tuple[types.SimpleNamespace, ...]:
    """A seeded multi-source stream with generated backdates.

    A stream with no contradiction exercises only the feasible path, so some records are
    moved behind their own predecessors on purpose. The pass must name the same timestamps
    whatever order the records arrive in.
    """
    events: list[types.SimpleNamespace] = []
    for source_index in range(rng.randrange(1, 4)):
        source = f"s{source_index}"
        instant = 100 * SECOND
        count = rng.randrange(2, 10)
        for seq in range(count):
            instant += rng.randrange(1, 12) * SECOND
            t_ns = instant
            if rng.random() < 0.25:
                t_ns = max(SECOND, instant - rng.randrange(1, 60) * SECOND)
            events.append(_temporal_event(source, seq, t_ns))
    return tuple(events)


class TestDeterminismUnderPermutation(unittest.TestCase):
    """Permuting the order of input events changes no artifact.

    Both stages under test sort their inputs internally, so this asserts that the sort is
    total and that nothing downstream of it iterates a set or a dict whose order depends on
    insertion. A failure means a hash written into a certificate depends on the order a
    reader happened to feed records in, and `spectra_vs_verify` could not reproduce it from
    the same bundle.
    """

    @classmethod
    def setUpClass(cls) -> None:
        raw = _raw_stream(_seeded("permutation.stream"))
        cls.by_key = _canonical_by_key(raw)
        cls.profile = _mono_profile(cls.by_key)
        thinned = degrade.degrade(raw, degrade.Completeness.percent(70), 424242)
        cls.survivors = frozenset((str(r.source_id), r.seq) for r in thinned.raw)

    def test_permuting_the_input_events_leaves_the_liveness_bytes_identical(self) -> None:
        """The breakpoint grid is a sorted set union, so permuting the records that feed it
        and the envelope stage's query endpoints must union to the same grid. The endpoint
        SET is drawn once and only its order varies, because that is the normative statement
        in the liveness section: permuting the query order yields a byte-identical
        `liveness.json`."""
        rng = _seeded("permutation.liveness")
        endpoints = [
            _MONO_EPOCH + rng.randrange(0, _MONO_COUNT) * _MONO_PERIOD for _ in range(6)
        ]
        reference: bytes | None = None
        for index in range(24):
            source_inputs: list[liveness.SourceInput] = []
            for name in _MONO_SOURCES:
                source_id = SourceId.of(name)
                events = [
                    self.by_key[key]
                    for key in sorted(self.survivors)
                    if key[0] == str(source_id)
                ]
                rng.shuffle(events)
                source_inputs.append(
                    liveness.SourceInput(
                        source_id=source_id,
                        integrity_class=IntegrityClass.NONE,
                        events=tuple(events),
                    )
                )
            rng.shuffle(source_inputs)
            rng.shuffle(endpoints)
            description = (
                f"seed={SEED} permutation={index} "
                f"sources={[s.source_id.snake for s in source_inputs]} endpoints={endpoints}"
            )
            with self.subTest(case=description):
                document = liveness.build_liveness_document(
                    config=_mono_config(),
                    sources=tuple(source_inputs),
                    phases=_MONO_PHASES,
                    scenario_t0_ns=_MONO_EPOCH,
                    scenario_t1_ns=_MONO_SPAN_T1,
                    profile=self.profile,
                    binding_context=_mono_binding_context(),
                    query_endpoints=tuple(endpoints),
                )
                produced = document.canonical_bytes()
                if reference is None:
                    reference = produced
                self.assertEqual(
                    liveness.liveness_hash(document),
                    canon.hash_ref("live", reference),
                    description,
                )
                self.assertEqual(produced, reference, description)

    def test_permuting_the_input_events_leaves_the_temporal_pass_identical(self) -> None:
        rng = _seeded("permutation.temporal")
        for index in range(40):
            events = _temporal_stream(rng)
            canonical = temporal.run_pass(events, cap=8)
            shuffled = list(events)
            rng.shuffle(shuffled)
            description = (
                f"seed={SEED} case={index} "
                f"events={[(e.source_id, e.seq, e.t_evt_ns // SECOND) for e in events]} "
                f"order={[e.event_id for e in shuffled]}"
            )
            with self.subTest(case=description):
                permuted = temporal.run_pass(tuple(shuffled), cap=8)
                self.assertEqual(permuted.constraints, canonical.constraints, description)
                self.assertEqual(permuted.violations, canonical.violations, description)
                self.assertEqual(
                    permuted.correction_set, canonical.correction_set, description
                )
                self.assertEqual(
                    permuted.disputed_sources, canonical.disputed_sources, description
                )
                self.assertEqual(permuted, canonical, description)

    def test_the_permuted_streams_are_not_all_already_consistent(self) -> None:
        """A stream with nothing to correct exercises none of the ordering-sensitive code,
        so the generated population is required to contain contradictions."""
        rng = _seeded("permutation.temporal")
        disputed = 0
        for _ in range(40):
            if temporal.run_pass(_temporal_stream(rng), cap=8).correction_set:
                disputed += 1
        self.assertGreater(disputed, 10, f"seed={SEED}: no generated stream was disordered")


# ---------------------------------------------------------------------------
# 4. THE TWO-SIDED BRACKET ORDERS
# ---------------------------------------------------------------------------


def _generated_program_pair(
    rng: random.Random, atoms
) -> tuple[ReachProgram, ReachProgram, str]:
    """A layered AND/OR hypergraph and a superset of it, plus a printable description.

    The lower program is observed instances only. The upper one is the lower one plus
    licensed instances over the same and some additional facts, which is exactly the shape
    S9 produces: `P_max = P_min` union licensed silent instances union GHOSTs. Containment
    is structural here, as it is in S9, so what is under test is the ORDER the two programs
    induce on derivability and not the containment itself.

    Every instance gets a distinct rule id so that no two instances collide on the content
    hash that is their identity; the shapes are otherwise generated.
    """
    literals = atoms.literals
    layers: list[list[model.Fact]] = [
        [
            model.Fact.mint(
                "axiom.seed",
                (ids.EntityId.mint("resource", f"seed_{i}".encode("ascii")),),
                1,
            )
            for i in range(rng.randrange(2, 4))
        ]
    ]
    for depth in range(1, 4):
        layers.append(
            [
                model.Fact.mint(
                    f"layer{depth}.fact",
                    (ids.EntityId.mint("resource", f"n_{depth}_{i}".encode("ascii")),),
                    depth + 1,
                )
                for i in range(rng.randrange(2, 4))
            ]
        )

    rule_counter = [1]

    def next_rule() -> ids.RuleId:
        value = rule_counter[0]
        rule_counter[0] += 1
        return ids.RuleId.of(f"r{value:04d}")

    def blockers() -> tuple[int, ...]:
        picked = rng.sample(list(literals), rng.randrange(0, 3))
        return tuple(sorted({1 << literal.bit for literal in picked}))

    def evidence(tag: str) -> tuple[model.EvidenceRef, ...]:
        return (
            model.EvidenceRef(
                binding="slot_a",
                event_id=ids.EventId.mint(tag.encode("ascii")),
                source_id=ids.SourceId.of("res_access"),
                t_evt_ns=_MONO_EPOCH,
            ),
        )

    licence = model.Licence.mint(
        source_id=ids.SourceId.of("iam_audit"),
        interval=model.Interval(_MONO_EPOCH, _MONO_EPOCH + 2400 * SECOND),
        basis=model.LicenceBasis.BLIND,
        reason="B_GAP_EXCEEDS_THRESHOLD",
    )

    lower: list[model.RuleInstance] = []
    upper_only: list[model.RuleInstance] = []
    for depth in range(1, 4):
        for head in layers[depth]:
            pool = [f for lower_depth in range(depth) for f in layers[lower_depth]]
            for _ in range(rng.randrange(1, 3)):
                body = tuple(
                    sorted(
                        {
                            f.fact_key
                            for f in rng.sample(pool, min(len(pool), rng.randrange(1, 3)))
                        },
                        key=str,
                    )
                )
                observed = rng.random() < 0.65
                rule_id = next_rule()
                if observed:
                    lower.append(
                        model.RuleInstance.mint(
                            rule_id=rule_id,
                            rule_version="1.0.0",
                            head=head.fact_key,
                            body=body,
                            blockers=blockers(),
                            observed=model.Observation.OBSERVED,
                            tick=depth + 1,
                            evidence=evidence(f"ev:{rule_id}"),
                        )
                    )
                else:
                    upper_only.append(
                        model.RuleInstance.mint(
                            rule_id=rule_id,
                            rule_version="1.0.0",
                            head=head.fact_key,
                            body=body,
                            blockers=blockers(),
                            observed=model.Observation.LICENSED,
                            tick=depth + 1,
                            license_ids=(licence.license_id,),
                        )
                    )

    goal = layers[3][0]
    axioms = tuple(sorted((f.fact_key for f in layers[0]), key=str))

    def build(kind, instances) -> ReachProgram:
        return ReachProgram.build(
            kind=kind,
            instances=tuple(sorted(instances, key=lambda i: str(i.instance_id))),
            axioms=axioms,
            goal=goal.fact_key,
        )

    description = (
        f"axioms={len(layers[0])} layers={[len(l) for l in layers]} "
        f"observed={len(lower)} licensed={len(upper_only)}"
    )
    return build(model.ProgramKind.P_MIN, lower), build(
        model.ProgramKind.P_MAX, lower + upper_only
    ), description


class TestBracketOrders(unittest.TestCase):
    """For the same cut, derivable in the lower program implies derivable in the upper one.

    The contrapositive is the safe direction the whole verdict ladder rests on: goal not in
    `fix(P_max, S)` implies goal not in `fix(P_min, S)`, which is what makes ROBUST
    conservative. Both directions are one statement about the least fixpoint being monotone
    in the program, and it is checked over the WHOLE admissible-cut lattice rather than a
    sample, because a mutation to the blocker test would be invisible at a sampled cut.

    A failure means an attack route visible in the observed program vanished from the
    licensed one, so the bracket would no longer bracket anything.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.atoms = vs_fixtures.atom_table()
        cls.masks = admissible_cut_masks(cls.atoms.literals)

    def test_the_lattice_is_the_whole_admissible_set(self) -> None:
        self.assertEqual(len(self.masks), 162)

    def test_a_goal_derivable_in_the_lower_program_is_derivable_in_the_upper_one(self) -> None:
        rng = _seeded("bracket")
        witnessed = 0
        for index in range(40):
            lower, upper, shape = _generated_program_pair(rng, self.atoms)
            for mask in self.masks:
                description = (
                    f"seed={SEED} case={index} cut={canon.mask_hex(mask)} {shape}"
                )
                with self.subTest(case=description):
                    low = reach(lower, mask)
                    high = reach(upper, mask)
                    if low.derivable:
                        witnessed += 1
                        self.assertTrue(
                            high.derivable,
                            f"{description}: the goal is derivable in PMin and not in PMax",
                        )
                    if not high.derivable:
                        self.assertFalse(
                            low.derivable,
                            f"{description}: PMax severs the goal and PMin does not",
                        )
        self.assertGreater(
            witnessed, 200, f"seed={SEED}: no generated cut ever derived the goal"
        )

    def test_the_lower_closure_is_contained_in_the_upper_closure_under_every_cut(self) -> None:
        """The stronger statement the derivability order follows from: `P_min` a subset of
        `P_max` implies `reach(P_min, S).U` a subset of `reach(P_max, S).U`, for every S."""
        rng = _seeded("bracket.closure")
        for index in range(30):
            lower, upper, shape = _generated_program_pair(rng, self.atoms)
            for mask in self.masks:
                description = f"seed={SEED} case={index} cut={canon.mask_hex(mask)} {shape}"
                with self.subTest(case=description):
                    low = {str(f) for f in reach(lower, mask).closure}
                    high = {str(f) for f in reach(upper, mask).closure}
                    self.assertEqual(
                        sorted(low - high),
                        [],
                        f"{description}: facts derived in PMin and not in PMax",
                    )

    def test_the_fixture_cells_obey_the_same_order(self) -> None:
        """The generated programs are shapes; these two are the slice's own cells, and the
        degraded one is the case the property was written for - route B exists in the upper
        program only."""
        for label, cell in (
            ("complete", vs_fixtures.cell_complete(self.atoms)),
            ("degraded", vs_fixtures.cell_degraded(self.atoms)),
        ):
            for mask in self.masks:
                description = f"seed={SEED} cell={label} cut={canon.mask_hex(mask)}"
                with self.subTest(case=description):
                    if reach(cell.p_min, mask).derivable:
                        self.assertTrue(reach(cell.p_max, mask).derivable, description)


# ---------------------------------------------------------------------------
# 5. THE SEQ FEASIBILITY FUNCTION
# ---------------------------------------------------------------------------


def _brute_force_seq_feasible(
    left: tuple[int, int], right: tuple[int, int], within: int
) -> bool:
    """The reference: enumerate every placement and ask whether one satisfies the bound.

    This is the definition `ground.seq_feasible` claims to compute in closed form -
    "whether SOME left time and SOME right time satisfy `left < right <= left + within`" -
    written the slow, obviously-correct way. It is only usable over small ranges, which is
    why the ranges below are small and the coverage is exhaustive rather than sampled.
    """
    for l_time in range(left[0], left[1] + 1):
        for r_time in range(right[0], right[1] + 1):
            if l_time < r_time <= l_time + within:
                return True
    return False


class TestSeqFeasibility(unittest.TestCase):
    """`ground.seq_feasible` against a brute-force reference, exhaustively.

    WHY EXHAUSTIVELY. The previous behaviour skipped the comparison whenever either side was
    licensed, which admitted an escalation licensed in the first second of the horizon paired
    with an export 76 minutes later under a 30-minute rule. That put a control in the
    blindness premium at full telemetry for no reason a sensor could explain, and it is
    recorded as INC-0010. A sampled test would not have found it and will not find its
    successor, so every combination in the range is checked.

    A failure in the TRUE direction admits a combination no placement realizes, which
    inflates `P_max` and can manufacture a blindness premium. A failure in the FALSE
    direction drops a real possibility from `P_max`, which is the unsafe direction: it can
    make an unreachable claim that is not true of every realizable world.
    """

    #: The tick range every enumeration runs over. Small on purpose: the reference is
    #: quadratic in it and the property is about the closed form, not about magnitude.
    BOUND = 8

    def test_an_observed_pair_reduces_to_the_plain_bound(self) -> None:
        """For observed points the function must be `left < right <= left + within` exactly.

        An observed fact is the single instant it was observed at, so there is nothing to
        over-approximate: any widening here would be invented precision in the other
        direction."""
        checked = 0
        for left in range(self.BOUND):
            for right in range(self.BOUND):
                for within in range(0, 7):
                    description = (
                        f"seed={SEED} left=({left},{left}) right=({right},{right}) "
                        f"within={within}"
                    )
                    with self.subTest(case=description):
                        self.assertEqual(
                            seq_feasible((left, left), (right, right), within),
                            left < right <= left + within,
                            description,
                        )
                    checked += 1
        self.assertEqual(checked, self.BOUND * self.BOUND * 7)

    def test_an_observed_pair_agrees_with_the_brute_force_reference(self) -> None:
        """The same cases through the reference, so that the plain bound above and the
        enumeration below are pinned to each other and not only to the implementation."""
        for left in range(self.BOUND):
            for right in range(self.BOUND):
                for within in range(0, 7):
                    description = (
                        f"seed={SEED} left=({left},{left}) right=({right},{right}) "
                        f"within={within}"
                    )
                    with self.subTest(case=description):
                        self.assertEqual(
                            seq_feasible((left, left), (right, right), within),
                            _brute_force_seq_feasible((left, left), (right, right), within),
                            description,
                        )

    def test_an_interval_pair_is_feasible_exactly_when_some_placement_is(self) -> None:
        """Every closed tick range against every other, for every positive bound.

        A licensed fact is the span of the blind window its step could have occupied, so the
        answer must be "some placement works", never "the representative tick works"."""
        checked = 0
        for l_lo in range(self.BOUND):
            for l_hi in range(l_lo, self.BOUND):
                for r_lo in range(self.BOUND):
                    for r_hi in range(r_lo, self.BOUND):
                        for within in range(1, 7):
                            left, right = (l_lo, l_hi), (r_lo, r_hi)
                            description = (
                                f"seed={SEED} left={left} right={right} within={within}"
                            )
                            with self.subTest(case=description):
                                self.assertEqual(
                                    seq_feasible(left, right, within),
                                    _brute_force_seq_feasible(left, right, within),
                                    description,
                                )
                            checked += 1
        self.assertEqual(checked, 36 * 36 * 6)

    def test_a_zero_width_bound_admits_no_pair_at_all(self) -> None:
        """REGRESSION for a defect this file found. At `within == 0` the closed form was
        wrong for every pair where at least one side is an interval.

        WHAT WAS OBSERVED, before the fix. `seq_feasible` was
        `(r_hi - l_lo) > 0 and (r_lo - l_hi) <= within`. The difference `right - left`
        ranges over `[r_lo - l_hi, r_hi - l_lo]` and the bound asks for a difference in
        `(0, within]`, so the two intervals meet iff `r_hi - l_lo >= 1` AND
        `r_lo - l_hi <= within`. That derivation is right for `within >= 1` and wrong for
        `within == 0`, where `(0, 0]` is EMPTY and no difference can land in it. The
        smallest reproducer is `seq_feasible((0, 1), (0, 1), 0)`, which returns True; no
        placement satisfies `l < r <= l + 0`, so the answer is False. Exhaustively over
        `0 <= l_lo <= l_hi < 8`, `0 <= r_lo <= r_hi < 8` there are 245 such pairs, and every
        single mismatch between the implementation and the reference has `within == 0`.

        WHY IT IS REACHABLE. `rules._parse_temporal` defaults `within` to 0 when a `seq`
        operator omits the `within` key, and `rules.duration_ticks("0s")` is a valid 0. The
        shipped `config/vs/rules.toml` gives every `seq` rule a positive bound, so nothing in
        the slice hits it today - it is latent, not live.

        WHICH DIRECTION IT FAILS IN. TRUE where the reference says False, so `P_max` would
        over-admit rather than under-admit. That keeps ROBUST sound, but it is precisely the
        INC-0010 shape: a pair impossible for EVERY placement admitted into the envelope,
        which can put a control in the blindness premium that no sensor gap explains.

        THE FIX WAS ONE CONJUNCT, not a change to this test: the meet is now written
        `max(r_lo - l_hi, 1) <= min(r_hi - l_lo, within)`, which is empty at `within == 0`
        by construction. The test was written failing on purpose, under
        `expectedFailure`, and the decorator came off with the fix.
        """
        mismatches: list[tuple[tuple[int, int], tuple[int, int]]] = []
        for l_lo in range(self.BOUND):
            for l_hi in range(l_lo, self.BOUND):
                for r_lo in range(self.BOUND):
                    for r_hi in range(r_lo, self.BOUND):
                        left, right = (l_lo, l_hi), (r_lo, r_hi)
                        if seq_feasible(left, right, 0) != _brute_force_seq_feasible(
                            left, right, 0
                        ):
                            mismatches.append((left, right))
        self.assertEqual(
            mismatches,
            [],
            f"seed={SEED}: {len(mismatches)} pairs disagree with the reference at "
            f"within=0; smallest is left={mismatches[0][0]} right={mismatches[0][1]}"
            if mismatches
            else "",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
