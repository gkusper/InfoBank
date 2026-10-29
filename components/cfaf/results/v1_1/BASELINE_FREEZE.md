# Completed v1 freeze

Completed v1 HEAD: `ca2e3e111c63fbd67ff8965e5b05f3530a85c8a0`. Its earlier base bfd80bb is not its completion. The worktree was clean before this task. Annotated local tag: `component-cfaf-v1-freeze-20261029T170700Z`; tag object `2736c8247411d43fa3959661fdd8391cf2d9d6dc`. It dereferences to the completed v1 commit. All 66 public v1 files and nine original private result files are hashed and preserved; a separate exact source snapshot runs the fresh C1 arm.

The original 54 tests pass against that immutable snapshot. All third-party versions remain unchanged; only the editable component package release changes to 0.1.1. A/C1 use the original frozen 2048-token prompt/schema configuration in fresh processes; C2 loads current v1.1 code at 1536 tokens. No cached C1 output substitutes for a fresh paired result. A/B use the original ordinary configuration and guard.

All other worktrees, branches, tags and manuscript remain protected. Only ComponentBasaedCFAF receives new commits. No push/merge is performed. Original v1 manifests, reports, tests and raw outputs are retained, not rewritten; reproduction uses the freeze tag rather than the modified current source tree.
