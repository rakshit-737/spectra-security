// spectra verify - the independent checker.
// Spec: Part I 32.5; Part II 69 (ABI), 75.2 C6.
// Status: not started.
//
// TODO(module path owner): github.com/rakshit-737/spectra-security is a placeholder chosen
// for this skeleton. Change it here and in every import path when the
// repository's final owner is fixed.
// TODO(dependencies): Part II 69.20 (make no-service-deps) requires this
// module's non-stdlib dependency set to be empty apart from a pinned BLAKE3
// implementation, and forbids any database, HTTP, DNS, queue or telemetry
// client. Vendoring is go mod vendor with GOFLAGS=-mod=vendor and GOPROXY=off
// (Part II 74.2).

module github.com/rakshit-737/spectra-security/verify

go 1.23.2
