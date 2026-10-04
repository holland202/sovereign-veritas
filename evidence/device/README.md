# Device package (unsigned)

`sv_package_de9fee31b190.json` is the package made on the S25 on 2026-09-25 and used for the README's damaged-copies row.
It was kept on the device until 2026-10-04, when an outside reproduction pointed out that nobody else could rerun that result.

- **Unsigned.** It has no `.sig` and is not in `witness/packages.log`. It shows the verifier rejecting damaged bytes; it says
  nothing about who made it.
- md5 `de9fee31b190cfa5accaf24bd03ab6d8`, 17,157 bytes, sha256 in the package's own `package_sha256` field.
- It lives in this subfolder so tools that read `evidence/*.json` (the signed set) are unaffected.

Rerun 2026-10-04, same output on the S25 (main's verifier, Python 3.14.6) and in a Linux container:

```
$ python tools/verify_package.py evidence/device/sv_package_de9fee31b190.json
VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=NOT_PROVEN

$ python tools/package_recovery_sim.py evidence/device/sv_package_de9fee31b190.json
package 17157 bytes, seed 7
TRUNCATION  0 of 17157 strict prefixes accepted
CORRUPTION  0 of 200 single-bit flips accepted []
VERDICT     nothing damaged was accepted
```
