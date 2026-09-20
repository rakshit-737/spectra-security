"""Subprocess client for the kernel and checker binaries.

Owning spec sections: Part II 69.1, 69.4, 69.8 and 69.12. This package is the
only place in the Python tree permitted to spawn a process; the one-spawner lint
of Part II 69.20 (make one-spawner-lint) is pointed here rather than at
services/kernel_client.py, the path 69.12.1 spells under a layout Part I 32.3
does not use. TODO(conflict): reconcile the path before the lint is written.

Status: not started. Package root only; no implementation.
"""
