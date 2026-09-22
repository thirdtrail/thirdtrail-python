# Workflows

`ci.yml` — tests on every supported Python, plus lint and type-check once.

`release.yml` — publishes to PyPI when a `v*` tag is pushed.

## Releasing

```bash
# bump the version in pyproject.toml and src/thirdtrail/__init__.py
git commit -am "release: v0.1.1"
git tag v0.1.1
git push origin main --tags
```

There is no PyPI token to manage. Publishing uses Trusted Publishing: GitHub
mints a short-lived OIDC credential scoped to this workflow in this repo, and
PyPI is configured to trust that exact combination. Nothing long-lived exists
to leak or rotate.

The version lives in two files and they must agree; `tests/test_packaging.py`
enforces that, because a tag that disagrees with the metadata publishes a
release nobody can `pip install` by the version they expect.
