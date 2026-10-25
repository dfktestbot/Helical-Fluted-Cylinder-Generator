# Helical Fluted Cylinder

A parametric hollow cylinder with longitudinal flutes that twist along its axis. The project has two parts:

- **Fusion 360 script**: builds the real CAD solid using sketches, a loft, a bore cut and a rectangular pattern.
- **Browser preview studio**: a single-file Three.js tool for exploring parameters quickly and exporting a preview STL, with no Fusion required.

**Live preview:** `https://dfktestbot.github.io/helical-fluted-cylinder/`

---

## Repository contents

| File | Purpose |
|---|---|
| `index.html` | Browser preview studio (Three.js loaded from a CDN, no build step) |
| `Helical Fluted Cylinder.py` | Fusion 360 script with a native parameter dialog |

---

## How the shape is defined

The twist at normalized position `f` along a section (`0` to `1`) is

$$
\phi(f) = 2\pi R f + \theta \sin(2\pi C f)
$$

where `R` is the number of base revolutions, `θ` is the twist variation in radians and `C` is the number of variation cycles. The same formula and the same flute cross-section equations are used in both the script and the preview.

### Parameters

All dimensions are in millimeters.

| Parameter | Meaning |
|---|---|
| Total length | Overall length; each section is `total length / pattern count` |
| Pattern count | Number of repeated sections along Z |
| Pattern spacing offset | Subtracted from the section length to set the pattern spacing |
| Bore ID | Inner diameter of the central bore |
| Wall thickness | Nominal wall; nominal OD = ID + thickness |
| Flute height | How far each flute tip extends beyond the nominal OD |
| Flute apex angle | Included angle at the flute tip |
| Flute count | Number of flutes around the circumference |
| Base revolutions | Baseline rotation per section |
| Intervals per revolution | Number of loft profiles per revolution |
| Twist variation | Amplitude `θ` of the sinusoidal variation, in degrees |
| Twist cycles | Number of variation cycles `C` per section |
| Cut bore | Cut the central bore after the loft |

### Presets

Both tools offer the same quick-load presets. Each one sets the twist variation and twist cycles.

| Preset | Twist variation | Twist cycles |
|---|---|---|
| Bold | 35° | 1 |
| Balanced | 25° | 1 |
| Extreme | 50° | 1 |
| Ripple | 12° | 3 |

Presets are starting points. They do not guarantee that every combination of the other parameters produces valid geometry.

---

## Using the Fusion 360 script

1. In Fusion 360, open **Utilities → Add-Ins → Scripts and Add-Ins** (or press `Shift+S`).
2. Create a new Python script with the green **+** button, then replace its contents with `Helical_Fluted_Cylinder_Parameter_Dialog_Fixed7.py`.
3. Open a design and run the script.
4. Adjust the values in the dialog, choose a preset if you like, and confirm.

The script builds one section as a loft, cuts the bore, and applies a rectangular pattern when the pattern count is greater than 1.

### Built-in checks

The script stops or warns before building when it detects:

- **Overlapping flutes:** the angular span of one flute is at least the flute pitch. Reduce flute height or apex angle, or reduce flute count.
- **Twist variation too large:** the phase would stop moving forward (`θ·C ≥ R`).
- **Section-to-section rotation too large:** see the next section.
- **Heavy builds:** a warning appears above 200 loft profiles.

---

## Using the browser preview

Open the live page, or open `index.html` in any modern browser while online (it loads Three.js from a CDN).

- Controls are grouped as **Dimensions**, **Flute geometry**, **Revolutions and twist** and **Pattern**.
- Drag to orbit, scroll to zoom, right-drag to pan.
- Use the **Perspective**, **Side**, **End** and **Front** buttons, and **Fit model** to frame the whole part.
- **Show mesh edges** displays the wireframe.
- **Surface smoothing** adds interpolated rows between sections for a smoother surface. It is a display setting only and has no counterpart in Fusion.
- **Export preview STL** saves the preview mesh. It uses the same axes as a Fusion export (length along Z).

### Match Fusion loft

This option is on by default. Fusion's loft pairs each flute with the nearest flute on the next section, and the preview does the same so that it shows what Fusion will actually build. Turn it off to see the intended helix instead.

---

## Intervals per revolution and flute count

This is the most common reason a model loses its twist.

With 20 flutes the pitch is 18°. At 10 intervals per revolution each section is rotated 36°, which is exactly two pitches, so neighboring profiles look identical. The loft reads this as no rotation, and the helix collapses to a small wobble.

To keep the twist, each section-to-section rotation, including the twist variation, must stay **below half a flute pitch**. For the base twist alone that means more than `2 × flute count` intervals per revolution (more than 40 for 20 flutes). Larger twist variation needs more. Both tools warn when this condition is violated.

---

## Known limitations

- The preview is a mesh approximation. It does not reproduce Fusion's loft solver, and surfaces between profiles are interpolated with a spline.
- Fusion's exact interpolation between sections is not documented. The nearest-flute pairing model was checked against one Fusion export at 10 intervals, where it matched closely. Behavior at higher interval counts has not been compared.
- The exported preview STL is a triangulated mesh, not a CAD feature tree, and its watertightness has not been verified.
- Full runtime behavior of the script inside Fusion 360 has been tested by building models, but not across every parameter combination.

---

## Publishing the preview with GitHub Pages

1. Rename the preview file to `index.html` and push it to a public repository.
2. In the repository, go to **Settings → Pages**.
3. Under **Source**, select **Deploy from a branch**, choose `main` and `/ (root)`, and save.
4. The site is served at `https://YOUR-USERNAME.github.io/REPOSITORY-NAME/` after a minute or two.
