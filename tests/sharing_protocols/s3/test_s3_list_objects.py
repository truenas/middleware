"""The listing argument matrix: prefixes, delimiters, caps and cursors.

A listing is the operation a client spends most of its requests on and
the one whose contract is almost entirely about arguments, so it is
where a thin suite costs the most. Every case here drains what it wrote:
the bucket is session-scoped and shared with every other module.

**One divergence shapes every case below.** This server lists a
directory as a 0-byte `Contents` row when no delimiter is given, where
AWS emits a row only for a key a client actually `PUT` — nothing on disk
separates an implicit ancestor from an explicit `key/` marker. So the
argument cases filter directory rows out and assert on the keys they
wrote, and the divergence itself is asserted once, deliberately, in
`test_only_a_directory_a_client_asked_for_is_a_row`.
"""

import pytest
from s3_client import code_of, drain, raw_query, status_of

PREFIX = "edges/"

#: Two directories and a bare key, so a delimiter has something to fold
#: and something to leave alone.
TREE = [
    f"{PREFIX}asdf",
    f"{PREFIX}boo/bar",
    f"{PREFIX}boo/baz/xyzzy",
    f"{PREFIX}cquux/thud",
    f"{PREFIX}cquux/bla",
]


@pytest.fixture(scope="module")
def tree(s3, bucket):
    drain(s3, bucket, PREFIX)
    for key in TREE:
        s3.put_object(Bucket=bucket, Key=key, Body=b"")
    yield PREFIX
    drain(s3, bucket, PREFIX)


def keys_of(page):
    return [c["Key"] for c in page.get("Contents", [])]


def objects_of(page):
    """`keys_of` without the directory rows — see the module docstring."""
    return [k for k in keys_of(page) if not k.endswith("/")]


def groups_of(page):
    return [p["Prefix"] for p in page.get("CommonPrefixes", [])]


# ── the shapes a client actually uses ────────────────────────────────


def test_a_flat_listing_is_in_path_byte_order(s3, bucket, tree):
    page = s3.list_objects_v2(Bucket=bucket, Prefix=tree)
    assert objects_of(page) == sorted(TREE)


def test_a_delimiter_folds_one_level(s3, bucket, tree):
    page = s3.list_objects_v2(Bucket=bucket, Prefix=tree, Delimiter="/")
    assert keys_of(page) == [f"{PREFIX}asdf"]
    assert groups_of(page) == [f"{PREFIX}boo/", f"{PREFIX}cquux/"]


def test_a_delimiter_that_matches_nothing_folds_nothing(s3, bucket, tree):
    page = s3.list_objects_v2(Bucket=bucket, Prefix=tree, Delimiter="!")
    assert sorted(objects_of(page)) == sorted(TREE)
    assert groups_of(page) == []


def test_an_empty_delimiter_is_no_delimiter(s3, bucket, tree):
    """`delimiter=` is what a client sends when its own parameter is
    unset, and folding on it would collapse the listing to one group."""
    page = s3.list_objects_v2(Bucket=bucket, Prefix=tree, Delimiter="")
    assert sorted(objects_of(page)) == sorted(TREE)
    assert groups_of(page) == []


def test_a_multi_character_delimiter_folds_on_the_whole_string(s3, bucket):
    """A delimiter is a string, not a character, and folding on its first
    byte would group `boo/bar` under `b`."""
    drain(s3, bucket, "alt/")
    for key in ["alt/boo/bar", "alt/boo/baz", "alt/plain"]:
        s3.put_object(Bucket=bucket, Key=key, Body=b"")
    try:
        page = s3.list_objects_v2(Bucket=bucket, Prefix="alt/", Delimiter="oo/")
        assert groups_of(page) == ["alt/boo/"]
        assert keys_of(page) == ["alt/plain"]
    finally:
        drain(s3, bucket, "alt/")


def test_a_prefix_ending_in_the_delimiter_lists_that_level(s3, bucket, tree):
    """The prefix names a directory, so its own row must not come back as
    a group of itself — the recursion a resume rule depends on."""
    page = s3.list_objects_v2(Bucket=bucket, Prefix=f"{PREFIX}boo/", Delimiter="/")
    assert keys_of(page) == [f"{PREFIX}boo/bar"]
    assert groups_of(page) == [f"{PREFIX}boo/baz/"]


@pytest.mark.parametrize(
    "prefix,keys,delimiter,groups,rest",
    [
        ("ws/", ["ws/a b", "ws/a c", "ws/plain"], " ", ["ws/a "], ["ws/plain"]),
        ("pct/", ["pct/b%ar", "pct/b%az", "pct/plain"], "%", ["pct/b%"], ["pct/plain"]),
    ],
    ids=["whitespace", "percent"],
)
def test_an_awkward_delimiter_byte_folds(s3, bucket, prefix, keys, delimiter, groups, rest):
    """A space is a legal delimiter and a legal key byte, and `%` is the
    one byte the `encoding-type=url` round trip can corrupt — so folding
    on each exercises the encoder and the grouper together."""
    drain(s3, bucket, prefix)
    for key in keys:
        s3.put_object(Bucket=bucket, Key=key, Body=b"")
    try:
        page = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, Delimiter=delimiter)
        assert groups_of(page) == groups
        assert keys_of(page) == rest
    finally:
        drain(s3, bucket, prefix)


def test_a_fold_costs_one_row_however_many_keys_it_spans(s3, bucket):
    """A `CommonPrefixes` entry spends *one* of `max-keys`, not one per
    key underneath it.

    An implementation charging the page per underlying key truncates a
    listing that AWS answers whole, and the client pages forever over a
    directory it can never step past. The four bare keys are chosen for
    their bytes: `#` (0x23) and `+` (0x2B) both sort below the delimiter
    `/` (0x2F), which is the half a resume that advances by incrementing
    a byte gets wrong.
    """
    drain(s3, bucket, "fold/")
    kids = [f"fold/0/{i}" for i in range(1000, 1012)]
    bare = ["fold/1999", "fold/1999#", "fold/1999+", "fold/2000"]
    for key in kids + bare:
        s3.put_object(Bucket=bucket, Key=key, Body=b"")
    try:
        for name, call in (("v1", s3.list_objects), ("v2", s3.list_objects_v2)):
            page = call(Bucket=bucket, Prefix="fold/", Delimiter="/", MaxKeys=5)
            assert groups_of(page) == ["fold/0/"], name
            assert keys_of(page) == bare, name
            # Five asked for and five delivered — the group and the four
            # keys — so nothing is left to page over.
            assert page["IsTruncated"] is False, name
    finally:
        drain(s3, bucket, "fold/")


# ── max-keys ─────────────────────────────────────────────────────────


def test_max_keys_one_pages_the_whole_tree(s3, bucket, tree):
    """One row per page is the setting that finds a cursor that does not
    advance: at any larger cap a stalled marker still makes progress
    through the page and the walk terminates by luck."""
    seen = []
    token = None
    for _ in range(len(TREE) * 3 + 8):
        kwargs = {"Bucket": bucket, "Prefix": tree, "MaxKeys": 1}
        if token:
            kwargs["ContinuationToken"] = token
        page = s3.list_objects_v2(**kwargs)
        got = keys_of(page)
        assert len(got) <= 1, f"MaxKeys=1 returned {len(got)} rows"
        seen += [k for k in got if not k.endswith("/")]
        if not page.get("IsTruncated"):
            token = None
            break
        token = page.get("NextContinuationToken")
        assert token, "a truncated page named no continuation token"
    assert token is None, "the walk did not terminate"
    assert sorted(seen) == sorted(TREE)


def test_max_keys_zero_is_an_empty_untruncated_page(s3, bucket, tree):
    """A page with no last row has nothing to resume after, so
    `IsTruncated` must be false and no cursor may be offered."""
    for call, kwargs in ((s3.list_objects_v2, {"MaxKeys": 0}), (s3.list_objects, {"MaxKeys": 0})):
        page = call(Bucket=bucket, Prefix=tree, **kwargs)
        assert keys_of(page) == []
        assert page.get("IsTruncated") is False
        assert "NextContinuationToken" not in page
        assert "NextMarker" not in page


def test_max_keys_above_the_ceiling_is_clamped_not_refused(s3, bucket, tree):
    """S3 caps at 1000 and does not refuse a larger request, which is
    what an SDK sends when a caller asks for everything."""
    page = s3.list_objects_v2(Bucket=bucket, Prefix=tree, MaxKeys=100000)
    assert page["MaxKeys"] <= 1000
    assert sorted(objects_of(page)) == sorted(TREE)


def test_an_unparseable_max_keys_is_refused(s3, bucket, tree):
    """boto3 will not send a non-integer, so this goes on the wire by
    hand through the same signed client."""
    resp = raw_query(s3, bucket, {"list-type": "2", "max-keys": "blah"})
    assert resp.status_code == 400, resp.text[:400]
    assert "InvalidArgument" in resp.text


def test_the_default_max_keys_is_a_thousand_and_is_echoed(s3, bucket, tree):
    """A listing that names no `max-keys` is not unbounded: the default
    is a thousand and the response says so.

    Both halves matter — a server silently applying a smaller cap
    truncates without the client having asked, and one echoing the
    request's absence as `0` tells a client that reads the field it may
    stop. Asserted on all three listings, because each parses `max-keys`
    separately.
    """
    for name, page in (
        ("v1", s3.list_objects(Bucket=bucket, Prefix=tree)),
        ("v2", s3.list_objects_v2(Bucket=bucket, Prefix=tree)),
        ("versions", s3.list_object_versions(Bucket=bucket, Prefix=tree)),
    ):
        assert page["MaxKeys"] == 1000, name
        assert page["IsTruncated"] is False, name


# ── the resume tokens ────────────────────────────────────────────────


def test_a_marker_that_is_not_a_key_resumes_after_it(s3, bucket, tree):
    """V1's `marker` is a position, not a row that must exist.
    `edges/blah` sorts between `asdf` and `boo/`."""
    page = s3.list_objects(Bucket=bucket, Prefix=tree, Marker=f"{PREFIX}blah")
    assert objects_of(page) == [
        f"{PREFIX}boo/bar",
        f"{PREFIX}boo/baz/xyzzy",
        f"{PREFIX}cquux/bla",
        f"{PREFIX}cquux/thud",
    ]


def test_a_marker_past_every_key_lists_nothing(s3, bucket, tree):
    page = s3.list_objects(Bucket=bucket, Prefix=tree, Marker=f"{PREFIX}zzzzz")
    assert keys_of(page) == []
    assert page.get("IsTruncated") is False


def test_an_empty_marker_is_no_marker(s3, bucket, tree):
    page = s3.list_objects(Bucket=bucket, Prefix=tree, Marker="")
    assert sorted(objects_of(page)) == sorted(TREE)


def test_a_v1_walk_at_one_row_a_page_terminates(s3, bucket, tree):
    """`NextMarker` is a key by S3's definition, so a page ending on a
    `CommonPrefix` emits the prefix and the client hands it straight
    back.

    Compared as a plain key it consumes nothing, the page repeats and the
    marker never moves — boto3's own paginator refuses a token it has
    seen twice. Walked to exhaustion, because terminating is the property.
    """
    seen, marker, ended = [], None, False
    for _ in range(8):
        kwargs = {"Bucket": bucket, "Prefix": f"{PREFIX}", "Delimiter": "/", "MaxKeys": 1}
        if marker:
            kwargs["Marker"] = marker
        page = s3.list_objects(**kwargs)
        seen += [f"K:{c['Key']}" for c in page.get("Contents", [])]
        seen += [f"P:{p['Prefix']}" for p in page.get("CommonPrefixes", [])]
        if not page.get("IsTruncated"):
            ended = True
            break
        nxt = page.get("NextMarker")
        assert nxt is not None, "a truncated v1 delimiter page names one"
        assert nxt != marker, f"the v1 marker advances (stuck at {nxt})"
        marker = nxt
    assert ended, f"a v1 walk terminates (got {seen})"
    assert seen == [f"K:{PREFIX}asdf", f"P:{PREFIX}boo/", f"P:{PREFIX}cquux/"], seen


def test_start_after_and_a_continuation_token_together(s3, bucket, tree):
    """The token wins; `start-after` is only the first page's floor.

    A server that re-applied `start-after` on the resumed page would skip
    rows the client has not seen.
    """
    first = s3.list_objects_v2(Bucket=bucket, Prefix=tree, StartAfter=f"{PREFIX}asdf", MaxKeys=1)
    assert first["IsTruncated"]
    assert f"{PREFIX}asdf" not in keys_of(first)

    second = s3.list_objects_v2(
        Bucket=bucket,
        Prefix=tree,
        StartAfter=f"{PREFIX}asdf",
        ContinuationToken=first["NextContinuationToken"],
        MaxKeys=100,
    )
    both = objects_of(first) + objects_of(second)
    assert f"{PREFIX}asdf" not in both
    assert set(both) == {
        f"{PREFIX}boo/bar",
        f"{PREFIX}boo/baz/xyzzy",
        f"{PREFIX}cquux/bla",
        f"{PREFIX}cquux/thud",
    }


def test_an_empty_continuation_token_lists_from_the_start(s3, bucket, tree):
    """An empty token is accepted, echoed, and starts at the beginning —
    so the empty value is *absent*, not malformed.

    The forged token below is the one that must be refused: a value which
    does not decode was minted by someone, and answering it with an empty
    page is indistinguishable from an empty bucket.
    """
    page = s3.list_objects_v2(Bucket=bucket, Prefix=tree, ContinuationToken="")
    assert page.get("ContinuationToken") == ""
    assert page["IsTruncated"] is False
    assert sorted(objects_of(page)) == sorted(TREE)


@pytest.mark.parametrize("token", ["not-a-token", "AAAA", "//////", "eyJrIjoiYSJ9"])
def test_a_forged_continuation_token_is_refused(s3, bucket, tree, token):
    """A cursor defect this server once had, kept as a test: a token the
    server did not mint made a populated bucket report zero keys."""
    with pytest.raises(Exception) as caught:
        s3.list_objects_v2(Bucket=bucket, Prefix=tree, ContinuationToken=token)
    assert status_of(caught.value) == 400, token
    assert code_of(caught.value) == "InvalidArgument", token


# ── prefixes ─────────────────────────────────────────────────────────


def test_an_empty_prefix_is_no_prefix(s3, bucket, tree):
    page = s3.list_objects_v2(Bucket=bucket, Prefix="")
    assert set(TREE) <= set(objects_of(page))


def test_a_prefix_that_is_not_a_directory_boundary_still_matches(s3, bucket):
    """A prefix is a byte prefix, not a path component: `ba` must match
    `bar` and `baz` — a server that split on `/` first would return
    nothing."""
    drain(s3, bucket, "pfx/")
    for key in ["pfx/bar", "pfx/baz", "pfx/quux"]:
        s3.put_object(Bucket=bucket, Key=key, Body=b"")
    try:
        page = s3.list_objects_v2(Bucket=bucket, Prefix="pfx/ba")
        assert sorted(objects_of(page)) == ["pfx/bar", "pfx/baz"]
    finally:
        drain(s3, bucket, "pfx/")


def test_only_a_directory_a_client_asked_for_is_a_row(s3, bucket, tree):
    """Which directories are rows, asserted once where it is the subject.

    Both halves are pinned: a listing that started emitting implicit
    directories again would be the divergence this server used to have,
    and one that stopped emitting explicit markers would break every
    client that writes them — rclone under `directory_markers`, s3fs, and
    Veeam's Folder step.
    """
    page = s3.list_objects_v2(Bucket=bucket, Prefix=tree)
    assert [k for k in keys_of(page) if k.endswith("/")] == [], "an implied directory is not a row"

    marker = f"{PREFIX}boo/"
    s3.put_object(Bucket=bucket, Key=marker, Body=b"")
    try:
        page = s3.list_objects_v2(Bucket=bucket, Prefix=tree)
        rows = {c["Key"]: c for c in page["Contents"]}
        assert marker in rows, list(rows)
        assert rows[marker]["Size"] == 0
        assert rows[marker]["ETag"] == '"d41d8cd98f00b204e9800998ecf8427e"'
        assert [k for k in keys_of(page) if k.endswith("/")] == [marker]
    finally:
        s3.delete_object(Bucket=bucket, Key=marker)


# ── arguments a client sends as bytes, not as text ───────────────────


def test_a_control_character_delimiter_folds_nothing(s3, bucket, tree):
    """A delimiter is a byte string and not a path separator, so the
    answer is the ordinary one and the value is echoed back unchanged."""
    page = s3.list_objects(Bucket=bucket, Prefix=tree, Delimiter="\x0a")
    assert page["Delimiter"] == "\x0a"
    assert objects_of(page) == sorted(TREE)
    assert groups_of(page) == []


def test_a_control_character_marker_resumes_from_the_start(s3, bucket, tree):
    """`\\x0a` sorts before every key, so the page is the whole tree.

    The echo is asserted too: a server that treated an unprintable value
    as absent would answer the same page here and a different one for a
    marker that sorts in the middle.
    """
    page = s3.list_objects(Bucket=bucket, Prefix=tree, Marker="\x0a")
    assert page["Marker"] == "\x0a"
    assert page["IsTruncated"] is False
    assert objects_of(page) == sorted(TREE)

    v2 = s3.list_objects_v2(Bucket=bucket, Prefix=tree, StartAfter="\x0a")
    assert objects_of(v2) == sorted(TREE)


# ── what a row says, against what the object says ────────────────────


def test_a_listed_row_agrees_with_the_head_of_its_key(s3, bucket, tree):
    """A listing builds its rows from a directory walk and a HEAD builds
    its headers from an open file, so the two are separate reads of one
    object and are free to disagree — which is the whole reason to check.

    A client that lists to decide what to download compares these fields
    and skips anything it thinks it already has.
    """
    key = f"{PREFIX}rowdata.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"row data")
    try:
        row = next(c for c in s3.list_objects(Bucket=bucket, Prefix=key)["Contents"] if c["Key"] == key)
        head = s3.head_object(Bucket=bucket, Key=key)
        assert row["Size"] == head["ContentLength"]
        assert row["ETag"] == head["ETag"]
        assert row["LastModified"] == head["LastModified"]
        assert row["StorageClass"] == "STANDARD"
    finally:
        s3.delete_object(Bucket=bucket, Key=key)


def test_v2_stamps_an_owner_only_when_asked(s3, bucket, tree):
    """`fetch-owner` is v2's and its default is off; v1 has no such
    argument and stamps the block into every row.

    The default matters: an owner block is per row, and sending it
    unasked inflates every page of every listing a client makes.
    """
    default = s3.list_objects_v2(Bucket=bucket, Prefix=tree)
    assert "Owner" not in default["Contents"][0]

    asked = s3.list_objects_v2(Bucket=bucket, Prefix=tree, FetchOwner=True)
    owner = asked["Contents"][0]["Owner"]
    assert owner.get("ID"), owner

    v1 = s3.list_objects(Bucket=bucket, Prefix=tree)
    assert v1["Contents"][0]["Owner"]["ID"] == owner["ID"]


def test_the_key_count_follows_the_page(s3, bucket, tree):
    """`KeyCount` is this page's `Contents` plus its `CommonPrefixes`: a
    v2-only element that counts the page rather than the bucket, which a
    client uses to size its own buffer before parsing."""
    whole = s3.list_objects_v2(Bucket=bucket, Prefix=tree)
    assert whole["KeyCount"] == len(whole["Contents"])

    folded = s3.list_objects_v2(Bucket=bucket, Prefix=tree, Delimiter="/")
    assert folded["KeyCount"] == len(folded.get("Contents", [])) + len(folded.get("CommonPrefixes", []))

    capped = s3.list_objects_v2(Bucket=bucket, Prefix=tree, MaxKeys=2)
    assert capped["KeyCount"] == 2
    assert capped["IsTruncated"] is True


# ── encoding-type=url ────────────────────────────────────────────────


def elements(xml, tag):
    return [chunk.split(f"</{tag}>")[0] for chunk in xml.split(f"<{tag}>")[1:] if f"</{tag}>" in chunk]


@pytest.fixture
def awkward(s3, bucket):
    """Keys covering the classes the encoder decides between."""
    drain(s3, bucket, "enc/")
    keys = ["enc/a b", "enc/p+q", "enc/~tilde", "enc/paren(3).png"]
    for key in keys:
        s3.put_object(Bucket=bucket, Key=key, Body=b"x")
    yield keys
    drain(s3, bucket, "enc/")


def test_the_encoder_percent_encodes_and_leaves_the_unreserved_set(s3, bucket, awkward):
    """Percent-encoding, not form encoding.

    MinIO's own table asserts `a b` becomes `a+b` and `~user` becomes
    `%7Euser`; this server answers `a%20b` and leaves `~` alone, which is
    what the reference's own example shows and what RFC 3986's unreserved
    set gives. A client running a form-style decoder over the response —
    which the Java and Go SDKs do — turns `+` back into a space, so a
    literal `+` must leave here as `%2B` or the key it names is corrupted.
    """
    resp = raw_query(s3, bucket, {"list-type": "2", "prefix": "enc/", "encoding-type": "url"})
    assert resp.status_code == 200
    keys = elements(resp.text, "Key")
    assert "enc/paren%283%29.png" in keys, "the reference's own example"
    assert "enc/a%20b" in keys
    assert "enc/p%2Bq" in keys
    assert "enc/a+b" not in keys
    assert "enc/~tilde" in keys, "`~` is RFC 3986 unreserved"
    assert "<EncodingType>url</EncodingType>" in resp.text


def test_without_the_parameter_nothing_is_encoded(s3, bucket, awkward):
    """The negative control: the encoder runs on request, not always."""
    resp = raw_query(s3, bucket, {"list-type": "2", "prefix": "enc/"})
    keys = elements(resp.text, "Key")
    assert "enc/a b" in keys
    assert "enc/paren(3).png" in keys
    assert "<EncodingType>" not in resp.text


def test_a_common_prefix_is_encoded_too(s3, bucket):
    """A client that resumes into a group sends the value back, so an
    unencoded one round-trips wrong."""
    drain(s3, bucket, "grp/")
    s3.put_object(Bucket=bucket, Key="grp/sp ace/one.txt", Body=b"x")
    try:
        resp = raw_query(
            s3,
            bucket,
            {"list-type": "2", "prefix": "grp/", "delimiter": "/", "encoding-type": "url"},
        )
        assert "grp/sp%20ace/" in elements(resp.text, "Prefix")
    finally:
        drain(s3, bucket, "grp/")


def test_an_unknown_encoding_type_is_refused(s3, bucket):
    """*Valid Values: url*. Ignoring it would hand back keys the client is
    about to decode."""
    resp = raw_query(s3, bucket, {"list-type": "2", "encoding-type": "bogus"})
    assert resp.status_code == 400
    assert "<Code>InvalidArgument</Code>" in resp.text
