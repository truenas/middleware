# Update Version Selection

## Purpose

This capability defines how the system reads the state published on the update server and decides
which single version, if any, it should offer and download as the next update. Selection walks two
axes in a fixed order: first the sequence of trains, then the releases within a train. Profiles are an
input to this decision and are defined in the `update-profiles` capability.

## Requirements

### Requirement: Reliance on published content

Selection SHALL rely on the update server content satisfying the `update-server-publishing`
capability, and SHALL NOT verify those guarantees at runtime.

Where this capability depends on a property of published content — the order of trains, the order of
releases within a train, the accuracy of a train's declared highest profile, the permanence of a
redirected train's release file, or a version appearing in exactly one train — that property is an
obligation on the publisher and is specified there rather than restated here.

#### Scenario: Published content satisfies the contract

- **WHEN** published content satisfies the `update-server-publishing` capability
- **THEN** the selection behavior specified below holds

#### Scenario: Published content violates the contract

- **WHEN** published content does not satisfy that capability
- **THEN** selection yields an incorrect or absent result rather than reporting a contract violation,
  because these properties are not checked

### Requirement: Current train resolution

The system SHALL take the current train from the local update manifest, and SHALL substitute the
redirect target when the update server declares a redirection for that train. Resolution SHALL apply
exactly one redirection hop.

If the resolved current train is absent from the published train list, the system SHALL treat it as
present with default properties, which places it last in the train sequence.

#### Scenario: Current train is not redirected

- **WHEN** the manifest's train has no redirection entry
- **THEN** the manifest's train is the current train

#### Scenario: Current train is redirected

- **WHEN** the manifest's train has a redirection entry
- **THEN** the redirect target is the current train, and update candidates are drawn from that target

### Requirement: Identity is read from the frozen train, targets from the live train

For a system whose train has been redirected, the frozen release file of the recorded train SHALL
supply only the identity of the running version, while all update candidates SHALL be drawn from the
redirect target, which continues to receive new releases.

Because every update moves the running version onto a release published in the live target train, a
profile derived from a frozen release file SHALL persist only until the next update, and SHALL never
prevent that update from being offered.

#### Scenario: System is running a version from a redirected train

- **WHEN** the running version belongs to a train that has since been redirected
- **THEN** its profile is read from that train's frozen release file, and its update candidates are
  drawn from the redirect target

#### Scenario: System updates off a redirected train

- **WHEN** a system running a version from a redirected train installs a candidate from the redirect
  target
- **THEN** its profile is thereafter read from the target's live release file and tracks subsequent
  promotions

### Requirement: Candidate train list

The system SHALL build the list of candidate trains by walking the published train sequence forward
from the current train, and SHALL:

- include a train only when the train's declared highest profile ranks at or above the configured
  profile, so that trains which cannot contain an acceptable release are never fetched;
- stop after the first train marked stable, because stable trains are mandatory stepping stones and
  SHALL NOT be skipped;
- treat a train as stable, and as reaching only `DEVELOPER`, when it does not declare otherwise;
- order the collected trains newest first, and append the current train last, so that a release on the
  train already in use is chosen only when no newer train offers an acceptable one.

The current train SHALL be appended unconditionally and SHALL NOT be subject to the profile filter
applied to the trains beyond it.

#### Scenario: A stable train is reached

- **WHEN** walking forward encounters a train marked stable
- **THEN** that train is the last one considered, and trains beyond it are not candidates

#### Scenario: A train cannot contain an acceptable release

- **WHEN** a train beyond the current one declares a highest profile ranking below the
  configured profile
- **THEN** that train is excluded before its release file is fetched

#### Scenario: No newer train qualifies

- **WHEN** every train beyond the current one is excluded
- **THEN** the current train alone remains a candidate, and is still scanned

### Requirement: Train order takes strict priority over version order

Selection SHALL treat the candidate train order as a strict priority ranking. The first candidate
train containing any acceptable release SHALL win outright, and its chosen release SHALL be the
answer even if a later candidate train contains a higher version number. The system SHALL NOT compare
version numbers across trains.

Note that version numbers are not a safe substitute for this ordering. Version numbers do not increase
monotonically across the product's history: `26.04.x` is followed by `26.0.0`, so a component-wise
comparison ranks the newer release below the older one, and update eligibility carries an explicit
rule for that transition. A rule of the form "the highest version number across all candidate trains
wins" would therefore not preserve the behavior specified here.

#### Scenario: An earlier candidate train yields a lower version number

- **WHEN** the first candidate train contains an acceptable release whose version number is lower than
  an acceptable release in a later candidate train
- **THEN** the release from the first candidate train is chosen

#### Scenario: A candidate train yields nothing

- **WHEN** a candidate train contains no acceptable release
- **THEN** the next candidate train is scanned

### Requirement: Release recency follows release file order

Within a train, the system SHALL treat the order of entries in the published release file as the
authoritative statement of recency, scanning it in reverse so that the last entry is considered
newest. The system SHALL NOT sort or otherwise compare version numbers to establish this order.

#### Scenario: A train's releases are scanned

- **WHEN** a candidate train's release file is scanned for an acceptable release
- **THEN** entries are considered from last to first, and the first acceptable entry is chosen

### Requirement: Selection outcome

Having chosen a release, the system SHALL report one of the following outcomes:

- when the chosen release is the running version, that no new version is available;
- when the chosen release is a version the running version may update to, that version as the new
  version, together with its manifest and release notes;
- when the chosen release is not a version the running version may update to, an error stating that
  the installed version is newer than the newest version the winning train provides.

The system SHALL NOT fall back to another train or to an older release once a release has been chosen.

#### Scenario: System is up to date

- **WHEN** the chosen release is the running version
- **THEN** the system reports no new version, rather than an error

#### Scenario: An update is available

- **WHEN** the chosen release differs from the running version and may be updated to
- **THEN** that release is reported as the new version

#### Scenario: The winning train has fallen behind the running version

- **WHEN** the chosen release may not be updated to because the running version is newer
- **THEN** the system reports an error and does not reconsider other candidates

#### Scenario: No candidate train contains an acceptable release

- **WHEN** every candidate train has been scanned without finding a release matching the configured
  profile
- **THEN** the system reports an error stating that no releases match the configured update profile

### Requirement: Conditions reported instead of a version

The system SHALL report the following conditions in place of a selection outcome, each distinguishable
by the caller:

- an update has already been applied and the system is awaiting reboot;
- the system is licensed for high availability but high availability is currently unavailable;
- the published update server content could not be retrieved or parsed.

#### Scenario: An update is already applied

- **WHEN** an update has been applied and the system has not yet rebooted
- **THEN** the system reports that a reboot is required, without evaluating candidates

#### Scenario: High availability is degraded

- **WHEN** the system is licensed for high availability and high availability is unavailable
- **THEN** the system reports that condition, without evaluating candidates

#### Scenario: The update server cannot be reached

- **WHEN** retrieving or parsing published update server content fails
- **THEN** the system reports an error carrying the failure reason, rather than reporting that no
  update is available

### Requirement: Automatic download decision

When automatic checking is enabled, the system SHALL check the update server once nightly and download
the selected version if one is available. When automatic checking is disabled, no such check SHALL be
scheduled.

The nightly download SHALL reuse the selection outcome rather than applying its own policy, and SHALL
take no action when the selection reports no new version.

#### Scenario: Automatic checking is enabled and an update is available

- **WHEN** the nightly check runs and selection reports a new version
- **THEN** that version is downloaded

#### Scenario: Automatic checking is enabled and no update is available

- **WHEN** the nightly check runs and selection reports no new version
- **THEN** nothing is downloaded

#### Scenario: Automatic checking is toggled

- **WHEN** automatic checking is enabled or disabled
- **THEN** the nightly schedule is added or removed accordingly

### Requirement: Explicitly requested versions bypass the profile

A caller MAY request a specific train and version for download or installation. Such a request SHALL be
validated only against whether the running version may update to it, and SHALL NOT be checked against
the configured profile.

A request SHALL specify both a train and a version, or neither; specifying one alone SHALL be rejected.

#### Scenario: A caller requests a version below the configured profile

- **WHEN** a caller requests a specific train and version whose profile ranks below the configured
  profile
- **THEN** the request proceeds, because the configured profile governs only automatic selection

#### Scenario: A caller requests a version that cannot be updated to

- **WHEN** a caller requests a specific train and version the running version may not update to
- **THEN** the request is rejected

#### Scenario: A caller supplies an incomplete request

- **WHEN** a caller supplies a train without a version, or a version without a train
- **THEN** the request is rejected

### Requirement: Enumeration of available versions

The system SHALL expose an enumeration of the versions present in every candidate train. Because the
candidate train list is itself constrained by the configured profile, the enumeration inherits that
train-level constraint. Within those trains, however, releases SHALL be filtered only by whether the
running version may update to them, and SHALL NOT be filtered by their own profile.

#### Scenario: Versions are enumerated

- **WHEN** the available versions are enumerated
- **THEN** every version in every candidate train that the running version may update to is returned,
  including versions whose own profile ranks below the configured profile
