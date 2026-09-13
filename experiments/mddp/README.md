# MDDP WH experimental compatibility work

**Compiled and checked offline only. Not loaded, flashed, or hardware-accepted.**
`legacy_wh_handshake` is a read-only-at-runtime module parameter (0400), disabled
by default. These patches are deliberately excluded from `patches/series.json`.

The current modem reports capability `0x3`, without WH bit `0x4`. Correcting
`/dev/mddp` permissions lets the HAL open the device, but does not supply this
capability. This candidate tests a legacy handshake path; it does not simply
force a capability bit on every modem.

## Source and build inputs

| Input | Pinned source |
|---|---|
| MediaTek device-module source | [MotorolaMobilityLLC/kernel-kernel_device_modules-6.6](https://github.com/MotorolaMobilityLLC/kernel-kernel_device_modules-6.6/tree/9b049a46b9fc6b08372fb1bb782d0f49dc7c9ef1), commit `9b049a46b9fc6b08372fb1bb782d0f49dc7c9ef1` |
| GKI common source | [Android common](https://android.googlesource.com/kernel/common/+/be8d201b0d27dd3258f8e1a816c2c364af6dcb32), commit `be8d201b0d27dd3258f8e1a816c2c364af6dcb32` |
| Compiler | Android Clang r510928, build 11368308; prebuilt repository commit `921f6da692b1ffc96a0daa7e741373f0089d40b0` |
| Configuration | `final-build.config`; relevant differences from the device configuration in `config-differences.diff` |
| Symbol versions | `verified-imports.symvers`, derived and cross-checked against original matching provider modules |

Apply in order inside the Motorola source checkout:

```sh
git apply /path/to/lineageos-gold/experiments/mddp/0001-honor-modem-failure.patch
git apply /path/to/lineageos-gold/experiments/mddp/0002-opt-in-legacy-handshake-DRAFT.patch
```

Patch 1 respects modem failure/timeouts and serializes response/state handling.
Patch 2 optionally attempts the restricted legacy WH handshake, sets the WH
capability only after a valid successful response, clears it on reset, and uses
only the first five shared-memory regions. Other modes are rejected.

**Rebuild limitation:** this is not a standalone `make` recipe. The validated
build also used generated kernel headers/configuration and matching provider
objects in a prepared output tree. Those generated objects and proprietary
provider binaries are not published here. The source patches, configuration,
ABI data and test fixture preserve the work; a clean-source reconstruction of
all provider inputs remains necessary before claiming full reproducibility.

## Existing offline evidence

- Candidate: 175880 bytes, SHA-256
  `1b25847d38f96134a10ad7b094cdd1c4d4cf4779bf069ed7ee61cacdd21873c4`.
  The binary is not distributed by this repository.
- Baseline reconstruction matched all 133 compared function bodies of the
  original module; candidate preserved 123 and changed the expected 10.
- All 100 imported-symbol CRCs matched; 133 shared KCFI entry prefixes matched;
  the checked app structure was 232 bytes.
- MODVERSIONS and CFI were retained. MODPOST was not silenced. BTF generation
  was skipped because a complete matching vmlinux was unavailable.
- Original vermagic contained the vendor SCM suffix; rebuilt vermagic was
  `6.6.89-4k`. It was not forged to claim the vendor source revision. Offline
  compatibility reasoning is not proof the kernel will load the module.
- 45 extracted host-test cases passed. The fixture uses mocked dispatchers and
  simplified host synchronization; it is not a kernel concurrency test.

To run that fixture on the host:

```sh
cc -std=c11 -Wall -Wextra -Werror extracted-host-test.c -o /tmp/gold-mddp-host-test
/tmp/gold-mddp-host-test
```

Real modem handshake, actual offloaded traffic/counters, reset/reconnect,
concurrency, long-running stability and thermal behavior remain unverified.
