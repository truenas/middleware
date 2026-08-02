# Update Profiles

## Purpose

Update profiles express how much field testing an operator requires of a system version before
accepting it as an update. This capability defines the profile ladder, how a profile is assigned to a
release and to the running system, which profiles an operator may select, and how the system reports
compliance with the selected profile.

## Requirements

### Requirement: Profile ladder ordering and terminology

The system SHALL define exactly four update profiles, totally ordered. In ascending order they are
`DEVELOPER`, `EARLY_ADOPTER`, `GENERAL`, `MISSION_CRITICAL`, carrying the ordinal values 0, 1, 2 and 3
respectively. Every comparison between profiles SHALL use this ordering.

Wherever profiles are reasoned about, the following terms SHALL carry these meanings:

| Term | Meaning |
| --- | --- |
| **rank** | a profile's position in the ordering above |
| **higher**, **above** | greater ordinal value; nearer `MISSION_CRITICAL` |
| **lower**, **below** | smaller ordinal value; nearer `DEVELOPER` |
| **at or above** | greater than or equal in rank; the comparison used by the profile match test |
| **at or below** | less than or equal in rank |
| **highest**, **lowest** | the greatest-ranked and least-ranked member of a set of profiles |
| **maturity** | the extent of field testing a release is held to have received; a release's rank is a statement of its maturity |
| **promoted** | re-labelled from a lower rank to a higher one as field data accumulates |
| **attained** | the rank a release has been promoted to so far |

Rank direction SHALL NOT be read as permissiveness. A release at a higher rank is acceptable to more
configurations, whereas a configured profile at a higher rank accepts fewer releases. Raising the
configured profile therefore narrows the set of acceptable releases and lowering it widens that set:
`DEVELOPER` as a configured profile accepts every release, and `MISSION_CRITICAL` as a configured
profile accepts only releases promoted to `MISSION_CRITICAL`.

#### Scenario: Two profiles are compared

- **WHEN** any two profiles are compared
- **THEN** `DEVELOPER` ranks lowest, `MISSION_CRITICAL` ranks highest, and `EARLY_ADOPTER` and
  `GENERAL` rank between them in that order

#### Scenario: The configured profile is raised

- **WHEN** the configured profile is changed to a higher rank
- **THEN** fewer releases are acceptable, because acceptability requires a release to rank at or above
  the configured profile

#### Scenario: A release is promoted

- **WHEN** a release is re-labelled from a lower rank to a higher one
- **THEN** its attained maturity has increased, and it becomes acceptable to configurations that
  previously declined it

### Requirement: Profile meaning depends on where it is attached

The same profile name SHALL carry a different meaning depending on what it is attached to:

- on a **release**, the maturity that release has been promoted to;
- on a **train**, the highest profile attained by any release in that train;
- in the **system configuration**, the *minimum* maturity the operator will accept.

A release is therefore expected to be re-labelled upward over its lifetime as field data accumulates.

The configured profile SHALL NOT be understood as selecting a separate stream of builds. Every system
draws from the same trains and the same releases; the configured profile sets how much field history a
release must have accumulated before that system will accept it. Two systems on different profiles
therefore generally receive the same release at different times, rather than different releases.

This holds only as far as promotion goes. A release that is never promoted to the configured profile is
skipped rather than delayed, and a train whose declared highest profile never reaches the configured
profile is never considered at all.

#### Scenario: Operator selects the lowest profile

- **WHEN** the configured profile is `DEVELOPER`
- **THEN** releases at every maturity are acceptable, because every profile ranks at or above
  `DEVELOPER`

#### Scenario: Operator selects the highest profile

- **WHEN** the configured profile is `MISSION_CRITICAL`
- **THEN** only releases promoted to `MISSION_CRITICAL` are acceptable

### Requirement: Profile match test

A release SHALL be considered acceptable under a configured profile when the release's profile ranks
at or above the configured profile.

#### Scenario: Release is more mature than required

- **WHEN** a release is labelled `GENERAL` and the configured profile is `EARLY_ADOPTER`
- **THEN** the release is acceptable

#### Scenario: Release is less mature than required

- **WHEN** a release is labelled `EARLY_ADOPTER` and the configured profile is `GENERAL`
- **THEN** the release is not acceptable

### Requirement: Profile of the running version

The system SHALL determine the profile of the running version by looking that version up in the
release file of the train recorded in the local update manifest, and reading the release's profile.
The recorded train SHALL be used as-is for this lookup, without applying train redirection.

If the running version is absent from that release file, the system SHALL treat the version as
`DEVELOPER` when its version string contains `CUSTOM`, `INTERNAL`, or `MASTER`, and SHALL otherwise
fail, because a version that cannot be placed on the ladder cannot be reasoned about.

#### Scenario: Running version is listed in its train

- **WHEN** the running version appears in its recorded train's release file
- **THEN** the profile recorded for that release is the running version's profile

#### Scenario: Running version is a development build

- **WHEN** the running version is absent from the release file and its version string contains
  `CUSTOM`, `INTERNAL`, or `MASTER`
- **THEN** the running version's profile is `DEVELOPER`

#### Scenario: Running version cannot be placed on the ladder

- **WHEN** the running version is absent from the release file and its version string contains none of
  those markers
- **THEN** the system reports an error rather than assuming a profile

### Requirement: Profile visibility by product type

The set of profiles offered to the operator SHALL depend on the product type. A non-enterprise system
SHALL be offered every profile at or below `GENERAL`. An enterprise system SHALL be offered every
profile at or above `GENERAL`. `GENERAL` SHALL be annotated as the default on non-enterprise systems
and as not recommended on enterprise systems.

#### Scenario: Non-enterprise system lists profiles

- **WHEN** an operator on a non-enterprise system lists profile choices
- **THEN** `DEVELOPER`, `EARLY_ADOPTER`, and `GENERAL` are offered, and `GENERAL` is annotated as the
  default

#### Scenario: Enterprise system lists profiles

- **WHEN** an operator on an enterprise system lists profile choices
- **THEN** `GENERAL` and `MISSION_CRITICAL` are offered, and `GENERAL` is annotated as not recommended

### Requirement: Profile selectability ceiling

A profile SHALL be selectable only when it ranks at or below the profile of the running version, or
when it is already the configured profile. An operator SHALL NOT be able to demand more maturity than
the version they are running has attained.

This ceiling constrains only changes to the configured profile. It SHALL NOT prevent an update from
being offered or installed.

#### Scenario: Operator raises the requirement above the running version

- **WHEN** the running version is labelled `EARLY_ADOPTER` and the operator attempts to select
  `GENERAL`
- **THEN** the selection is rejected as unavailable

#### Scenario: Configured profile already exceeds the ceiling

- **WHEN** the configured profile ranks above the running version's profile
- **THEN** that profile remains selectable, so the existing configuration is never rendered invalid

#### Scenario: Ceiling does not block updating

- **WHEN** the running version's profile is below the configured profile
- **THEN** update candidates are still evaluated and offered normally

### Requirement: Compliance reporting

The system SHALL report whether the running version satisfies the configured profile, and SHALL raise
a warning alert while it does not.

#### Scenario: Running version satisfies the configured profile

- **WHEN** the running version's profile ranks at or above the configured profile
- **THEN** the system reports the running version as matching the profile and raises no profile alert

#### Scenario: Running version falls short of the configured profile

- **WHEN** the running version's profile ranks below the configured profile
- **THEN** the system reports the running version as not matching the profile and raises a warning
  alert naming both the running and the selected profile

### Requirement: Enterprise licensing forces the highest profile

When an enterprise license is applied to a system that did not previously hold one, the system SHALL
set the configured profile to `MISSION_CRITICAL`. This assignment SHALL bypass the selectability
ceiling, and SHALL be performed without contacting the update server, because network access may be
unavailable at that moment.

#### Scenario: License applied to a system running a less mature version

- **WHEN** an enterprise license is first applied to a system whose running version is labelled below
  `MISSION_CRITICAL`
- **THEN** the configured profile becomes `MISSION_CRITICAL`, the ceiling is not enforced, and the
  system subsequently reports itself as not matching the profile until it is updated

### Requirement: Configured profile is backfilled on first use

When no profile has been configured, the ordinary read path SHALL adopt the profile of the running
version and persist it. Determining the running version's profile requires reading a release file from
the update server, so this backfill SHALL fail when the update server is unreachable. Once a profile is
stored, the ordinary read path SHALL NOT contact the update server.

A second read path SHALL therefore be available that returns the stored configuration without
backfilling, and SHALL NOT contact the update server under any circumstances. It exists for callers
that need the configuration for reasons other than selecting an update — deciding whether to schedule
the nightly check, and assigning the profile when a license is applied — neither of which may fail
because the system is offline.

#### Scenario: Profile has never been configured and the update server is reachable

- **WHEN** the update configuration is read through the ordinary path and no profile is stored
- **THEN** the running version's profile is determined, stored, and returned

#### Scenario: Profile has never been configured and the update server is unreachable

- **WHEN** the update configuration is read through the ordinary path and no profile is stored
- **THEN** the read fails, because the running version's profile cannot be determined

#### Scenario: Profile is already configured

- **WHEN** the update configuration is read through the ordinary path and a profile is stored
- **THEN** the stored profile is returned without contacting the update server

#### Scenario: Configuration is read without backfilling

- **WHEN** the update configuration is read through the path that does not backfill
- **THEN** the stored configuration is returned as it stands, including an unconfigured profile, and
  the update server is not contacted
