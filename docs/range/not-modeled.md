# What the container range does not model

Source: build specification Part II, sections 75.4, 75.9 and 71.4. This file is the only place in
the repository where the realism adjective may appear. Everywhere else it is a banned phrase, and
the replacement is a link to this page.

Status of the range: not started. No container has been built, no bundle has been produced, and the
realism corroboration has not been performed.

Status of the range in the project: **non-normative.** This overrides Part I, which made the range
the only source of SPECTRA telemetry. The seeded synthetic generator is the normative telemetry
source. The range is a realism corroboration whose bundles no published number depends on, because
byte-identical replay is impossible with live services and the reproducibility claim outranks the
realism claim. The range sits on the first rung of the descope ladder; if time runs short it is
deleted entirely, and this file then records that the corroboration was never performed.

## What the range is

A handful of egress-blocked containers on one laptop, on internal Docker networks, with images
pinned by digest, no outbound network path, no Docker socket, no real credentials, no real domains
and no external name resolution. It is a laboratory model of an identity and application estate. It
is not a model of an organisation.

## What it does not contain

This list is the honest counterweight to anything the range appears to demonstrate. It is appended
to, never trimmed.

- **No people.** No users, no operators, no administrators, no working hours, no habits, no mistakes,
  no shadow processes, no one ignoring an alert.
- **No business.** No business processes, no approval chains, no seasonal load, no quarter-end, no
  mergers, no contractors, no onboarding or offboarding churn.
- **No scale.** The container count is small by construction and the event volume is whatever the
  scenario emits. Nothing here says anything about behaviour at estate scale.
- **No Windows estate.** No domain controller, no directory service, no Kerberos, no group policy,
  no Windows event log semantics.
- **No endpoint agents.** No endpoint detection platform, no antivirus, no host firewall product, no
  kernel-level sensor and none of the telemetry any of those would produce.
- **No cloud control plane.** No cloud provider audit log, no managed identity service, no
  serverless platform, no object store access log.
- **No third-party software-as-a-service.** No external identity provider, no external mail platform,
  no collaboration suite, no partner tenancy.
- **No mail.** No mail flow, no phishing, no attachment handling, no mail gateway.
- **No network estate.** No routers, no switches, no firewalls, no proxies, no load balancers, no
  virtual private network concentrators, no wide-area links, no packet loss, no asymmetric routing.
- **No physical layer.** No hardware, no physical access, no removable media, no out-of-band
  management.
- **No operational entropy.** No configuration drift, no patch cycles, no failed deployments, no
  half-migrated services, no legacy system nobody understands, no undocumented integration.
- **No logging-pipeline reality.** No log forwarder outages, no retention policies, no index
  rollover, no sampling, no vendor field mangling, no multi-line parse failures at estate scale. The
  degradation operators model loss deliberately; they do not model a real pipeline failing.
- **No clock reality.** No estate-wide clock skew, no time-source failures, no time-zone diversity
  beyond the fixed configuration, no daylight-saving transitions.
- **No adaptive adversary.** The modelled attacker is non-adaptive: it does not observe the controls,
  does not re-plan when one is enabled, does not abort, does not pivot to an unmodelled technique and
  does not take longer on purpose. This is the single most important item on this list.
- **No unmodelled techniques.** By construction the range exercises only what the rule table can
  express. It cannot surprise the rule table, so it cannot test whether the rule table is complete.
- **No malware.** No sample is downloaded, stored, detonated or referenced for retrieval. Generators
  emit telemetry records; nothing here acts on a host.
- **No exploitation.** There is no exploitation code path in this repository and none is planned. The
  attack profile writes log lines describing what an attack would have looked like.
- **No baseline history.** No long-running normal-activity baseline, no established seasonality, and
  therefore no basis for any claim about behaviour under a mature baseline.
- **No diversity of implementation at estate scale.** The service languages present are chosen to
  exercise reconstruction across heterogeneous producers; they are not a sample of anything.

## How to talk about the range

Describe what it contains and link this page. Do not use the realism adjective outside this file, do
not call the range enterprise-grade, production-like or a real-world environment, and do not state
or imply that a result obtained here transfers to an estate.

No number produced by the range appears in a gate, in a results table, in the README or in the paper.
If you find one, that is a defect in the run provenance, not a new result.

## If the range is cut

Rung D1 of the descope ladder demotes the range to a non-normative realism check before any kernel
thinning begins, and deletes it outright if time is short. If that happens, this file is the record:
it states that the realism corroboration was not performed, and nothing elsewhere in the repository
may imply that it was.
