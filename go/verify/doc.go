// Package verify is the module root of the independent SPECTRA checker.
//
// Owning spec sections: Part I 32.5 (this module shares no code, no generated
// artifact and no dependency with the Rust workspace); Part II 69 (the
// subprocess and content-addressed-file boundary, the exit-code taxonomy) and
// 75.2 C6.
//
// The command at cmd/spectra-verify does not exist yet, and neither do the
// re-grounding, liveness and check packages named in Part I 32.5.
//
// Status: not started. This file declares the package and nothing else.
package verify
