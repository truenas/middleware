# S3 protocol tests

Buckets and access keys are provisioned through the middleware API and
exercised over S3. Most of what a bucket row stores — `object_ownership`,
a `DENY` grant, `manage_buckets` — has no observable effect through the
API alone.

## Running

```sh
cd tests
./runtest.py --ip <IP> --password <PASSWORD> --test_dir sharing_protocols/s3
```

`boto3` is the only extra dependency, already in `tests/requirements.txt`.

## Layout

| | |
|---|---|
| `middlewared/test/integration/assets/s3.py` | provisioning: accounts, keys, buckets, grants, the service. Middleware API only — no client library, so it stays importable without one. |
| `s3_client.py` | the boto3 client and the helpers that read an answer off it. Here rather than in `tests/protocols/`, whose `__init__` imports every client it re-exports and would make an S3 case need samba and pynfs. Imported by bare name, as `nfs/` and `nvmet/` import theirs. |
| `conftest.py` | the session deployment, below. |

## Session fixtures

Two accounts:

| | roles | clients |
|---|---|---|
| `s3protomain` | `SHARING_S3_WRITE` | `s3` (plain key), `admin_s3` (same account, `manage_buckets` key) |
| `s3protoalt` | none | `alt_s3` — no grant anywhere, so any allow it sees came from a stored ACL |

Nine buckets. `buckets["<leaf>"]` is the name, or `None` if it could not
be provisioned; modules skip rather than fall back to the ordinary
bucket.

| leaf | configuration |
|---|---|
| `attached` | `OBJECT_WRITER` — the default bucket (`bucket` fixture) |
| `locked` | `versioning=ENABLED`, `object_lock` |
| `defaulted` | as `locked`, plus a `GOVERNANCE`/1-day rule |
| `history` | `versioning=SUSPENDED`, `snapshot_versions` |
| `attic` | `versioning=OFF`, `snapshot_versions` |
| `minted` | `multipart_etag=MINTED` |
| `preferred` | `BUCKET_OWNER_PREFERRED`, owned by `alt` |
| `denied` | a `DENY` grant naming its own owner |
| `excluded` | dataset destroyed under a live row — serves 503 |

Three constraints on that set:

- `attached` is `OBJECT_WRITER`, not the `BUCKET_OWNER_ENFORCED` default,
  because enforced ownership disables the ACL surface entirely.
- `preferred` is owned by `alt` and written by `main`; a bucket whose
  owner is its writer answers both ways identically.
- `S3_VERSIONING` and `S3_AUDIT` are mocked entitled *before the service
  starts*. The daemon reads them at start-up and downgrades unlicensed
  rows, so a later mock would be too late.

Buckets are session-scoped and shared. Drain any prefix you write, and
abort any multipart upload you open — `ListMultipartUploads` and a flat
listing both answer for the whole bucket.

## Not covered

- **The on-disk format** — object records, the garbage collector, staged
  names. The S3 service's contract, tested where the engine lives.
- **Other client stacks** — rclone, s3cmd, aws CLI, s3fs. Each sends
  shapes botocore does not; each needs its binary on the runner.
- **Below the SDK** — bad signatures, clock skew, malformed
  `Content-Length`, `Expect: 100-continue`. Unreachable through boto3;
  needs a hand-rolled socket and signer.
- **Unlicensed answers** — `403 NotLicensed` for entering versioning
  without `S3_VERSIONING`. The session mocks the entitlement entitled and
  the daemon caches it at start-up, so this needs a module owning its own
  service lifecycle.
- **Concurrency** — racing writers, a read in flight under an overwrite.
