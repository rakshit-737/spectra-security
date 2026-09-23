# research/

Machine-readable outcomes of the pre-registrations in `docs/research/`.

`results/<registration>.json` is written by the demonstration and is COMMITTED, which
`runs/` is not. The reason is `CLAIMS.md`: a sentence that states a number may appear on a
surface only if it carries a `CLM-####` anchor whose record points at an artifact, and an
artifact nobody can open is not support. These files are what the records point at.

Each file holds the registered falsifiers, whether each passed, and the few figures the
cells produced. It holds no path, no clock, no host and no seed of the machine that ran it,
so two machines that agree produce the same bytes. `runs/<id>/` keeps the full artifacts of
a run and is deliberately not committed: it is large, it is reproducible from the
repository, and a directory name is a path.

WHAT A FILE HERE IS NOT. It is not a measurement. The telemetry is the output of a seeded
synthetic generator and the attack in it is simulated, so every figure is a property of the
model and its inputs. It is not a held-out result either: the scenario was authored and
edited by the same author who wrote the predictions, which is why the registry records
these claims as TUNED and keeps them off the README's headline.
