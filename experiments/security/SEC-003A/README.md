# SEC-003A: Stack overflow fuzzing

Local Termux ARM64 experiment using LLVM libFuzzer and AddressSanitizer.

The vulnerability was intentionally planted in a standalone C harness. It is not a demonstrated Sovereign Veritas production vulnerability.

Discovery and separate-process replay reported a stack-buffer-overflow at fuzz_stack.c:14:23.

The binary is excluded from Git. Its SHA-256 is recorded in evidence_manifest.json.

Cross-substrate and external independent verification remain incomplete.

Original evidence is preserved in the local experiment directory. See replay_status.json for the replay result.
