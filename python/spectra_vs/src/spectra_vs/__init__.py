"""SPECTRA-VS: the vertical slice stages. A PYTHON REFERENCE IMPLEMENTATION.

Per ADR-0013 the specification's Rust kernel and Go checker do not exist on this machine
and are not produced by this package. Nothing here may state or imply otherwise.

This package holds the stages of the slice pipeline. The three in this commit:

  `rules`     S1, the declarative rule table and the guard front end: blocker masks over
              threshold literals, with the bit assignment recorded beside every mask
  `ground`    S8, semi-naive fixpoint with provenance over the OBSERVED facts, producing
              the bipartite AND/OR hypergraph of P_min
  `envelope`  S9, licensed silent instances and obligation-forced GHOSTs, producing P_max

Importing this package imports no stage: a stage is imported by name, so a module that
needs only the rule table does not pull in the fixpoint. The digest throughout is
`spectra_core.canon`'s blake2b-256, labelled `b2b256:` and never `blake3:`.
"""

__all__ = ["__version__"]

#: Fixed text, not derived from a tag: a version read from the environment would differ
#: between two runs that must be byte-identical.
__version__ = "0.1.0"
