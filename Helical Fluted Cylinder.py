
import adsk.core
import adsk.fusion
import traceback
import math


# ============================================================
# USER PARAMETERS
# Dimensions are in millimeters unless stated otherwise.
# ============================================================

TOTAL_LENGTH = 100

# Rectangular pattern settings
PATTERN_COUNT = 2
PATTERN_SPACING_OFFSET_MM = 0.01

LENGTH = float(TOTAL_LENGTH / PATTERN_COUNT)
ID = 18.8
THICKNESS = 4
OD = ID + THICKNESS

FLUTE_HEIGHT = 1.5
APEX_ANGLE_DEG = 50
FLUTE_COUNT = 20

REVOLUTIONS = 1
INTERVALS_PER_REV = 10

# Nonlinear vase-style twist — default values; presets are available in the dialog.
TWIST_VARIATION = 10
TWIST_CYCLES = 1       

CUT_BORE_AFTER_LOFT = True

# Validation settings
ASK_BEFORE_BUILDING_WITH_WARNINGS = True
WARN_IF_MORE_THAN_PROFILES = 200

# Debug configuration summary:
# Creates a dedicated text-only sketch after the first flute profile sketch.
# It is never added to the loft, extrusion, cut, or pattern features.
# Hidden by default so it does not clutter the viewport or affect fit-to-view.
CREATE_DEBUG_SUMMARY_SKETCH = True
DEBUG_SUMMARY_VISIBLE = False
DEBUG_SUMMARY_TEXT_HEIGHT_MM = 2.0



# ============================================================
# UNIT CONVERSION
# ============================================================

def mm(value):
    return value / 10.0


# ============================================================
# VALIDATION
# ============================================================

def validate_parameters(ui):
    errors = []
    warnings = []

    if LENGTH <= 0:
        errors.append("LENGTH must be greater than zero.")
    if OD <= 0:
        errors.append("OD must be greater than zero.")
    if ID <= 0 or ID >= OD:
        errors.append("ID must be positive and smaller than OD.")
    if FLUTE_HEIGHT <= 0:
        errors.append("FLUTE_HEIGHT must be greater than zero.")
    if not 0 < APEX_ANGLE_DEG < 180:
        errors.append("APEX_ANGLE_DEG must be between 0 and 180.")
    if int(FLUTE_COUNT) != FLUTE_COUNT or FLUTE_COUNT < 3:
        errors.append("FLUTE_COUNT must be an integer of at least 3.")
    if int(REVOLUTIONS) != REVOLUTIONS or REVOLUTIONS < 1:
        errors.append("REVOLUTIONS must be a positive integer.")
    if int(INTERVALS_PER_REV) != INTERVALS_PER_REV or INTERVALS_PER_REV < 1:
        errors.append("INTERVALS_PER_REV must be a positive integer.")
    if int(PATTERN_COUNT) != PATTERN_COUNT or PATTERN_COUNT < 1:
        errors.append("PATTERN_COUNT must be a positive integer.")
    if int(TWIST_CYCLES) != TWIST_CYCLES or TWIST_CYCLES < 1:
        errors.append("TWIST_CYCLES must be a positive integer.")
    if TWIST_VARIATION < 0:
        errors.append("TWIST_VARIATION cannot be negative.")

    if PATTERN_COUNT > 1 and LENGTH - PATTERN_SPACING_OFFSET_MM <= 0:
        errors.append("Pattern spacing must be positive.")

    # The two flanks of each flute must not overlap the adjacent flute.
    # If their angular span is equal to or greater than one flute pitch,
    # the sketch contains intersecting edges and Fusion reports many profiles.
    if (
        OD > 0
        and FLUTE_HEIGHT > 0
        and 0 < APEX_ANGLE_DEG < 180
        and FLUTE_COUNT >= 3
    ):
        try:
            lower, tip, upper = make_flute(
                OD / 2.0,
                FLUTE_HEIGHT,
                math.radians(APEX_ANGLE_DEG),
                0.0
            )
            lower_angle = math.atan2(lower[1], lower[0])
            upper_angle = math.atan2(upper[1], upper[0])
            flute_angular_span = upper_angle - lower_angle
            flute_pitch = 2.0 * math.pi / float(FLUTE_COUNT)

            if flute_angular_span >= flute_pitch:
                errors.append(
                    "Adjacent flutes overlap with the current settings. "
                    "Reduce FLUTE_HEIGHT, reduce APEX_ANGLE_DEG, or reduce "
                    "FLUTE_COUNT. With the current dimensions, each flute "
                    "occupies {:.2f} degrees but the pitch is only {:.2f} "
                    "degrees.".format(
                        math.degrees(flute_angular_span),
                        math.degrees(flute_pitch)
                    )
                )
        except ValueError as exc:
            errors.append(str(exc))

    # Keep the angular phase moving forward at all points.
    if (
        math.radians(TWIST_VARIATION) * TWIST_CYCLES >= REVOLUTIONS
        and TWIST_VARIATION > 0
    ):
        errors.append(
            "Twist variation is too large for the base revolutions. "
            "Reduce TWIST_VARIATION or TWIST_CYCLES."
        )

    if errors:
        ui.messageBox(
            "Invalid parameters:\n\n" + "\n".join(errors),
            "Helical Fluted Cylinder"
        )
        return False

    profile_count = REVOLUTIONS * INTERVALS_PER_REV + 1
    twist_step_deg = 360.0 / INTERVALS_PER_REV
    pattern_spacing = LENGTH - PATTERN_SPACING_OFFSET_MM

    if twist_step_deg > 30:
        warnings.append(
            "Each loft interval rotates more than 30 degrees. "
            "Consider increasing INTERVALS_PER_REV."
        )

    if profile_count > WARN_IF_MORE_THAN_PROFILES:
        warnings.append(
            "The loft has more than {} profiles and may take "
            "a long time to compute.".format(WARN_IF_MORE_THAN_PROFILES)
        )

    summary = (
        "Nonlinear helical fluted cylinder\n\n"
        "Length: {:.3f} mm\n"
        "Nominal OD: {:.3f} mm\n"
        "Bore ID: {:.3f} mm\n"
        "Flute-tip diameter: {:.3f} mm\n"
        "Flutes: {}\n"
        "Base revolutions: {}\n"
        "Twist variation: {:.3f} degrees\n"
        "Twist cycles: {}\n"
        "Intervals per revolution: {}\n"
        "Loft profiles: {}\n"
        "Pattern count: {}\n"
        "Pattern spacing: {:.3f} mm"
    ).format(
        LENGTH, OD, ID, OD + 2 * FLUTE_HEIGHT,
        FLUTE_COUNT, REVOLUTIONS, TWIST_VARIATION,
        TWIST_CYCLES, INTERVALS_PER_REV,
        profile_count, PATTERN_COUNT, pattern_spacing
    )

    if warnings:
        summary += "\n\nWarnings:\n- " + "\n- ".join(warnings)

    if warnings and ASK_BEFORE_BUILDING_WITH_WARNINGS:
        result = ui.messageBox(
            summary + "\n\nContinue building?",
            "Helical Fluted Cylinder",
            adsk.core.MessageBoxButtonTypes.YesNoButtonType
        )
        return result == adsk.core.DialogResults.DialogYes

    ui.messageBox(summary, "Helical Fluted Cylinder")
    return True


# ============================================================
# NONLINEAR TWIST
# Preserves total rotation at both ends.
# ============================================================

def calculate_phase(fraction):
    variation_rad = math.radians(TWIST_VARIATION)

    return (
        2.0 * math.pi * REVOLUTIONS * fraction
        + variation_rad
        * math.sin(2.0 * math.pi * TWIST_CYCLES * fraction)
    )


# ============================================================
# FLUTE CROSS-SECTION GEOMETRY
# ============================================================

def make_flute(radius, height, apex, angle):
    tip_radius = radius + height
    half = apex / 2.0

    discriminant = (
        radius ** 2
        - tip_radius ** 2 * math.sin(half) ** 2
    )

    if discriminant <= 0:
        raise ValueError(
            "Flute geometry does not intersect the nominal OD. "
            "Reduce FLUTE_HEIGHT or adjust APEX_ANGLE_DEG."
        )

    d = (
        tip_radius * math.cos(half)
        - math.sqrt(discriminant)
    )

    x = tip_radius - d * math.cos(half)
    y = d * math.sin(half)

    c = math.cos(angle)
    s = math.sin(angle)

    def rotate(px, py):
        return (
            px * c - py * s,
            px * s + py * c
        )

    lower = rotate(x, -y)
    tip = rotate(tip_radius, 0.0)
    upper = rotate(x, y)

    return lower, tip, upper


# ============================================================
# CREATE ONE CLOSED PROFILE AT A GIVEN Z POSITION
# ============================================================

def make_section(
    component, z_mm, phase, radius, height, apex, flute_count
):
    planes = component.constructionPlanes
    plane_input = planes.createInput()

    plane_input.setByOffset(
        component.xYConstructionPlane,
        adsk.core.ValueInput.createByReal(mm(z_mm))
    )

    plane = planes.add(plane_input)
    sketch = component.sketches.add(plane)
    sketch.name = "Flute Section Z {:.3f} mm".format(z_mm)

    lines = sketch.sketchCurves.sketchLines
    arcs = sketch.sketchCurves.sketchArcs

    pitch = 2.0 * math.pi / flute_count
    apex_rad = math.radians(apex)

    flute_points = []

    for i in range(flute_count):
        angle = phase + i * pitch
        lower, tip, upper = make_flute(
            radius, height, apex_rad, angle
        )
        flute_points.append((lower, tip, upper))

    for i in range(flute_count):
        lower, tip, upper = flute_points[i]
        next_lower = flute_points[(i + 1) % flute_count][0]

        lines.addByTwoPoints(
            adsk.core.Point3D.create(
                mm(lower[0]), mm(lower[1]), 0
            ),
            adsk.core.Point3D.create(
                mm(tip[0]), mm(tip[1]), 0
            )
        )

        lines.addByTwoPoints(
            adsk.core.Point3D.create(
                mm(tip[0]), mm(tip[1]), 0
            ),
            adsk.core.Point3D.create(
                mm(upper[0]), mm(upper[1]), 0
            )
        )

        upper_angle = math.atan2(upper[1], upper[0])
        next_lower_angle = math.atan2(
            next_lower[1], next_lower[0]
        )

        while next_lower_angle <= upper_angle:
            next_lower_angle += 2.0 * math.pi

        mid_angle = (upper_angle + next_lower_angle) / 2.0

        mid_point = adsk.core.Point3D.create(
            mm(radius * math.cos(mid_angle)),
            mm(radius * math.sin(mid_angle)),
            0
        )

        arcs.addByThreePoints(
            adsk.core.Point3D.create(
                mm(upper[0]), mm(upper[1]), 0
            ),
            mid_point,
            adsk.core.Point3D.create(
                mm(next_lower[0]), mm(next_lower[1]), 0
            )
        )

    if sketch.profiles.count != 1:
        raise RuntimeError(
            "Expected one closed profile at Z = {:.3f} mm, "
            "but found {}.".format(z_mm, sketch.profiles.count)
        )

    return sketch.profiles.item(0)


# ============================================================
# DEBUG CONFIGURATION SUMMARY SKETCH
# This sketch is independent of all model-generating features.
# It is the very first sketch created by the script, before any
# flute profile sketch, and is never passed to the loft, extrusion,
# cut, or pattern operations.
# ============================================================

def create_debug_summary_sketch(component):
    if not CREATE_DEBUG_SUMMARY_SKETCH:
        return None

    summary_sketch = component.sketches.add(
        component.xYConstructionPlane
    )
    summary_sketch.name = "DEBUG - Configuration Summary"

    profile_count = int(REVOLUTIONS * INTERVALS_PER_REV) + 1
    spacing_mm = LENGTH - PATTERN_SPACING_OFFSET_MM
    expected_patterned_span = (
        LENGTH + (PATTERN_COUNT - 1) * spacing_mm
        if PATTERN_COUNT > 1 else LENGTH
    )
    flute_span_deg = None
    flute_pitch_deg = 360.0 / float(FLUTE_COUNT) if FLUTE_COUNT else 0.0

    try:
        lower, tip, upper = make_flute(
            OD / 2.0,
            FLUTE_HEIGHT,
            math.radians(APEX_ANGLE_DEG),
            0.0
        )
        lower_angle = math.atan2(lower[1], lower[0])
        upper_angle = math.atan2(upper[1], upper[0])
        flute_span_deg = math.degrees(upper_angle - lower_angle)
    except Exception:
        pass

    if flute_span_deg is None:
        overlap_status = "Could not calculate"
        span_text = "N/A"
    else:
        overlap_status = (
            "PASS - no angular overlap"
            if flute_span_deg < flute_pitch_deg
            else "FAIL - flute span meets/exceeds pitch"
        )
        span_text = "{:.3f} deg".format(flute_span_deg)

    lines = [
        "HELICAL FLUTED CYLINDER",
        "DEBUG CONFIGURATION SUMMARY",
        "",
        "DIMENSIONS (mm)",
        "Requested total length: {:.3f}".format(TOTAL_LENGTH),
        "Section length: {:.3f}".format(LENGTH),
        "Expected patterned span: {:.3f}".format(expected_patterned_span),
        "Pattern spacing offset: {:.3f}".format(PATTERN_SPACING_OFFSET_MM),
        "Actual pattern spacing: {:.3f}".format(spacing_mm),
        "Bore ID: {:.3f}".format(ID),
        "Wall thickness: {:.3f}".format(THICKNESS),
        "Nominal OD: {:.3f}".format(OD),
        "Flute-tip diameter: {:.3f}".format(OD + 2.0 * FLUTE_HEIGHT),
        "",
        "FLUTE GEOMETRY",
        "Flute height: {:.3f} mm".format(FLUTE_HEIGHT),
        "Apex angle: {:.3f} deg".format(APEX_ANGLE_DEG),
        "Flute count: {}".format(FLUTE_COUNT),
        "Angular pitch: {:.3f} deg".format(flute_pitch_deg),
        "Calculated flute span: {}".format(span_text),
        "Overlap check: {}".format(overlap_status),
        "",
        "TWIST / LOFT",
        "Base revolutions: {}".format(REVOLUTIONS),
        "Twist variation: {:.3f} deg".format(TWIST_VARIATION),
        "Twist cycles: {}".format(TWIST_CYCLES),
        "Intervals per revolution: {}".format(INTERVALS_PER_REV),
        "Loft profile count: {}".format(profile_count),
        "",
        "FEATURE OPTIONS",
        "Cut central bore: {}".format(CUT_BORE_AFTER_LOFT),
        "Pattern count: {}".format(PATTERN_COUNT),
        "Pattern feature created: {}".format(PATTERN_COUNT > 1),
    ]
    summary_text = "\n".join(lines)

    texts = summary_sketch.sketchTexts
    text_height = mm(DEBUG_SUMMARY_TEXT_HEIGHT_MM)
    text_input = None

    # Fusion 360 API versions from November 2025 onward provide createInput3.
    # Fall back to createInput2 for older Fusion builds.
    if hasattr(texts, "createInput3"):
        text_input = texts.createInput3(
            "'" + summary_text + "'",
            adsk.core.ValueInput.createByReal(text_height)
        )
    elif hasattr(texts, "createInput2"):
        text_input = texts.createInput2(summary_text, text_height)
    else:
        summary_sketch.deleteMe()
        raise RuntimeError(
            "This Fusion 360 version does not expose a supported sketch-text input API."
        )

    # Put the debug text beside the first cross-section, not over the part.
    # Coordinates and text height are in Fusion's internal centimeter units.
    offset_mm = OD / 2.0 + FLUTE_HEIGHT + 10.0
    text_x = mm(offset_mm)
    text_y = mm(offset_mm)
    box_width = mm(125.0)
    box_height = mm(max(45.0, len(lines) * DEBUG_SUMMARY_TEXT_HEIGHT_MM * 1.5))

    text_input.setAsMultiLine(
        adsk.core.Point3D.create(text_x, text_y, 0),
        adsk.core.Point3D.create(text_x + box_width, text_y - box_height, 0),
        adsk.core.HorizontalAlignments.LeftHorizontalAlignment,
        adsk.core.VerticalAlignments.TopVerticalAlignment,
        0
    )

    created_text = texts.add(text_input)
    if created_text is None:
        summary_sketch.deleteMe()
        raise RuntimeError("Fusion could not create the debug configuration text.")

    summary_sketch.isVisible = DEBUG_SUMMARY_VISIBLE
    return summary_sketch


# ============================================================
# CREATE NONLINEAR HELICAL LOFT
# ============================================================

def create_fluted_loft(component):
    lofts = component.features.loftFeatures

    loft_input = lofts.createInput(
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    loft_input.isSolid = True

    total_intervals = int(REVOLUTIONS * INTERVALS_PER_REV)

    # Create the isolated debug sketch first, as the initial sketch of the whole
    # process. It is not added to loft_input or any later feature.
    if CREATE_DEBUG_SUMMARY_SKETCH:
        create_debug_summary_sketch(component)

    for i in range(total_intervals + 1):
        fraction = i / float(total_intervals)
        z_mm = LENGTH * fraction

        # Nonlinear twist replaces the original linear phase.
        phase = calculate_phase(fraction)

        profile = make_section(
            component,
            z_mm,
            phase,
            OD / 2.0,
            FLUTE_HEIGHT,
            APEX_ANGLE_DEG,
            int(FLUTE_COUNT)
        )

        loft_input.loftSections.add(profile)

    loft = lofts.add(loft_input)

    if loft is None or loft.bodies.count == 0:
        raise RuntimeError("The loft failed to create a solid body.")

    return loft


# ============================================================
# CUT CENTRAL BORE
# ============================================================

def cut_central_bore(component, body):
    sketch = component.sketches.add(
        component.xYConstructionPlane
    )
    sketch.name = "Central Bore Sketch"

    sketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(0, 0, 0),
        mm(ID / 2.0)
    )

    if sketch.profiles.count != 1:
        raise RuntimeError(
            "Could not create a single central bore profile."
        )

    profile = sketch.profiles.item(0)
    extrudes = component.features.extrudeFeatures

    extrude_input = extrudes.createInput(
        profile,
        adsk.fusion.FeatureOperations.CutFeatureOperation
    )

    extrude_input.setDistanceExtent(
        False,
        adsk.core.ValueInput.createByReal(mm(LENGTH))
    )

    # Explicitly limit the cut to the original loft body.
    extrude_input.participantBodies = [body]

    cut_feature = extrudes.add(extrude_input)

    if cut_feature is None:
        raise RuntimeError("The central bore cut failed.")

    return cut_feature


# ============================================================
# RECTANGULAR PATTERN
# Repeats the finished body along the central Z axis.
# ============================================================

def pattern_fluted_body(component, body, count, section_length_mm):
    if int(count) != count or count < 1:
        raise ValueError("Pattern count must be a positive integer.")

    if count == 1:
        return None

    spacing_mm = section_length_mm - PATTERN_SPACING_OFFSET_MM

    if spacing_mm <= 0:
        raise ValueError("Pattern spacing must be greater than zero.")

    entities = adsk.core.ObjectCollection.create()
    entities.add(body)

    patterns = component.features.rectangularPatternFeatures

    quantity_one = adsk.core.ValueInput.createByString(str(int(count)))
    distance_one = adsk.core.ValueInput.createByReal(mm(spacing_mm))

    pattern_input = patterns.createInput(
        entities,
        component.zConstructionAxis,
        quantity_one,
        distance_one,
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType
    )

    pattern_input.isSymmetricInDirectionOne = False

    # Disable the second pattern direction.
    pattern_input.quantityTwo = adsk.core.ValueInput.createByReal(1)

    # One direction only; do not define direction two.
    pattern = patterns.add(pattern_input)

    if pattern is None:
        raise RuntimeError("The rectangular pattern could not be created.")

    return pattern


# ============================================================
# MAIN ENTRY POINT
# ============================================================

# ============================================================
# NATIVE FUSION PARAMETER DIALOG
# ============================================================

_PRESETS = {
    "Custom / Current Values": None,
    "Bold": (35.0, 1),
    "Balanced": (25.0, 1),
    "Extreme": (50.0, 1),
    "Ripple": (12.0, 3),
}

_handlers = []


def _add_string_input(inputs, input_id, name, value):
    return inputs.addStringValueInput(input_id, name, str(value))


def _set_input_text(inputs, input_id, value):
    item = inputs.itemById(input_id)
    if item:
        item.value = str(value)


def _number(inputs, input_id, cast=float):
    raw = inputs.itemById(input_id).value.strip()
    value = cast(raw)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("{} must be a finite number.".format(input_id))
    return value


class _ParameterDialogCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            cmd.isExecutedWhenPreEmpted = False
            inputs = cmd.commandInputs

            preset = inputs.addDropDownCommandInput(
                "preset", "Quick-load preset",
                adsk.core.DropDownStyles.TextListDropDownStyle
            )
            for i, name in enumerate(_PRESETS.keys()):
                preset.listItems.add(name, i == 0)

            # Dimensions and geometry
            _add_string_input(inputs, "total_length", "Total length (mm)", TOTAL_LENGTH)
            _add_string_input(inputs, "pattern_count", "Pattern count", PATTERN_COUNT)
            _add_string_input(inputs, "spacing_offset", "Pattern spacing offset (mm)", PATTERN_SPACING_OFFSET_MM)
            _add_string_input(inputs, "id", "Bore inner diameter ID (mm)", ID)
            _add_string_input(inputs, "thickness", "Wall thickness (mm)", THICKNESS)
            _add_string_input(inputs, "flute_height", "Flute height (mm)", FLUTE_HEIGHT)
            _add_string_input(inputs, "apex_angle", "Flute apex angle (degrees)", APEX_ANGLE_DEG)
            _add_string_input(inputs, "flute_count", "Flute count", FLUTE_COUNT)

            # Helix and nonlinear twist
            _add_string_input(inputs, "revolutions", "Base revolutions per section", REVOLUTIONS)
            _add_string_input(inputs, "intervals", "Intervals per revolution", INTERVALS_PER_REV)
            _add_string_input(inputs, "twist_variation", "Twist variation (degrees)", TWIST_VARIATION)
            _add_string_input(inputs, "twist_cycles", "Twist cycles", TWIST_CYCLES)

            inputs.addBoolValueInput("cut_bore", "Cut central bore after loft", True, "", CUT_BORE_AFTER_LOFT)
            inputs.addBoolValueInput("confirm_warnings", "Ask before building with warnings", True, "", ASK_BEFORE_BUILDING_WITH_WARNINGS)
            _add_string_input(inputs, "profile_warning", "Warn above this profile count", WARN_IF_MORE_THAN_PROFILES)

            changed = _ParameterDialogInputChangedHandler()
            cmd.inputChanged.add(changed)
            _handlers.append(changed)

            execute = _ParameterDialogExecuteHandler()
            cmd.execute.add(execute)
            _handlers.append(execute)

            # End the Fusion script when this command/dialog is closed.
            destroyed = _ParameterDialogDestroyHandler()
            cmd.destroy.add(destroyed)
            _handlers.append(destroyed)
        except:
            app = adsk.core.Application.get()
            app.userInterface.messageBox(
                "Could not create parameter dialog:\n\n{}".format(traceback.format_exc()),
                "Helical Fluted Cylinder"
            )


class _ParameterDialogInputChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        try:
            changed_input = args.input
            if changed_input.id != "preset":
                return
            selected = changed_input.selectedItem.name
            values = _PRESETS.get(selected)
            if values is None:
                return
            _set_input_text(args.inputs, "twist_variation", values[0])
            _set_input_text(args.inputs, "twist_cycles", values[1])
        except:
            # Do not interrupt dialog interaction for a preset-refresh issue.
            pass


class _ParameterDialogDestroyHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        # The script was kept alive so its event handlers could service the
        # native command. Once the command is destroyed, explicitly end it.
        try:
            adsk.terminate()
        except:
            pass


class _ParameterDialogExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        global TOTAL_LENGTH, PATTERN_COUNT, PATTERN_SPACING_OFFSET_MM
        global LENGTH, ID, THICKNESS, OD, FLUTE_HEIGHT, APEX_ANGLE_DEG, FLUTE_COUNT
        global REVOLUTIONS, INTERVALS_PER_REV, TWIST_VARIATION, TWIST_CYCLES
        global CUT_BORE_AFTER_LOFT, ASK_BEFORE_BUILDING_WITH_WARNINGS
        global WARN_IF_MORE_THAN_PROFILES

        app = adsk.core.Application.get()
        ui = app.userInterface
        try:
            inputs = args.command.commandInputs

            TOTAL_LENGTH = _number(inputs, "total_length")
            PATTERN_COUNT = _number(inputs, "pattern_count", int)
            PATTERN_SPACING_OFFSET_MM = _number(inputs, "spacing_offset")
            ID = _number(inputs, "id")
            THICKNESS = _number(inputs, "thickness")
            FLUTE_HEIGHT = _number(inputs, "flute_height")
            APEX_ANGLE_DEG = _number(inputs, "apex_angle")
            FLUTE_COUNT = _number(inputs, "flute_count", int)
            REVOLUTIONS = _number(inputs, "revolutions", int)
            INTERVALS_PER_REV = _number(inputs, "intervals", int)
            TWIST_VARIATION = _number(inputs, "twist_variation")
            TWIST_CYCLES = _number(inputs, "twist_cycles", int)
            CUT_BORE_AFTER_LOFT = inputs.itemById("cut_bore").value
            ASK_BEFORE_BUILDING_WITH_WARNINGS = inputs.itemById("confirm_warnings").value
            WARN_IF_MORE_THAN_PROFILES = _number(inputs, "profile_warning", int)

            LENGTH = float(TOTAL_LENGTH) / float(PATTERN_COUNT) if PATTERN_COUNT else 0
            OD = ID + THICKNESS

            if not validate_parameters(ui):
                return

            design = adsk.fusion.Design.cast(app.activeProduct)
            if design is None:
                ui.messageBox("Open a Fusion 360 design before running this script.")
                return

            component = design.rootComponent

            loft = create_fluted_loft(component)
            body = loft.bodies.item(0)
            body.name = "Nonlinear Helical Fluted Cylinder"

            if CUT_BORE_AFTER_LOFT:
                cut_central_bore(component, body)

            # Only create a rectangular pattern when multiple sections are requested.
            # With a count of 1, keep the original body and avoid a redundant pattern feature.
            if PATTERN_COUNT > 1:
                pattern_fluted_body(component, body, PATTERN_COUNT, LENGTH)

            design.computeAll()

            spacing_mm = LENGTH - PATTERN_SPACING_OFFSET_MM
            ui.messageBox(
                "Nonlinear helical fluted cylinder created successfully.\n\n"
                "Total length: {:.3f} mm\n"
                "Section length: {:.3f} mm\n"
                "Nominal OD: {:.3f} mm\n"
                "Bore ID: {:.3f} mm\n"
                "Flutes: {}\n"
                "Base revolutions: {}\n"
                "Twist variation: {:.3f} degrees\n"
                "Twist cycles: {}\n"
                "Loft profiles per section: {}\n\n"
                "Pattern count: {}\n"
                "Pattern spacing: {:.3f} mm".format(
                    TOTAL_LENGTH, LENGTH, OD, ID, FLUTE_COUNT, REVOLUTIONS,
                    TWIST_VARIATION, TWIST_CYCLES,
                    int(REVOLUTIONS * INTERVALS_PER_REV) + 1,
                    PATTERN_COUNT, spacing_mm
                ),
                "Helical Fluted Cylinder"
            )
        except:
            ui.messageBox(
                "Failed:\n\n{}".format(traceback.format_exc()),
                "Helical Fluted Cylinder"
            )


def run(context):
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if design is None:
            ui.messageBox("Open a Fusion 360 design before running this script.")
            return

        command_id = "HelicalFlutedCylinderParameterDialog"
        command_def = ui.commandDefinitions.itemById(command_id)
        if command_def:
            command_def.deleteMe()
        command_def = ui.commandDefinitions.addButtonDefinition(
            command_id,
            "Helical Fluted Cylinder",
            "Configure parameters and build a nonlinear helical fluted cylinder."
        )
        created = _ParameterDialogCreatedHandler()
        command_def.commandCreated.add(created)
        _handlers.append(created)
        # Keep the script alive while Fusion's native dialog is open. The
        # command destroy handler calls adsk.terminate() when it closes.
        adsk.autoTerminate(False)
        command_def.execute()
    except:
        app = adsk.core.Application.get()
        app.userInterface.messageBox(
            "Failed to open parameter dialog:\n\n{}".format(traceback.format_exc()),
            "Helical Fluted Cylinder"
        )
