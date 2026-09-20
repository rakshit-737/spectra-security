# Development environment

Status: **not started.** Nothing in SPECTRA is implemented. This directory holds the documents a
contributor needs before the first build, and they are written as they become true, not in advance.

| Document | Covers | State |
| --- | --- | --- |
| [wsl.md](wsl.md) | Why every target runs inside WSL2 or the devcontainer, and how to get there | written |
| `toolchains.md` | What each pinned toolchain is for and how the builder image supplies it | not written |
| `offline.md` | Vendoring per ecosystem, and how a clean clone builds with the network off | not written |

The authoritative source for all of this is the specification, Part II section 74. These documents
exist so a contributor does not have to read a 26,000-line specification to run `make doctor`; where
they disagree with the specification, the specification wins and the document is the defect.
