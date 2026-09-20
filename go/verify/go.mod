// spectra verify - the independent checker.
// Spec: Part I 32.5; Part II 69 (ABI), 75.2 C6.
// Status: not started.
//
// Module path fixed by docs/adr/0003; docs/adr/0011 corrected which artifact
// that audit named as stale. The owner segment is not a placeholder. Changing
// it changes spectra.toml [project].repository and [names].go_module, every Go
// import path and CITATION.cff together.
// TODO(dependencies): Part II 69.20 (make no-service-deps) requires this
// module's non-stdlib dependency set to be empty apart from a pinned BLAKE3
// implementation, and forbids any database, HTTP, DNS, queue or telemetry
// client. Vendoring is go mod vendor with GOFLAGS=-mod=vendor and GOPROXY=off
// (Part II 74.2).

module github.com/rakshit-737/spectra-security/go/verify

go 1.23.2
