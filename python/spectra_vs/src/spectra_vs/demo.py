"""THE DEMONSTRATION: two completeness cells and one pre-registered blackout cell.

WHY THIS FILE EXISTS. The slice exists to show two things and nothing else:

  1. that missing telemetry becomes an EXPLICIT, NAMED, RE-CHECKABLE LICENCE for an
     unobserved attacker step, rather than a silent gap or an assumption inside a
     heuristic;
  2. the separation between a control that is genuinely needed and a control that is in
     the cut ONLY because a sensor could not see. That difference is the blindness premium.

Both cells are printed. The full-telemetry cell is the CONTROL ARM: without it the other
cell demonstrates nothing, because a premium that is non-empty everywhere is not evidence
about blindness. If the premium at the degraded cell is empty, that is printed as the
result it is; the scenario, the seed, the thresholds and the completeness levels are not
adjusted to produce a prettier one.

The headline compares the control arm with the BLACKOUT CELL: one sensor taken offline over
one window, registered with its predictions in docs/research/prereg-0001-blackout-cell.md
before the operator existed. The falsifiers are evaluated in code, only for the seeds the
prediction was made for. The random 70% cell is kept as a degradation-matrix cell.

EXIT STATUS. 0 when every certificate is accepted and the prediction held or was not
evaluated; 1 when the separate checker rejects a certificate; 2 when the prediction failed.

WHAT NOTHING HERE MEANS. No number printed below is measured. There is no Rust kernel, no
Go checker, no C guard VM and no Docker range; telemetry is the output of a seeded
synthetic generator and the attack it contains is simulated and did not happen. A cut
severs a chain IN THE MODEL, under this rule table and this control catalog, over the
telemetry actually ingested, against a non-adaptive attacker. It prevented nothing and
would have stopped nothing.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from spectra_core import canon, model
from spectra_vs import cert as cert_mod
from spectra_vs import degrade as degrade_mod
from spectra_vs import liveness as liveness_mod
from spectra_vs import pipeline as pipeline_mod

__all__ = ["CELLS", "main", "render_cell", "render_difference"]

#: The two cells of the minimum-viable design: full telemetry, then the degraded cell.
#: Fixed here rather than taken from the command line, because a completeness level chosen
#: after seeing the answer is a fitted parameter and a fitted premium is worthless.
CELLS: tuple[tuple[str, degrade_mod.Completeness], ...] = (
    ("c=100%  full telemetry (CONTROL ARM)", degrade_mod.Completeness.of(1, 1)),
    ("c=70%   degraded cell", degrade_mod.Completeness.of(7, 10)),
)

_RULE = "=" * 96
_THIN = "-" * 96


@dataclass(frozen=True, slots=True)
class Rendered:
    """One cell's printable summary, kept as data so the difference block can re-read it."""

    label: str
    cell: pipeline_mod.CellResult

    @property
    def premium(self) -> tuple[str, ...]:
        result = self.cell.prove.premium
        if not result.published:
            return ()
        return tuple(str(c) for c in result.blindness_premium)

    @property
    def premium_published(self) -> bool:
        return self.cell.prove.premium.published


def _raised(cut: model.Cut) -> tuple[tuple[str, int], ...]:
    levels: dict[str, int] = {}
    for atom in cut.atoms:
        key = str(atom.control_id)
        levels[key] = max(levels.get(key, 0), atom.level)
    return tuple(sorted(levels.items(), key=lambda kv: canon.byte_order_key(kv[0])))


def _render_cut(cut: model.Cut) -> str:
    raised = _raised(cut)
    if not raised:
        return "(no control raised)"
    return ", ".join(f"{name} >= {level}" for name, level in raised)


def _licence_line(licence: model.Licence) -> str:
    """A licence is a permission for a step nobody could have seen. Never an observation."""
    span_ns = licence.t1_ns - licence.t0_ns
    minutes = span_ns // 60_000_000_000
    basis = str(licence.basis)
    witness = (
        " no witness (a BLIND licence records that nobody could have seen)"
        if basis == "BLIND"
        else f" bracketed by {len(licence.witness)} record ids"
    )
    return (
        f"{licence.license_id}  {licence.source_id}  [{licence.t0_ns}, {licence.t1_ns})"
        f"  {minutes} min  {basis}/{licence.reason}{witness}"
    )


def render_cell(rendered: Rendered) -> str:
    """Everything one cell has to show: cut, cardinality, minimality, verdict, flags, premium."""
    cell = rendered.cell
    prove = cell.prove
    out: list[str] = []
    add = out.append

    add(_RULE)
    add(rendered.label)
    add(_RULE)
    add(f"run_id            {cell.run_id}")
    add(f"run directory     {cell.run_dir}")
    add(
        f"completeness      {cell.completeness.num}/{cell.completeness.den} exact rational"
        f"   (deleted {len(cell.degrade.result.removed)} of "
        f"{len(cell.gen.result.raw)} simulated records, delete-only)"
    )
    add(
        f"seeds             analysis 0x{cell.seed:016x}, degradation "
        f"0x{cell.degradation_seed:016x}, calibration band is disjoint"
    )
    add(f"bundle            {len(cell.ingest.result.events)} sealed records")
    add(
        f"programs          P_min {len(cell.ground.result.program.instances)} observed "
        f"instances / P_max {len(cell.envelope.result.p_max.instances)} instances "
        f"({prove.silent_count} silent)"
    )
    add(
        f"counts            observed_event_count {prove.observed_event_count}, "
        f"ghost_count {prove.ghost_count}   (two members, never summed)"
    )
    add(
        f"goal library      {len(prove.goal_library)} fact(s) of the bound goal predicate"
        + ("" if prove.goal_resolved else "   (EMPTY: proving against a sentinel key)")
    )
    add("")

    add("LIVENESS (the only producer of licences; no threshold comes from this run)")
    for source in cell.liveness.document.sources:
        blind = {str(r): v for r, v in source.blind_volume_ns_by_reason}
        parts = ", ".join(f"{k}={v}ns" for k, v in sorted(blind.items())) or "no blind volume"
        add(f"  {source.source_id!s:<16} mode {source.mode:<16} {parts}")
    add("")

    add("LICENCES RELIED ON (a licence is a permission for an unobserved step)")
    if not prove.licences:
        add("  none: no silent instance is licensed in this cell")
    for licence in prove.licences:
        add(f"  {_licence_line(licence)}")
    if cell.envelope.result.blind_spots:
        add("")
        add(
            "PERMANENT BLIND SPOTS (obligation unsatisfied AND unlicensed; no GHOST is "
            "created, because the honest answer is that the step is invisible)"
        )
        for spot in cell.envelope.result.blind_spots:
            add(
                f"  {spot.rule_id} {spot.head_predicate} over "
                f"[{spot.t0_ns}, {spot.t1_ns}) on "
                f"{', '.join(str(s) for s in spot.producing_sources)}: {spot.reason}"
            )
    add("")

    add("THE TWO-SIDED BRACKET (a pair, never a confidence interval)")
    lower = prove.bracket.lower
    upper = prove.bracket.upper
    add(
        f"  Psi_min  {len(lower.psi.corridors)} corridors, complete={lower.psi.complete}"
        f"     Psi_max  {len(upper.psi.corridors)} corridors, "
        f"complete={upper.psi.complete}"
    )
    add(f"  cut over P_min   {_render_cut(lower.cut)}")
    add(
        f"                   cardinality {lower.cut.cardinality} raised controls   "
        f"minimality {lower.minimality}"
    )
    add(f"                   {cert_mod.render_minimality(lower.cut.minimality)}")
    add(f"  cut over P_max   {_render_cut(upper.cut)}")
    add(
        f"                   cardinality {upper.cut.cardinality} raised controls   "
        f"minimality {upper.minimality}"
    )
    add(f"                   {cert_mod.render_minimality(upper.cut.minimality)}")
    add("")

    add("VERDICTS, each with the scope it is relative to")
    add("  proving with S = the cut over P_min:")
    for line in cert_mod.render_long(prove.verdict_at_cut_min, prove.scope).splitlines():
        add(f"    {line}")
    add("  proving with S = the cut over P_max:")
    for line in cert_mod.render_long(prove.verdict_at_cut_max, prove.scope).splitlines():
        add(f"    {line}")
    robust = cert_mod.Safety.ROBUST
    if robust in (prove.verdict_at_cut_min.safety, prove.verdict_at_cut_max.safety):
        add(
            "  ROBUST requires a NoTamperToken, which the liveness stage mints only when no "
            "source is tamper-suspected. The check behind it (ADR-0016) compares recorded"
        )
        add(
            "  timestamps against the order their own source recorded, and nothing else: a "
            "consistently rewritten source, a forged chain and suppression on a source"
        )
        add("  without a sequence number are all invisible to it.")
    add("")

    add("FLAGS SET")
    add(f"  {', '.join(prove.flags) if prove.flags else 'none'}")
    # A result, not an absent check, since ADR-0016 - but a narrow one, and the line says
    # how narrow rather than letting "none" read as "no tampering found".
    disputed = cell.liveness.document.disputed_events
    if disputed:
        add(
            f"  TEMPORAL DISPUTE: {len(disputed)} recorded timestamp(s) contradict their "
            "source's own order. The licences resting on them are RETAINED in P_max;"
        )
        add("  only the verdict is weakened. Voiding them would reward the tampering.")
        for event in disputed:
            add(f"    {event.event_id}  {event.source_id}  recorded at {event.t_evt_ns}")
    else:
        add(
            "  No recorded timestamp contradicts the order its own source recorded. That is "
            "what the pass checks and all it checks."
        )
    add("")

    add("BLINDNESS PREMIUM   B = NEC(Psi_max) \\ OCC(Psi_min)")
    result = prove.premium
    if not result.published:
        add(
            f"  ABSENT. premium_suppressed_reason = {result.suppressed_reason}. "
            "The member is omitted entirely, not null, not [] and not 0."
        )
    else:
        add(f"  NEC(Psi_max)  {', '.join(str(c) for c in result.nec_max) or '(empty)'}")
        add(f"  OCC(Psi_min)  {', '.join(str(c) for c in result.occ_min) or '(empty)'}")
        premium = rendered.premium
        if not premium:
            add("  B             EMPTY")
        else:
            add(f"  B             {', '.join(premium)}")
            for entry in prove.premium_entries:
                deficiency = entry.calibration_deficiency
                phrase = (
                    "needed because this run was not calibrated for this source"
                    if deficiency > 0
                    else "rests on observed-gap licences"
                )
                add(
                    f"                {entry.control_id}: "
                    f"calibration_deficiency {deficiency.numerator}/"
                    f"{deficiency.denominator} -- {phrase}"
                )
    add("")
    add(
        f"cut_delta_canonical  {', '.join(str(c) for c in prove.cut_delta) or '(empty)'}"
    )
    add(f"  {cert_mod.CUT_DELTA_CAPTION}")
    add("")
    for line in _witness_lines(cell):
        add(line)
    add(f"certificate       {prove.cert_path}")
    if cell.verify_exit is not None:
        add(
            f"S11 checker       exit {cell.verify_exit} "
            f"({'ACCEPT' if cell.verify_exit == 0 else 'REJECT'})"
        )
        for line in cell.verify_text.splitlines():
            add(f"  | {line}")
    if cell.complaints:
        add("")
        add("SEAMS REPORTED BY THIS RUN (config files authored against different vocabularies)")
        for complaint in cell.complaints:
            add(f"  - {complaint}")
    return "\n".join(out)


def _witness_lines(cell: pipeline_mod.CellResult) -> list[str]:
    """The witnesses exactly as the certificate publishes them, one line per step.

    Read back from the certificate body - the flat node lists of ADR-0015 - rather than
    from the pipeline's own objects, so what is printed is what the checker was given.
    """
    body = cell.prove.body
    witnesses = body["witnesses"]
    if not witnesses:
        return []
    instances = {i["instance_id"]: i for i in body["instances"]}
    # Label each step by the predicate of the fact it actually heads, not by its rule's
    # head pattern: a GHOST instance heads an obligation-forced premise, which is not the
    # rule's head, and the first version of this block printed the wrong predicate for it.
    predicates = {str(f.fact_key): f.predicate for f in cell.envelope.result.p_max.facts}
    basis = {
        "OBSERVED": "cites {n} record(s)",
        "GHOST": "unobserved, obligation-forced; licence {lic}",
        "LICENSED": "unobserved, licensed silent step; licence {lic}",
    }
    lines = [
        "WITNESSES IN THE CERTIFICATE (the derivation that returns when one control is "
        "dropped from the cut over P_max)",
    ]
    for entry in witnesses:
        nodes = entry["nodes"]
        unobserved = sum(1 for n in nodes if n["kind"] != "OBSERVED")
        lines.append(
            f"  without {entry['removed_control']}: {len(nodes)} step(s), "
            f"{unobserved} unobserved"
        )
        depth = {0: 0}
        for index, node in enumerate(nodes):
            inst = instances[node["instance_id"]]
            text = basis[node["kind"]].format(
                n=len(node["evidence"]),
                lic=", ".join(lic[:20] for lic in inst["license_ids"]),
            )
            lines.append(
                f"    {'  ' * depth[index]}{inst['rule_id']} "
                f"{predicates.get(inst['head'], '(unnamed fact)'):<24} "
                f"{node['kind']:<9} {text}"
            )
            for child in node["children"]:
                depth[child] = depth[index] + 1
    lines.append(
        "  Drawn from P_max: one tree may combine silent steps that no single consistent "
        "world realizes."
    )
    lines.append("")
    return lines


#: Pre-registration 0001, docs/research/prereg-0001-blackout-cell.md. These values were
#: committed in ce8ed9c BEFORE the blackout operator existed or ran. They are compared
#: mechanically below and must not be edited to match a result; a different prediction is a
#: new pre-registration.
PREREG_0001_SOURCE: str = "iam_audit"
PREREG_0001_WINDOW_S: tuple[int, int] = (4200, 4800)
PREREG_0001_PSI_MIN: int = 1
PREREG_0001_PSI_MAX: int = 2
PREREG_0001_PREMIUM: tuple[str, ...] = ("ctl:priv_approval",)

#: The registration fixes "the same generator seed" and "the same calibration profile" as the
#: full-telemetry cell, which was run with the defaults of the day. They are pinned here as
#: literals, so that changing a default does not silently point the prediction at a run it was
#: never made for. Under any other seed the prediction is not evaluated at all.
PREREG_0001_ANALYSIS_SEED: int = 7
PREREG_0001_CALIBRATION_SEED: int = 1000007

#: Exit statuses of `main`, distinct so a gate can tell a rejected certificate from a failed
#: prediction without parsing the transcript.
EXIT_OK: int = 0
EXIT_CHECKER_REJECTED: int = 1
EXIT_PREDICTION_FAILED: int = 2


def prereg_0001_blackout(epoch_ns: int) -> degrade_mod.Blackout:
    """The intervention exactly as registered: one source, one window, nothing else."""
    lo, hi = PREREG_0001_WINDOW_S
    return degrade_mod.Blackout(
        sources=(PREREG_0001_SOURCE,),
        t0_ns=epoch_ns + lo * 1_000_000_000,
        t1_ns=epoch_ns + hi * 1_000_000_000,
    )


def prereg_0001_applies(*, seed: int, calibration_seed: int) -> bool:
    """Whether this run is the one the prediction was registered for."""
    return seed == PREREG_0001_ANALYSIS_SEED and calibration_seed == PREREG_0001_CALIBRATION_SEED


def prereg_0001_checks(cell: Rendered) -> tuple[tuple[str, bool, str], ...]:
    """Each registered falsifier as (name, passed, observed), evaluated in code."""
    prove = cell.cell.prove
    psi_min = len(prove.bracket.lower.psi.corridors)
    psi_max = len(prove.bracket.upper.psi.corridors)
    premium = tuple(sorted(cell.premium)) if cell.premium_published else None
    checks = (
        ("premium published", premium is not None, f"{'published' if premium is not None else 'suppressed'}"),
        ("premium non-empty", bool(premium), f"{premium or '()'}"),
        (
            f"premium == {PREREG_0001_PREMIUM}",
            premium == PREREG_0001_PREMIUM,
            f"{premium}",
        ),
        (f"|Psi_min| == {PREREG_0001_PSI_MIN}", psi_min == PREREG_0001_PSI_MIN, f"{psi_min}"),
        (f"|Psi_max| == {PREREG_0001_PSI_MAX}", psi_max == PREREG_0001_PSI_MAX, f"{psi_max}"),
    )
    return checks


def prereg_0001_held(cell: Rendered) -> bool:
    return all(ok for _, ok, _ in prereg_0001_checks(cell))


def render_prereg_0001(cell: Rendered) -> str:
    """Render the falsifiers and the verdict on the prediction."""
    checks = prereg_0001_checks(cell)
    out = [
        _RULE,
        "PRE-REGISTRATION 0001 -- predictions committed in ce8ed9c before the intervention existed",
        _RULE,
    ]
    for name, ok, observed in checks:
        out.append(f"  {'PASS' if ok else 'FAIL'}  {name:<42} observed {observed}")
    held = all(ok for _, ok, _ in checks)
    out.append(_THIN)
    out.append(
        "  PREDICTION HELD." if held else
        "  PREDICTION FAILED. Reported as the result it is; the window will not be moved."
    )
    return "\n".join(out)


def render_difference(cells: tuple[Rendered, ...]) -> str:
    """The headline: what changed between the two cells, in one short block."""
    out: list[str] = []
    add = out.append
    add(_RULE)
    add("THE DIFFERENCE BETWEEN THE TWO CELLS -- the headline")
    add(_RULE)

    control, degraded = cells[0], cells[1]
    for name, rendered in (("full telemetry", control), ("blackout cell", degraded)):
        prove = rendered.cell.prove
        premium = (
            "ABSENT (" + str(prove.premium.suppressed_reason) + ")"
            if not rendered.premium_published
            else (", ".join(rendered.premium) if rendered.premium else "EMPTY")
        )
        add(
            f"  {name:<16} |Psi_min|={len(prove.bracket.lower.psi.corridors)} "
            f"|Psi_max|={len(prove.bracket.upper.psi.corridors)}  "
            f"r_min={prove.bracket.lower.cut.cardinality} "
            f"r_max={prove.bracket.upper.cut.cardinality}  "
            f"licences={len(prove.licences)}  premium={premium}"
        )
    add(_THIN)

    gained = tuple(c for c in degraded.premium if c not in set(control.premium))
    lost = tuple(c for c in control.premium if c not in set(degraded.premium))
    if not control.premium_published or not degraded.premium_published:
        add(
            "  The premium is suppressed in at least one cell, so the two cells are not "
            "comparable on this axis and no difference is claimed."
        )
    elif gained and not control.premium:
        add(
            "  Degrading telemetry added "
            + ", ".join(gained)
            + " to the blindness premium: those controls are in the robust cut not "
            "because anyone saw the step they block, but because for the length of a "
            "blind window nobody could have."
        )
    elif not degraded.premium and not control.premium:
        add(
            "  The blindness premium is EMPTY IN BOTH CELLS. That is the result, reported "
            "as one. Nothing was tuned to avoid it: the scenario, the seed, the thresholds "
            "and the two completeness levels are exactly what the design fixes them at."
        )
    else:
        if control.premium:
            add(
                "  THE CONTROL ARM IS NOT CLEAN. The premium at FULL telemetry is already "
                "non-empty ("
                + ", ".join(control.premium)
                + "), so it is not evidence"
            )
            add(
                "  about degradation and the degraded cell has nothing to be contrasted "
                "with."
            )
        if lost:
            add(
                "  Under degradation the premium LOST "
                + ", ".join(lost)
                + ", which is the opposite of the direction the design predicts."
            )
        if gained:
            add("  Under degradation the premium GAINED " + ", ".join(gained) + ".")
        add(
            "  This is reported as the result it is. The scenario, the seed, the "
            "thresholds and the two completeness levels were not adjusted afterwards."
        )
    add(_THIN)
    for line in _causes(cells):
        add(line)
    add(_THIN)
    add(
        "  A cut severs this chain IN THE MODEL, under this rule table, this control "
        "catalog and the telemetry actually ingested, against a non-adaptive attacker."
    )
    add(
        "  P_max is a superset of realizable worlds, so any tree drawn from it may combine "
        "silent instances that no single consistent world realizes."
    )
    add(
        "  The checker establishes INTERNAL CONSISTENCY with the hashed inputs only. It "
        "shares an author, a language and a reading of the specification with the emitter, "
        "so no certificate here is independently verified."
    )
    return "\n".join(out)


def _causes(cells: tuple[Rendered, ...]) -> tuple[str, ...]:
    """Why the two cells came out as they did, read off the artifacts rather than asserted.

    Every line below is a consequence of a committed configuration value or of a count
    taken from a written artifact. None is an interpretation added after the fact, and no
    value it names was changed once the result was known.
    """
    lines: list[str] = ["  WHY, read off the artifacts:"]
    number = 0

    # Findings are numbered as they are emitted, so one that does not apply to this run
    # leaves no gap. The numbers were once fixed text, and dropping a finding left "1, 3".
    def item(first: str, *rest: str) -> None:
        nonlocal number
        number += 1
        lines.append(f"    {number}. {first}")
        lines.extend(f"       {line}" for line in rest)

    # LIVE is reported as COVERAGE - the share of source-time proved observed - and not as
    # a count of LIVE intervals. Intervals are RLE-merged runs, so a fully live source is
    # ONE interval and a fragmented one is many: deletion raises the count while lowering
    # the coverage. An earlier version printed the count, which showed 6 at full telemetry
    # and 144 at 70% and read as degradation making the timeline MORE observed.
    def _coverage(rendered: Rendered) -> tuple[int, int]:
        live = total = 0
        for source in rendered.cell.liveness.document.sources:
            for interval in source.intervals:
                span = interval.t1_ns - interval.t0_ns
                total += span
                if str(interval.verdict) == "LIVE":
                    live += span
        return live, total

    coverage = {rendered.label.split()[0]: _coverage(rendered) for rendered in cells}
    live_counts = {label: live for label, (live, _total) in coverage.items()}
    if all(count == 0 for count in live_counts.values()):
        m_min = cells[0].cell.liveness.document.m_min
        item(
            f"NO SOURCE IS LIVE IN ANY CELL. With m_min = {m_min} and a "
            "breakpoint at every record instant, an elementary interval",
            "brackets exactly two records, so R9 (n_records_in_span < m_min -> "
            "BLIND, B_WINDOW_UNDERSAMPLED) fires on every interval and",
            "R11, the only construction site of LIVE, is unreachable. "
            "config/vs/liveness.toml states this contradiction in its own",
            "comment and ships the value anyway. Blindness is therefore TOTAL AT "
            "EVERY COMPLETENESS LEVEL, and the full-telemetry cell",
            "cannot be a control arm for blindness.",
        )
    else:
        def _permille(live: int, total: int) -> str:
            # Integer arithmetic only: tenths of a percent, rounded down.
            if total == 0:
                return "n/a"
            tenths = live * 1000 // total
            return f"{tenths // 10}.{tenths % 10}%"

        # In cell order, so the control arm reads first. A label such as "c=100%" already
        # carries an "=", so the share follows a colon rather than a second "=".
        item(
            "LIVE share of source-time per cell (every declared source, including "
            "any that never emits): "
            + ", ".join(
                f"{label}: {_permille(live, total)}"
                for label, (live, total) in coverage.items()
            )
        )

    if all(not r.cell.prove.bracket.lower.psi.corridors for r in cells):
        # This branch checks a SYMPTOM. It must not assert a cause it did not check: an
        # earlier version named one specific cause here as fixed text, which stayed on
        # screen after that cause had been repaired and became a false statement about the
        # scenario. Name only what was measured, and point at where the cause is found.
        item(
            "Psi_min IS EMPTY IN EVERY CELL, so OCC(Psi_min) is empty and B "
            "degenerates to NEC(Psi_max). The premium then cannot",
            "distinguish a control needed because of blindness from a control "
            "needed at all.",
            "CAUSE NOT ESTABLISHED BY THIS REPORT. Inspect p_min.json for which "
            "goal facts P_min derives, and psi_min.json for the corridors.",
        )

    # Every cell is checked, and named: with a blackout cell beside the random one, "the
    # degraded cell" no longer identifies anything.
    for rendered in cells:
        if rendered.cell.prove.goal_resolved:
            continue
        item(
            f"At {rendered.label.split()[0]} the goal library is EMPTY: neither program "
            "derives a goal fact, so the premium there says nothing",
            "about what a sensor could see. CAUSE NOT ESTABLISHED BY THIS REPORT. "
            "Compare truth.jsonl against the degradation manifest",
            "to see which attack records the degradation removed.",
        )

    for rendered in cells:
        for entry in rendered.cell.prove.premium_entries:
            share = entry.calibration_deficiency
            if share > 0:
                item(
                    f"{entry.control_id} at {rendered.label.split()[0]} rests "
                    f"{share.numerator}/{share.denominator} on calibration-deficiency "
                    "licences, so the supported",
                    "sentence is 'needed because this run was not calibrated for "
                    "this source', NOT 'needed because a sensor could not see'.",
                )
    return tuple(lines)


def _preamble(layout: pipeline_mod.Layout) -> str:
    config = liveness_mod.load_liveness_config(str(layout.liveness_toml))
    return "\n".join(
        (
            _RULE,
            "SPECTRA vertical slice -- two completeness cells and one pre-registered "
            "blackout cell",
            _RULE,
            "PYTHON REFERENCE IMPLEMENTATION. No Rust kernel, no Go checker, no C guard VM",
            "and no Docker range exists or was built. Telemetry is the output of a seeded",
            "synthetic generator (bundle_provenance: synthetic_generator_no_range) and the",
            "attack in it is SIMULATED: nothing below happened. No figure here is measured.",
            "",
            f"liveness config   quantile {config.quantile}, slack "
            f"{config.slack_num}/{config.slack_den}, n_min {config.n_min}, "
            f"m_min {config.m_min}",
            "",
        )
    )


def main(
    *,
    repo_root: Path,
    seed: int = pipeline_mod.DEFAULT_ANALYSIS_SEED,
    degradation_seed: int = pipeline_mod.DEFAULT_DEGRADATION_SEED,
    calibration_seed: int = pipeline_mod.DEFAULT_CALIBRATION_SEED,
    verify: bool = True,
    stream=None,
) -> int:
    """Run the two completeness cells (NESTED deletion sets) and the pre-registered
    blackout cell, then print the comparison and the pre-registration's verdict."""
    out = stream if stream is not None else sys.stdout
    layout = pipeline_mod.Layout(repo_root=repo_root)

    print(_preamble(layout), file=out, flush=True)

    from spectra_vs import scenario as scenario_mod

    spec = scenario_mod.load_scenario(layout.scenario_toml)
    config = liveness_mod.load_liveness_config(str(layout.liveness_toml))
    calibration = pipeline_mod.s6_calibrate(layout, spec, config, calibration_seed)
    print(
        "S6 calibration profile "
        f"{calibration.profile.profile_id}\n"
        "  produced by a SEPARATE clean run at completeness 1.0 under a seed from the\n"
        "  calibration band, which is disjoint from the analysis band. It is a model of a\n"
        "  seeded generator's emission behaviour and measures nothing about real telemetry.\n",
        file=out,
        flush=True,
    )

    rendered: list[Rendered] = []
    parent = None
    for label, completeness in CELLS:
        cell = pipeline_mod.run_cell(
            layout,
            completeness=completeness,
            seed=seed,
            degradation_seed=degradation_seed,
            calibration=calibration,
            calibration_seed=calibration_seed,
            parent=parent,
            verify=verify,
        )
        parent = cell.degrade.result
        entry = Rendered(label=label, cell=cell)
        rendered.append(entry)
        print(render_cell(entry), file=out, flush=True)
        print("", file=out, flush=True)

    # The pre-registered controlled cell. It is not part of the nested completeness chain:
    # it varies one sensor over one window at completeness 1/1, so it takes no parent.
    blackout = prereg_0001_blackout(int(spec.epoch_ns))
    blackout_cell = pipeline_mod.run_cell(
        layout,
        completeness=degrade_mod.Completeness.of(1, 1),
        seed=seed,
        degradation_seed=degradation_seed,
        calibration=calibration,
        calibration_seed=calibration_seed,
        verify=verify,
        blackout=blackout,
    )
    lo, hi = PREREG_0001_WINDOW_S
    blackout_entry = Rendered(
        label=f"blackout {PREREG_0001_SOURCE} [+{lo} s, +{hi} s)  (PRE-REGISTERED 0001)",
        cell=blackout_cell,
    )
    print(render_cell(blackout_entry), file=out, flush=True)
    print("", file=out, flush=True)

    # The headline compares the control arm with the controlled intervention. The random
    # completeness cell stays in the output as a degradation-matrix cell.
    rendered.insert(1, blackout_entry)
    print(render_difference(tuple(rendered)), file=out, flush=True)
    print("", file=out, flush=True)
    applies = prereg_0001_applies(seed=seed, calibration_seed=calibration_seed)
    if applies:
        print(render_prereg_0001(blackout_entry), file=out, flush=True)
    else:
        print(
            f"{_RULE}\nPRE-REGISTRATION 0001 NOT EVALUATED: it was registered for analysis seed "
            f"{PREREG_0001_ANALYSIS_SEED} and calibration seed {PREREG_0001_CALIBRATION_SEED}, "
            "and this run used others.\nA prediction is not transferred to a run it was not "
            f"made for.\n{_RULE}",
            file=out,
            flush=True,
        )
    if any(r.cell.verify_exit not in (None, 0) for r in rendered):
        return EXIT_CHECKER_REJECTED
    if applies and not prereg_0001_held(blackout_entry):
        return EXIT_PREDICTION_FAILED
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main(repo_root=Path(__file__).resolve().parents[4]))
