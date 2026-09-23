// A manifest of the test files, and the reason it exists.
//
// `node --test frontend/tests` is the command the milestone asks for. On Node 24.14.0 a
// bare directory positional is not expanded by the test runner: it is resolved as a
// module specifier, which for a directory means this file. Without it the command fails
// with `Cannot find module 'frontend/tests'` before a single test runs.
//
// So this file is that module, and it imports every test file. Importing a file that
// calls `test()` at module scope registers its tests, so the whole suite runs in one
// process and the reported counts are the whole suite's.
//
// It is NOT named `*.test.js`, which matters: `node --test "frontend/tests/*.test.js"`
// and `node --test` from `frontend/` both expand to the six test files and do not match
// this one, so no test is registered twice.

import "./catalog.test.js";
import "./cert.test.js";
import "./honesty.test.js";
import "./render.test.js";
import "./serve.test.js";
import "./witness.test.js";
