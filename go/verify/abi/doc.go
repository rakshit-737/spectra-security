// Package abi holds the checker's hand-written ABI wire types.
//
// Owning spec sections: Part II 69.5.3 (Rust and Go each carry a hand-written
// definition; neither is generated from the other) and 69.20 (make abi-contract
// proves the Rust structs, these structs and abi/v1/*.schema.json describe the
// same field set with the same types and the same required-ness).
//
// Nothing here may be generated, and this package must import nothing outside
// the standard library.
//
// Status: not started. This file declares the package and nothing else.
package abi
