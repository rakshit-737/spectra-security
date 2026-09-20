# `docker/` — images and compose files

Status: **not started**. This directory contains this README and nothing else. No Dockerfile and no
compose file exists.

Owning sections: Part I §32.2 (the inventory), Part I §33.7 (the builder image), Part I §33.8 (the
devcontainer), Part I §33.6 (toolchain pins), Part I §52 (milestones).

## 1. Inventory

Every row is **not started**.

| Path | What it is | Milestone | Status |
|---|---|---|---|
| `builder.Dockerfile` | The one image containing every toolchain. Multi-stage: one stage per heavy toolchain, a final stage that copies them in. | M0 | not started |
| `runtime.Dockerfile` | Slim runtime for the api and worker services. | M0 | not started |
| `web.Dockerfile` | Node build, then static serve. | M0 | not started |
| `compose.core.yml` | postgres, redis, api, worker, web. | M0 | not started |
| `lab/` | Per-lab-node images: gateway, idp, appsrv, dbsrv, opsbox. | M3 | not started |
| `compose.lab.yml` | Isolated lab network, no egress. | M3 | not started |
| `compose.bench.yml` | Benchmark harness, pinned CPU and memory. | M7 | not started |

TODO(decision: milestone assignment for the lab and bench images): Part I §52 does not assign these
files to milestones by name. The assignments above follow the milestone deliverables: M0 requires
`docker compose up -d` to reach healthy for all core services (§52.3), M3 is the vertical slice that
first needs the modeled hosts, and M7 is the first milestone that produces a benchmark number.
To change one, edit this table and the corresponding milestone acceptance list together.

## 2. The builder image

`builder.Dockerfile` is the single source of the build environment. Part I §33.7:

- Multi-stage, one stage per heavy toolchain plus a final stage that copies them in, so that a
  change to one toolchain does not invalidate the rest.
- Contains **every** tool pinned in Part I §33.6, at the pinned version. `.tool-versions` and
  `.devcontainer/devcontainer.json` mirror those pins.
- Declares `ENV SPECTRA_IN_CONTAINER=1`. Nothing else sets that variable, so it is a reliable test
  for re-entrancy: `make` targets re-execute themselves inside this image unless it is set.
- Runs as a non-root `builder` user with a writable `/work`.
- Ends with `RUN spectra-doctor --strict`.
- **Publishes nothing.** The image is built locally and cached by CI keyed on the Dockerfile hash.
  There is no registry to pull it from and there must not be one.

The definition of "the builder image is complete" is machine-checkable and is not a judgement call:
`make doctor` inside it prints zero mismatches, and `make polyglot` inside it prints zero SKIPPED
components. Neither target exists.

`.devcontainer/devcontainer.json` builds from this same file. There is exactly one build
environment; do not create a second one for the devcontainer, for CI, or for a contributor's
convenience.

## 3. Rules every file here inherits

- **No floating versions. No `latest`, anywhere, in any Dockerfile.** Part I §33.6. Base images are
  pinned by digest, not by tag. A tag can be moved; a digest cannot.
- **Offline.** SPECTRA has no API keys, no cloud credentials and no paid services. The test job runs
  with `--network=none` and passes (Part I §52.3). A Dockerfile that needs the network at *run* time
  is wrong; one that needs it at *build* time must fetch only pinned artifacts.
- **Non-root.** The builder image runs as `builder`. Runtime images follow.
- **`compose.lab.yml` has no egress.** The lab network is isolated. That is a containment property
  of a security-research platform, not a preference.
- **Reproducible.** Part I §33.5 requires the build itself to be deterministic. Image builds are
  part of the build.
- **Health, not hope.** Part I §52.3's M0 acceptance is that `docker compose up -d` reaches healthy
  for all services in under 90 seconds. That requires real healthchecks, not a sleep.

## 4. What is not here

- `.devcontainer/devcontainer.json` lives at `.devcontainer/`, not here, and references
  `../docker/builder.Dockerfile`.
- `.dockerignore` lives at the repository root.
- Toolchain pins live in `.tool-versions` at the repository root and are mirrored into
  `builder.Dockerfile` and `.devcontainer/devcontainer.json`. The root file is the source; the
  mirrors are checked, not authored independently.

## 5. Negative requirements

- Do not use `latest` or any moving tag in any Dockerfile.
- Do not publish the builder image, and do not add a registry pull as a shortcut.
- Do not add a second build environment, for any reason.
- Do not add a toolchain to the devcontainer that the builder image already provides.
- Do not give the lab network egress.
- Do not run a service as root.
- Do not add a compose service that the Makefile does not drive. The Makefile is the only entry
  point, and Part I §33.9 forbids documenting a second way to do the same thing.
