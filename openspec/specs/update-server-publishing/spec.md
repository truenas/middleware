# Update Server Publishing

## Purpose

This capability defines the contract that content published on the update server must satisfy in order
for TrueNAS systems to resolve their own version, decide which version to offer as an update, and
download it. It is addressed to the party that publishes update server content, and states obligations
on that content rather than on any consuming system.

Consuming systems assume this contract holds. Most of it is not validated at runtime, so a violation
does not surface as a diagnostic — it surfaces as systems selecting the wrong version, being offered no
version, or reporting an error status.

## Published Layout

A worked example of a conforming server. The requirements below refer back to it.

```
https://auto-public.sys.truenas.net/
├── trains_v2.json
├── TrueNAS-SCALE-Fangtooth/
│   ├── releases.json
│   ├── TrueNAS-SCALE-25.04.2.update
│   └── TrueNAS-SCALE-25.04.2.release-notes.txt
├── TrueNAS-Goldeye-BETA/
│   └── releases.json          ← redirected; frozen, still served
├── TrueNAS-Goldeye-RC/
│   ├── releases.json
│   └── TrueNAS-26.0.0-RC.1.update
└── TrueNAS-Goldeye/
    ├── releases.json
    ├── TrueNAS-26.0.0.update
    ├── TrueNAS-26.0.0.release-notes.txt
    └── TrueNAS-26.0.1.update
```

`trains_v2.json`:

```json
{
  "trains": {
    "TrueNAS-SCALE-Fangtooth": {
      "description": "TrueNAS 25.04 [release]",
      "stable": true,
      "max_profile": "MISSION_CRITICAL"
    },
    "TrueNAS-Goldeye-RC": {
      "description": "TrueNAS 26.0 [release candidate]",
      "stable": false,
      "max_profile": "EARLY_ADOPTER"
    },
    "TrueNAS-Goldeye": {
      "description": "TrueNAS 26.0 [release]",
      "stable": true,
      "max_profile": "GENERAL"
    }
  },
  "trains_redirection": {
    "TrueNAS-Goldeye-BETA": "TrueNAS-Goldeye-RC"
  }
}
```

Note that `TrueNAS-Goldeye-BETA` appears only as a redirection source. A superseded train is removed
from `trains`, but its release file is still served, because systems running a version from it resolve
their own version and profile there — see *Train redirection* below.

This is the usual progression: once the release candidate train opens, the beta train stops receiving
releases and is redirected onto it, carrying beta testers forward without their having to reinstall.
When the release candidate train is in turn superseded by the general release train, the beta
redirection SHALL be re-pointed at the same time — see *Train redirection* below.

`TrueNAS-Goldeye/releases.json`:

```json
{
  "26.0.0": {
    "filename": "TrueNAS-26.0.0.update",
    "version": "26.0.0",
    "date": "2026-04-14",
    "changelog": "https://truenas.com/docs/goldeye/26.0.0/",
    "checksum": "3b1f8a02c47d5e9061b8d4c2f7a930e5c81d64ab29f70e3d5c8b1a4f6e2d90c7",
    "filesize": 2483027968,
    "profile": "GENERAL"
  },
  "26.0.1": {
    "filename": "TrueNAS-26.0.1.update",
    "version": "26.0.1",
    "date": "2026-06-02",
    "changelog": "https://truenas.com/docs/goldeye/26.0.1/",
    "checksum": "9c4e7d1a6b3f0582ae4c9d7b1e63a8e05d2c7419b8e6a3d0f5c1b9e7a24d68f3",
    "filesize": 2491416576,
    "profile": "EARLY_ADOPTER"
  }
}
```

This illustrates several obligations at once:

- Releases are ordered **oldest first**, so `26.0.1` being last is what makes it the newest.
- The train's `max_profile` is `GENERAL` — the highest profile across *all* its releases, which here is
  the older one. It is not the profile of the newest release.
- A system configured for `GENERAL` is therefore offered `26.0.0`, not `26.0.1`, because `26.0.1` has
  not yet been promoted that far.
- Version numbers do not reliably convey order across the product's history. The scheme changed within
  the 26 series, so a system on `26.04.x` updates forward onto `26.0.0` even though `26.0.0` ranks
  lower component-wise. Recency comes from train order and file order, never from comparing version
  strings.

## Requirements

### Requirement: Train list document

The update server SHALL publish a train list at `trains_v2.json` in the server root, containing a
`trains` member mapping each train name to a train description, and optionally a `trains_redirection`
member mapping a train name to the name of the train that supersedes it.

Each train description MAY declare `description`, `stable`, and `max_profile`. Any member that is
omitted SHALL take its default: an empty description, `stable` true, and a `max_profile` of
`DEVELOPER`.

Publishers SHALL treat those defaults as significant rather than neutral. A train published with no
declared members halts the forward walk at itself and is excluded from every configuration other than
`DEVELOPER`:

```json
"TrueNAS-Halfmoon": {}
```

is equivalent to, and behaves as:

```json
"TrueNAS-Halfmoon": {
  "description": "",
  "stable": true,
  "max_profile": "DEVELOPER"
}
```

The least-specified train is therefore the most restrictive one. Any train intended to be reachable
SHALL declare `max_profile` explicitly, and any pre-release train SHALL declare `stable` explicitly.

#### Scenario: A train omits its properties

- **WHEN** a train is published with no `stable` or `max_profile` declared
- **THEN** it is treated as stable and as containing nothing above `DEVELOPER`, which stops the search
  at that train and hides it from all but `DEVELOPER` configurations

#### Scenario: No redirections are in force

- **WHEN** `trains_redirection` is omitted
- **THEN** no train is treated as superseded

### Requirement: Train sequence order is significant

Trains SHALL be listed in `trains_v2.json` in ascending release order, oldest first. Consuming systems
determine which trains a system may advance to by taking the entries positioned after its current
train, and SHALL NOT sort the list or compare train names.

#### Scenario: Trains are listed out of order

- **WHEN** a train is positioned earlier in the list than a train it supersedes
- **THEN** systems on the superseded train do not see it as an upgrade candidate, and systems on it may
  be offered an older train's releases

### Requirement: Stable trains are mandatory stepping stones

A train that constitutes a release systems must pass through SHALL be published with `stable` true.
Consuming systems stop their forward walk at the first stable train and SHALL NOT skip past it, so
pre-release trains such as nightly, alpha, beta, and release candidate trains SHALL be published with
`stable` false.

#### Scenario: A pre-release train is published as stable

- **WHEN** a release candidate train is published with `stable` true or without the member
- **THEN** the forward walk halts there and systems are never offered the general release beyond it

#### Scenario: Intermediate pre-release trains precede a stable train

- **WHEN** one or more trains with `stable` false are followed by a train with `stable` true
- **THEN** all of them are candidates, and the search stops at the stable train

### Requirement: Declared highest profile is accurate

A train's declared highest profile, carried in the `max_profile` member, SHALL name the highest profile
attained by any release in that train's release file. It SHALL be updated when a release in the train is
promoted past the currently declared value.

Consuming systems use this member to skip trains without fetching them. Declaring it below the true
highest hides releases; declaring it above causes trains to be fetched needlessly.

Given a train whose releases carry `GENERAL`, `EARLY_ADOPTER`, and `EARLY_ADOPTER`, the correct
declaration is the highest across all of them, not the profile of the newest:

```json
"TrueNAS-Goldeye": { "stable": true, "max_profile": "GENERAL" }
```

When `26.0.1` is later promoted from `EARLY_ADOPTER` to `MISSION_CRITICAL`, both the release entry and
the train's declaration are updated:

```json
"TrueNAS-Goldeye": { "stable": true, "max_profile": "MISSION_CRITICAL" }
```

#### Scenario: A train's declared highest profile is understated

- **WHEN** a train contains a `GENERAL` release but declares `max_profile` as `EARLY_ADOPTER`
- **THEN** systems configured for `GENERAL` exclude the train without fetching it, and never see that
  release

#### Scenario: A release is promoted past the declared highest profile

- **WHEN** a release in a train is promoted to a profile above the train's declared `max_profile`
- **THEN** the train's `max_profile` is raised to match, so that systems requiring that profile begin
  considering the train

### Requirement: Release file

For each train, the update server SHALL publish a release file at `<train>/releases.json`, mapping each
version string to a release description. Every release description SHALL carry all of `filename`,
`version`, `date`, `changelog`, `checksum`, `filesize`, and `profile`. None of these have defaults, and
omitting any one SHALL be understood to invalidate the entire train for consuming systems, not merely
the affected release.

The `profile` member SHALL be one of `DEVELOPER`, `EARLY_ADOPTER`, `GENERAL`, or `MISSION_CRITICAL`.

#### Scenario: A release omits a required member

- **WHEN** any release in a train's release file omits one of the required members
- **THEN** the whole release file fails to parse and systems treat the train as unavailable

### Requirement: Release order is significant

Releases SHALL be listed within a release file in ascending order, oldest first, so that the last entry
is the newest release in that train. Consuming systems read the file in reverse to find the newest
acceptable release, and SHALL NOT sort entries or compare version numbers to establish recency.

Version numbers SHALL NOT be relied upon to convey order. They have not increased monotonically across
the product's history — `26.04.x` is followed by `26.0.0` — so file position is the only expression of
recency available to consuming systems.

#### Scenario: A newer release is inserted before an older one

- **WHEN** a release is positioned earlier in the release file than a release it supersedes
- **THEN** consuming systems treat the older release as newer and may select it instead

### Requirement: Releases are promoted as they mature

A release's `profile` SHALL state the maturity that release has attained. While its train is still
receiving releases, that profile SHALL be raised as field data accumulates.

Consuming systems derive an operator's permitted configuration range from the profile of the version
they are running. Leaving a release at its initial profile while its train is still live holds every
system running it below the configuration range its maturity would justify.

Promotion necessarily ends when a train is superseded, because its release file is frozen from that
point — see *Train redirection*. Releases in a superseded train permanently retain the profile they
held at the moment of supersession, and this is not a defect: a system running one of them draws its
update candidates from the redirection target, whose releases are still being promoted, so the frozen
profile lasts only until that system's next update.

#### Scenario: A release accumulates field history

- **WHEN** a release published at `EARLY_ADOPTER` in a live train proves stable in the field
- **THEN** its `profile` is raised, and systems running it become able to select the higher profile

#### Scenario: A release's train is superseded

- **WHEN** a train is superseded and its release file frozen
- **THEN** the profiles of its releases stop changing, and systems running them retain that profile
  until they update onto the redirection target

### Requirement: Train redirection

A train that is no longer receiving releases MAY be superseded by naming its replacement in
`trains_redirection`. For every such redirection the publisher SHALL guarantee that:

- the superseded train's release file is frozen and continues to be served in perpetuity, because
  systems still running a version from it resolve their own version and profile from that file;
- the superseded train SHALL NOT remain listed in `trains`, and is named only as a redirection source,
  so that systems on earlier trains do not walk forward into a train that no longer receives releases;
- the redirection does not chain, meaning the target of a redirection is never itself the source of
  another;
- the target train is present in `trains_v2.json`.

Removing a superseded train from `trains` does not strand the systems running its releases. They
resolve their current train through the redirection and draw candidates from the target, and they read
their own profile from the frozen release file directly rather than through the train list.

Because redirections may not chain, superseding a train that is *already* a redirection target imposes
a simultaneous obligation: every redirection pointing at it SHALL be re-pointed at the new target in
the same publication. Redirections accumulate on the way through a release cycle, so this applies to
all of them, not only the most recent.

Following a release cycle through, with each state a complete `trains_redirection`:

```json
{ "TrueNAS-Goldeye-BETA": "TrueNAS-Goldeye-RC" }
```

Then the general release train opens and the release candidate train is superseded. Both entries change
together — the beta entry is re-pointed rather than left to chain through the release candidate train:

```json
{
  "TrueNAS-Goldeye-BETA": "TrueNAS-Goldeye",
  "TrueNAS-Goldeye-RC": "TrueNAS-Goldeye"
}
```

Publishing only the second entry would leave `TrueNAS-Goldeye-BETA` pointing at a train that is itself
a redirection source, which resolves one hop and strands beta systems on the superseded release
candidate train.

#### Scenario: A train stops receiving releases

- **WHEN** a train is superseded and redirected
- **THEN** it is removed from `trains` and named only in `trains_redirection`, its release file
  continues to be served unchanged, and systems running versions from it draw their update candidates
  from the target train

#### Scenario: A superseded train is left listed among the trains

- **WHEN** a train is redirected but not removed from `trains`
- **THEN** systems on earlier trains treat it as an upgrade candidate and may select one of its frozen
  releases, landing on a train they must immediately leave again

#### Scenario: A redirection target is itself superseded

- **WHEN** a train that is already the target of one or more redirections is superseded
- **THEN** those redirections are re-pointed at the new target in the same publication, so that no
  redirection resolves to another redirection source

#### Scenario: A superseded train's release file is withdrawn

- **WHEN** a redirected train's release file stops being served
- **THEN** systems still running a version from it can no longer determine their own profile and report
  an error status instead of an available update

#### Scenario: A redirection target is itself redirected

- **WHEN** a train is redirected to a train that is also a redirection source
- **THEN** only one hop is resolved, and systems land on a train that is no longer current

### Requirement: A version belongs to exactly one train

A given version string SHALL appear in the release file of exactly one train. Consuming systems resolve
the profile of the version they are running by looking it up in the release file of the train recorded
in their shipped image, and rely on that lookup being unambiguous.

#### Scenario: A version is published in two trains

- **WHEN** the same version string appears in two trains' release files
- **THEN** which record governs a running system's profile depends on the train recorded in its image
  rather than on the train it draws updates from, and the two records may disagree

### Requirement: Every shipped version is published in its train

For every image shipped to systems, the version string recorded in that image SHALL appear as an entry
in the release file of the train recorded in that same image.

A system whose version is absent from its train's release file cannot determine its own profile, and
SHALL report an error rather than assuming one, except where its version string contains `CUSTOM`,
`INTERNAL`, or `MASTER`, which are treated as development builds.

#### Scenario: A shipped version is absent from its train

- **WHEN** a system's version does not appear in its recorded train's release file and is not marked as
  a development build
- **THEN** the system cannot determine its profile and reports an error status

### Requirement: Metadata documents are always available

`trains_v2.json` and every release file referenced from it SHALL remain available for retrieval at all
times. A document that cannot be retrieved SHALL be understood to fail the entire update check for
every system that reaches it, rather than to indicate that no update is available.

#### Scenario: A release file cannot be retrieved

- **WHEN** a train's release file cannot be retrieved
- **THEN** consuming systems report an error, and no update is offered even if every other train is
  intact

### Requirement: Update file

For every release in a train listed in `trains`, the update file SHALL be available at
`<train>/<filename>`, using the `filename` declared for that release. Its size SHALL equal the
release's declared `filesize`, and its SHA-256 digest SHALL equal the release's declared `checksum`.

The update files of a superseded train MAY be withdrawn once that train is redirected, because a
superseded train never supplies update candidates: systems running its releases draw candidates from
the redirection target. Its release file SHALL nonetheless be retained and served in perpetuity, as
*Train redirection* requires. The distinction is deliberate — the release file is what those systems
read to resolve their own profile and is small, whereas retaining every superseded pre-release image
indefinitely is not.

A file that disagrees with its release entry SHALL be understood to be unusable rather than merely
suspect: consuming systems discard it and download it again, so a lasting disagreement presents as a
download that never completes rather than as a reported error.

An update file SHALL NOT be replaced in place without its release entry being updated in the same
publication. Publishing a rebuilt file under an unchanged `checksum` and `filesize` leaves systems that
already hold the previous file and systems fetching the new one unable to agree on which is valid.

#### Scenario: An update file disagrees with its release entry

- **WHEN** an update file's digest or size differs from the values declared for that release
- **THEN** consuming systems discard the downloaded file and attempt the download again, and never
  install it

#### Scenario: An update file is rebuilt

- **WHEN** a release's update file is replaced with a rebuilt file
- **THEN** that release's `checksum` and `filesize` are updated in the same publication to match it

#### Scenario: A superseded train's update files are withdrawn

- **WHEN** a train has been redirected and its update files are removed from the server
- **THEN** systems running its releases are unaffected, because they read only its retained release
  file and download their candidates from the redirection target

### Requirement: Release notes are optional

Release notes for a release MAY be published at `<train>/<filename without its .update suffix>.release-notes.txt`.
Consuming systems SHALL treat their absence as acceptable, and are not obliged to re-check for them
promptly once observed absent.

#### Scenario: Release notes are not published

- **WHEN** no release notes document exists for a release
- **THEN** the release is still offered, with no release notes attached

#### Scenario: Release notes are published after the release

- **WHEN** release notes are added for a release whose absence has already been observed
- **THEN** consuming systems may continue to report them as absent for a period before observing them
