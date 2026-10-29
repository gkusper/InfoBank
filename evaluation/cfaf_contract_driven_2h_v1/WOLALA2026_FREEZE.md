# Historical wolala2026 freeze

Verified local and remote branch `wolala2026`: `5f377de38312fb39c088551f9c74f8b6d4bd5080`. Remote SHA was read through the connected GitHub compare API for wolala2026 against itself; status identical, zero ahead/behind. Historical tree: `f37ba4ff901952d471ee927ca7a637d82121f261`.

Annotated local tag: `cfaf-wolala2026-freeze-2026-10-29`; tag object `96c7a12f679075c3e47e2d198ad0cd46330805c4`. This tag points at the exact historical commit. The branch was not changed, deleted, rebased or merged. A local tag provides a reproducible reference; it does not enforce GitHub branch protection or immutable remote refs.

New branch `experiment/cfaf-contract-driven-v1` starts from the latest local sparse-source HEAD `69e3e1eaff9143ab350b5366a7e64645ea455d06`, not from wolala2026. Existing RDA/RECV/target/claim/sparse work is retained. All earlier reports/source/annotations are protected by the starting SHA inventory in task_state.json.

Historical artifacts: evaluation/wolala2026/ contains original pipeline, selector, development and legacy heldout protocols/results. Historical40 synthetic-mode results and later exposed mixed development-mode results are different phases, not pooled factual-answer accuracy. The current full compatibility tests and known authorization-file-presence failure are in regression_audit.json and test XML/logs. The historical selector/eight stages remain unchanged. Original independent-student holdout is not opened; the legacy HELD3 cohort is already exposed and is explicitly development-only here.

Known limitations: no independent claim-entailment proof, public-benchmark familiarity, model-semantic scope/relations can be wrong, original per-source annotations do not provide Dataset3 binary gold. Sparse validation fixes an inventory contract, not semantic accuracy. The measured new study retains those limitations.

No remote action was performed. User performs any later push manually:

```powershell
git push origin refs/tags/cfaf-wolala2026-freeze-2026-10-29
git push -u origin experiment/cfaf-contract-driven-v1
```

Before publication, a repository administrator should configure protection/rulesets for wolala2026 and the freeze tag: restrict updates/deletion, block force pushes, require review and the repository's actually configured checks for allowed future development changes. This study does not invent CI check names or assert that protection is active. Keep the frozen historical branch immutable; develop on the separate branch. See https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches .

## Exact later protection actions (administrator, manual)

After publication, open the repository Settings > Branches, create a rule for exact branch wolala2026, enable Lock branch and Do not allow bypassing the above settings, and leave Allow force pushes / Allow deletions disabled. This is a read-only historical reference; future work stays on the separate experiment branch. For mutable development branches, configure review and the actually existing CI checks rather than inventing check names.

For tag cfaf-wolala2026-freeze-2026-10-29, use Settings > Rules > Rulesets, create an Active tag ruleset targeting that exact tag, restrict updates and deletions, and review the bypass list so it does not defeat the freeze. Ruleset availability depends on repository visibility/account plan and administrator permission; this task made no remote protection change. See [GitHub branch protection](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) and [branch/tag rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets).
