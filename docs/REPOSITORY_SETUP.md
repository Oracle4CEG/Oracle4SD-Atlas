# Repository setup and review boundary

Upstream: https://github.com/Oracle4CEG/Oracle4SD-Atlas. Personal fork: https://github.com/virusLuke3/Oracle4SD-Atlas. Starting template commit: 2ca64c50c43e189aa9cfc2cacd03520b71119301.

Current repairs are on `fix/usable-atlas-release-20261012` in the personal fork and proposed through organization PR #1 via `review/scientific-data-reproducibility-20260916`. The organization default branch is not merged automatically. Use the explicit branch clone command in the README and record the checked-out commit.

The original oracle-nature workspace is not modified by this repository pipeline. Production code is copied with original/imported checksums. The notebook's code commit and the documentation/report commit can differ: the notebook pins a preceding immutable code commit to avoid circular self-reference; execution reports record it explicitly.
