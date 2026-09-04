## ADDED Requirements

### Requirement: Check for Updates

The system SHALL let the golfer check for and install a newer packaged build from the
desktop app itself.

#### Scenario: Manual check

- **WHEN** the golfer selects "Check for Updates" from the File menu
- **THEN** the app queries GitHub Releases for this repository and reports whether a
  newer version than the running one is available

#### Scenario: Already up to date

- **WHEN** no newer release is available
- **THEN** the app tells the golfer they already have the latest version

#### Scenario: Downloading an update

- **WHEN** a newer release is found
- **THEN** the app downloads and verifies the new installer in the background while
  the golfer keeps using the app

#### Scenario: Prompt to install

- **WHEN** the update finishes downloading and verifying
- **THEN** the golfer is asked whether to restart now to install it or install it later
  on next launch

#### Scenario: Update check failure

- **WHEN** the update check or download fails (e.g. no network)
- **THEN** the golfer is told the check failed rather than the app silently doing
  nothing or crashing

#### Scenario: No update checking outside the packaged app

- **WHEN** the app is running under the development launcher (not an installed,
  packaged build)
- **THEN** no update check is performed

### Requirement: About Dialog

The system SHALL let the golfer see the running app's version number from the File
menu, so they can confirm whether an update actually applied.

#### Scenario: Viewing the version

- **WHEN** the golfer selects "About" from the File menu
- **THEN** the app shows the currently running version number
