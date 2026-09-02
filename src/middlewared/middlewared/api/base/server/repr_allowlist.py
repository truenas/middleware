from middlewared.alert.base import AlertClass

# A list of classes that appear in job parameters list, and so they must be serializable to JSON (they will be
# serialized as `{"repr": "<object at 0x...>"}`). Otherwise, `core.get_jobs` serialization will fail with `TypeError`.
# We don't do this for all classes, because failure to serialize an unexpected class acts like a canary that we have
# data flow issues. This list is here mostly for integration tests.
REPR_ALLOWLIST = (AlertClass,)
