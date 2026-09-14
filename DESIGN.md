# CleanMac — Design Direction

Status: direction agreed (Liquid Glass). Tokens below are committed; exact
radii/spacing remain open until the build phase.

## Visual authority

**Liquid Glass** — Apple's material language introduced in macOS 26 (Tahoe) and
refined in macOS 27. Depth comes from real material behaviour: translucent
chrome, content refraction, specular edges. Not from flat fills or drop shadows.

## Surface register

Product, not brand. This is a utility that performs destructive work; the design
must read as calm, precise, and Apple-native. No marketing flourish inside the
window.

## Structure

- Menu bar: template icon (auto light/dark), popover = `.menuBarExtraStyle(.window)`
  — state first, two actions, nothing else.
- Window: `NavigationSplitView` sidebar (always visible) + detail pane.
- Destructive work always ends on one plan screen with the full path list and a
  single gate.

## Committed rules

1. **Glass only over content.** Every glass surface floats over a wallpaper or
   another surface; glass on flat white is banned.
2. **Text legibility wins.** Content sits on a lighter/darker content sheet so
   contrast never depends on the wallpaper behind chrome.
3. **One gate.** Full path list, one confirm. No per-item prompts.
4. **Selection ≠ focus.** Distinct treatments; both readable in monochrome.
5. **Light and dark are peers.** Dark leans on a specular edge, not a bright fill.
6. **Template menu-bar icon.** Adapts automatically; never a hard-coded colour.
7. **Native controls only.** No custom-drawn lookalikes of system controls.

## Implementation notes (Apple guidance)

- Liquid Glass window chrome requires an `NSWindowController` with
  `.fullSizeContentView`. A SwiftUI `Window` scene cannot render it.
- Sidebar: `.listStyle(.sidebar)` + `scrollEdgeEffectStyle(.soft, for: .all)`
  (macOS 26+; wrap in `#available`).
- Detail: `Form` + `.formStyle(.grouped)` + `.scrollContentBackground(.hidden)`
  + `.contentMargins(.top, 8, for: .scrollContent)`.
- `@State` is a macro in SDK 27 — use Apple's migration reference, not memory.

## Open (do not invent)

- Accent hue and iconography set.
- Corner radii and spacing scale (indicative in the comps).
- Wallpaper: never shipped; only the user's desktop shows through.

Reference artifacts: `tasks/wireframes.html` (structure), `tasks/comps.html`
(visual direction).
