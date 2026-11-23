## ADDED Requirements

### Requirement: Swing plane reference lines show image-plane angles
The system SHALL show each swing-plane reference line's angle relative to the image's horizontal axis, measured in the displayed camera image rather than the overlay container. The angle SHALL be shown to one decimal place, update as the line is adjusted, and be identified as a 2D image measurement rather than a 3D swing-plane measurement.

#### Scenario: Line angle accounts for camera image dimensions
- **WHEN** a reference line is displayed over a camera image whose width and height differ
- **THEN** its angle is calculated using the line's pixel-space direction in that image, not its normalized overlay-box coordinates

#### Scenario: Angle readout follows line edits
- **WHEN** the operator adds or adjusts a reference line
- **THEN** its on-video label and line list show the updated angle to one decimal place

#### Scenario: Measurement limitation is clear
- **WHEN** the reference-line angle controls are shown
- **THEN** the interface identifies the values as measured in the camera's 2D image and not as true 3D angles

### Requirement: Intersecting reference lines show their angle difference
The system SHALL automatically show the acute angle at every in-frame intersection between two visible reference-line segments in the same camera view. The annotation SHALL identify both lines and update when either line is adjusted. The system SHALL NOT require the operator to select a comparison pair.

#### Scenario: Visible segments intersect in the image
- **WHEN** two visible reference-line segments cross within the camera image
- **THEN** the system shows their acute angle at the crossing and identifies both lines

#### Scenario: Segments do not cross within their endpoints
- **WHEN** two reference-line extensions would cross but their visible finite segments do not
- **THEN** the system does not show a comparison angle for that pair

#### Scenario: Several visible pairs intersect
- **WHEN** more than one pair of visible reference-line segments intersects in the image
- **THEN** the system shows an angle annotation for every intersecting pair and identifies each pair's lines

#### Scenario: Comparison stays within a camera view
- **WHEN** reference-line intersections are measured in a camera view
- **THEN** only pairs of lines belonging to that same camera view are compared

### Requirement: Reference-line controls support direct selection and angle snapping
The system SHALL present reference-line controls in a panel below the associated video, with an identifiable label for each line. The operator SHALL be able to select a line by clicking the line or its corresponding panel entry. During a Shift-drag adjustment, the system SHALL snap the line's image-plane angle to 5-degree increments, including level and plumb.

#### Scenario: Select a line from the video
- **WHEN** the operator clicks a reference line
- **THEN** that line becomes selected and its corresponding panel entry is identified as selected

#### Scenario: Select a line from the panel
- **WHEN** the operator clicks a line's panel entry
- **THEN** that line becomes selected and its editing handles are shown

#### Scenario: Shift-drag snaps the line angle
- **WHEN** the operator holds Shift while dragging a line endpoint
- **THEN** the adjusted line angle snaps to 5-degree increments, including 0 degrees and 90 degrees

### Requirement: Angle labels can be positioned and shown independently
The system SHALL let the operator independently show or hide each line-angle label and each crossing-angle annotation. The operator SHALL be able to drag either kind of label to a new position on the video image. Labels SHALL remain visible and be staggered automatically until the operator changes their position or visibility, and those per-camera choices SHALL persist across sessions.

#### Scenario: Hide and show one line-angle label
- **WHEN** the operator changes the visibility control for one line-angle label
- **THEN** only that line's angle label is hidden or shown, while the reference line remains visible

#### Scenario: Hide and show one crossing-angle annotation
- **WHEN** the operator changes the visibility control for one intersecting pair's angle annotation
- **THEN** only that pair's angle arc and label are hidden or shown

#### Scenario: Move an angle label
- **WHEN** the operator drags a line-angle label or crossing-angle label on the video
- **THEN** that label moves without moving its reference line or changing the measured angle

#### Scenario: Restore automatically placed labels
- **WHEN** the operator resets angle-label positions
- **THEN** all moved labels return to automatic positions without changing their visibility settings

#### Scenario: Angle-label settings persist per camera
- **WHEN** the operator hides or moves labels and later reopens the same camera view
- **THEN** that camera's label visibility and manually chosen positions are restored
