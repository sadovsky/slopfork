# License quick reference (not legal advice)

| Source license | transpile allowed? | Target license constraints | Notes |
|---|---|---|---|
| MIT / ISC / BSD-2/3 / 0BSD / Unlicense | yes | any; keep the copyright and permission notice | Simplest case |
| Apache-2.0 | yes | any compatible; keep LICENSE and NOTICE, state changes | Patent grant; GPLv2-only targets are incompatible |
| MPL-2.0 | yes | ported files stay MPL-2.0 (file-level copyleft) | Can be combined with other code in a larger work |
| LGPL-2.1/3.0 | yes | ported library stays LGPL | Linking rules differ by language; flag for review |
| GPL-2.0/3.0 | yes | target must be GPL (compatible version) | Note "GPL-2.0-only" vs "or later" |
| AGPL-3.0 | yes | target must be AGPL-3.0 | Network-use clause carries over |
| SSPL / BSL / Elastic / "source available" | usually **no** | read the terms | Often forbid competing offerings; tell the user |
| No license | **no** | n/a | All rights reserved. Ask the author, or use cleanroom/blackbox with the risk stated |
| Proprietary / EULA | **no** | n/a | EULAs may also forbid reverse engineering, which affects blackbox too |

Cleanroom and blackbox: the output is meant to be an independent work, so the source license doesn't bind it in the same way. But patents, trademarks (project name, logos), and EULA terms still apply. Don't reuse the project's name for the port without checking trademark use; a neutral name like `<name>-ts` with "port of" wording is common.

Also surface non-license signals to the user, such as a maintainer's stated policy on forks or AI-generated derivatives. These may not be legally binding, but the user should get to decide knowing them.
