# DEV media delivery — local preparation, not activated

Only `.github/workflows/hugo.yml` publishes DEV. Push to main and manual dispatch use the same gate. No ordinary article/video approval step is added. The workflow is JSON-formatted YAML (YAML 1.2 subset), allowing structural validation without installing another parser.

`delivery.py` obtains the locked media input, checks the exact ZIP SHA/size and member set, validates the existing bridge contracts, builds a current-source legacy baseline and the media-enabled candidate, runs the reused B3A acceptance checks, seals and verifies the candidate. The workflow verifies again immediately before official Pages upload; deploy depends on successful build. No second build follows acceptance. Output and input stay under runner temp, never public source or assets repository.

The input lock is generated release metadata, not a daily user-editable catalog. Snapshot counts (initially 45/27/18/26) belong to that snapshot, not a global website limit. Articles, videos and menus continue through GitHub Desktop Commit → Push → automatic checks/publication using the unchanged media snapshot. Baseline article metadata and article-local images are checked against a baseline from the CURRENT source; no historical article/file allowlist freezes new content. Media input changes require their own verified snapshot/lock in a later authorized task.

## Activation prerequisite — currently absent

`tools/media/input-lock.json` has `provider: null`. Every real workflow invocation therefore FAILS CLOSED before Hugo. Do not push this preparation expecting ordinary publishing to keep working until the provider is activated; there is intentionally no legacy/partial-gallery fallback.

After separate authorization, create a non-draft, non-prerelease versioned Release in `malin-bg/bgzona-win-dev` and upload the EXISTING input-only `bgzona-dev-media-input-bb9fc4fb148eb484.zip` (9,595,193 bytes). Exact SHA-256:

`35054cbed0f49ff6a9e656d46c7952bd3c903e6d2fc37dcbfd51d7987800b049`

Verify the actual downloaded asset bytes and record real `release_id`, `asset_id`, and `tag` under the lock's `provider` object. No real IDs, tag or URL have been assigned by this implementation. The helper constructs the GitHub API/download URLs from those verified values, confirms release/asset identity, then verifies the locked bytes. Missing/deleted/replaced/mismatched inputs stop publishing. No expiring Actions artifact or Work folder is the input provider. The archive must remain outside public source. Public download is the first-release contract; a private provider/auth change would require a separate design/authorization.

## Acceptance and integrity

The acceptance suite checks current media pages/IDs/canonical URLs, exact originals, format/animation, thumbnail fit, OG/Twitter/TXT/sharing, sitemap and exact slideshow membership, all HTML noindex, current articles/404/images, and private-path/bundle leaks. A trusted caller invokes acceptance and then seal directly; no arbitrary PASS receipt is accepted. SHA establishes integrity, not authorship or release authorization. Every new accepted website build receives a new seal.

The stdlib B3B1 seal is reused unchanged. Official Pages actions transfer and deploy this run's named artifact; there are no caller-supplied artifact IDs. Only deploy gets Pages/OIDC write permissions. Main/repository guards prevent dispatch from another branch/repository. Official direct actions are pinned to verified commit revisions; their transitive dependencies remain upstream-managed. Hugo extended 0.155.2 has a pinned Linux archive checksum; Python 3.13.16 and Pillow 12.3.0 are pinned. Dependency wheels are resolved from PyPI in the hosted runner; no claim of a cross-platform wheel hash lock is made.

Owner-verified Settings facts: production/DEV Pages use GitHub Actions; assets use main/root branch publishing. DEV domain is dev.bgzona.win with HTTPS enabled. No settings changes are needed or made. Actual github-pages environment reviewers/branch restrictions, repository rules, Actions permissions/allowlists and retention remain UNKNOWN and must be reviewed before first push. Required human environment approvals for ordinary main publishing would conflict with the approved UX; do not silently change protections.

## Local verification and rollback

`python -B tools/media/delivery.py --work <new-external-path> --hugo <verified-hugo> --local-archive <verified-existing-ZIP>` is a test-only override, forbidden when `GITHUB_ACTIONS=true` and absent from the workflow. It tests real build/accept/seal without claiming the remote provider or hosted runner passed. No deploy command exists in the helper.

Before first release, preserve a verified last-good deployed Pages artifact and an authorized redeployment procedure. Local pre-B3B2 workflow backup/isolated restore and exact diff live in the external B3B2 task folder; existing B1/B3A backups remain untouched. Source rollback, if separately authorized: preserve current files, verify backup SHA, restore only the previous workflow; remove only the six B3B2-added paths after checking the recorded creation manifest. Do not reset/clean or discard the 18 earlier DEV changes. This source rollback is not a live Pages rollback.

No commit, push, Release upload, workflow execution, deployment or settings edit is authorized by this preparation.
