# Anti-Slop Design System (CAD & Workbench Edition)

A strict, disciplined design standard for Outlaw Forge frontend and 3D viewport interfaces. Prevents generic AI design tropes ("slop"), enforces high-density workbench aesthetics, and ensures deterministic, keyboard-accessible engineering controls.

---

## 1. Brief Inference & The Design Read

Before touching JSX or CSS, the agent must output a **1-line Design Read**:
> *"Reading this as: [Tool / Inspector / Modal / Viewport control] for [CAD user / 3D printing engineer], with a high-density workbench language, leaning toward dark neutral palettes, mono-spaced data readouts, and immediate feedback."*

### Anti-Default Heuristics (Strict Bans)
- ❌ **No AI-Purple/Indigo gradients**: Do not use `from-purple-600 to-indigo-600` or arbitrary neon mesh backgrounds.
- ❌ **No generic 3-card marketing grids**: Workbench UIs use sidebars, inspector panes, collapsible accordions, floating toolbars, and dockable trays.
- ❌ **No em-dashes (`—`) or en-dashes (`–`)** in user-visible UI copy, button labels, tooltips, or alerts. Use colons, hyphens (`-`), or clean sentence structure.
- ❌ **No ungrounded micro-animations**: Avoid infinite pulsing glows or spinning cards. Motion is permitted only for state transitions (collapsing panels, toast dismissals, loading spinners).

---

## 2. The Three Dials (CAD Configuration)

* **`DESIGN_VARIANCE: 3`** (Scale 1-10: 1 = Rigid Modular CAD Grid, 10 = Artsy Chaos)
  - *Outlaw Forge Rule*: Keep variance low (2-4). Workbenches thrive on predictable grids, aligned input rows, and tabular data.
* **`MOTION_INTENSITY: 2`** (Scale 1-10: 1 = Instant/Snappy, 10 = Cinematic Physics)
  - *Outlaw Forge Rule*: Transitions must be snappy ($\le 150\text{ms}$). CAD tools prioritize instantaneous response over easing theatrics.
* **`VISUAL_DENSITY: 8`** (Scale 1-10: 1 = Airy Art Gallery, 10 = Cockpit / Data-Dense)
  - *Outlaw Forge Rule*: High density (7-9). Compact controls (28-32px row heights), monospace dimensional readouts (`font-mono text-xs`), and tight padding (`p-2` / `gap-1.5`).

---

## 3. Workbench UI Palette & Styling Rules

| Element | Specification | Tailwind Classes |
| :--- | :--- | :--- |
| **Workbench Canvas** | Dark charcoal slate / neutral dark | `bg-neutral-950 text-neutral-100` |
| **Panels & Drawers** | Low-contrast surface, subtle border | `bg-neutral-900/90 border-neutral-800 backdrop-blur-md` |
| **Input Fields** | Compact, high-contrast border, mono | `bg-neutral-950 border-neutral-700 text-xs font-mono h-7 px-2 focus:border-amber-500` |
| **Primary Actions** | Industrial amber / safety orange | `bg-amber-500 hover:bg-amber-400 text-neutral-950 font-semibold text-xs h-7 px-3` |
| **Secondary Actions**| Subtle neutral outline | `bg-neutral-800 hover:bg-neutral-700 text-neutral-200 border-neutral-700 text-xs h-7 px-2.5` |
| **Active/Selected** | Amber ring or distinct highlight | `ring-1 ring-amber-500 bg-amber-500/10 text-amber-300` |
| **Critical Warnings** | Safety red / hazard striping | `bg-red-950/50 border-red-800 text-red-400 text-xs` |

---

## 4. 3D Viewport Standards (Three.js)

1. **Units & Grid**:
   - The ground plane is an exact millimeter grid (`10mm` major lines, `1mm` minor lines).
   - The printer build volume is rendered as a wireframe box matching the active printer profile (e.g., $256 \times 256 \times 256\,\text{mm}$ for Bambu Lab X1C).
2. **Coordinate Standard**:
   - Geometry calculations in FastAPI use right-handed $Z$-up.
   - Three.js scenes use standard $Y$-up. Transformations between the two must be explicitly handled by loaders and transform managers in `packages/three-tools`.
3. **Lighting & Shaders**:
   - Use studio three-point lighting with directional key light and subtle ambient occlusion.
   - Mesh rendering modes must support: Standard Matcap (neutral grey/clay), Non-Manifold Error Highlight (wireframe red), Overhang Heatmap (color gradient $>45^\circ$), and Slicing Plane Intersect.
4. **Performance & Decoupling**:
   - **Never** store active `THREE.Mesh`, `THREE.BufferGeometry`, or `THREE.Scene` instances in React component state. Store mesh IDs/pointers in React and delegate scene manipulation to refs or dedicated scene managers.

---

## 5. Anti-Slop Pre-Flight Checklist

Before marking any UI/viewport task complete:
- [ ] Are all dimensional labels explicitly annotated with `mm`, `°`, or `g` in `font-mono`?
- [ ] Is all copy free of em-dashes (`—`) and en-dashes (`–`)?
- [ ] Do controls fit a compact CAD density without large empty padding gaps?
- [ ] Are keyboard shortcuts (e.g., `G` for Grab/Move, `R` for Rotate, `S` for Scale, `Delete` for Remove) mapped and documented in tooltips?
- [ ] Does the UI handle edge cases gracefully (e.g., 0-face meshes, multi-gigabyte models, out-of-bounds printer volumes)?
