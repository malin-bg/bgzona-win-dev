# Local DEV media integration

No deployment. Media mode is disabled in hugo.toml by default, retaining the existing collage gallery/slideshow when no validated artifact is mounted.

The deterministic tools/media/build.py entry reads a trusted frozen A2 release artifact directory and its exact path-to-SHA256 expected-files JSON. It validates bytes/schema/identity/state via the A3 bridge, writes only a NEW external output directory, then runs Hugo using a temporary mount/config. Do not supply incoming/replace/library/registry as the artifact. The expected-files authority must come from an accepted release receipt, not a manually edited list. This is validation, not a GitHub approval service.

Example: python tools/media/build.py --artifact <frozen-release> --expected-files <trusted-files.json> --output-root <new-external-directory>. Hugo must be on PATH or supplied with --hugo. No Work-specific paths, runtime APIs or persistent external mounts are stored in source. No originals/catalog JSON are committed into public/static/assets source folders.

Python 3.12.14 / Pillow 12.3.0 / Hugo extended 0.155.2 were tested. Pillow codecs JPEG/PNG/WebP/GIF are required. requirements.txt pins the tested package version but is not yet a platform wheel hash lock. Clean hosted runner and GitHub Pages deployment remain NOT VERIFIED. The image-build path uses no importer ID allocator, msvcrt lock or Git transport; those remain separate future assets automation. Node is not required for this build.

All outputs/resources/cache are external and --noBuildLock protects the checkout. Ordinary hugo without the helper retains legacy mode. Explicit media.enabled=true with missing catalog fails the build. Never publish this working tree using the old ungated workflow: exact artifact/DEV approval/Pages preflight remains a separate release gate. This helper never commits or deploys.
