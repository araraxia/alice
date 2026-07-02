# Taskbar — Planning Document

## Overview

A Windows 98-style taskbar fixed to the bottom of the screen. It shows one button per open
window; the active window's button appears pressed/highlighted. Clicking a button brings that
window to the front.

---

## What We Have to Build On

- **`WindowManager`** (`window_manager.js`) — maintains `this.windows` (a Map of windowId →
  `{dragWindow, container, titleBar}`), tracks `this.activeWindowId`, fires a
  `windowActivated` CustomEvent on `document`.
- **`DragWindow`** (`drag_window.js`) — manages individual window positioning and dragging.
- Windows are registered via `windowManager.registerWindow(id, container, titleBarSelector)`.
  Some are registered at page load (static windows in `index.html`); others are registered
  dynamically when modals open.
- Windows are currently removed from the DOM by `wrapper.remove()` (graph modal) or hidden
  with `windowManager.hideWindow()` (static windows like BG control).

There is **no unregister** method on WindowManager yet. Adding one (or firing an event when
a window is hidden/removed) will be needed so the taskbar can remove buttons.

---

## Implementation Sketch

### New files
- `static/js/taskbar.js` — `Taskbar` class
- `static/css/taskbar.css` — taskbar styles

### Changes to existing files
- `window_manager.js` — fire events on register, hide, and (optionally) unregister
- `index.html` — add `<div id="taskbar">` fixed at bottom; load stylesheet + script
- `static/css/index.css` or `static/css/main.css` — `body { padding-bottom: <taskbarH>px }`
  so page content isn't hidden behind the bar

### Taskbar class responsibilities
1. Listen for `windowRegistered` / `windowHidden` / `windowRemoved` events from
   `WindowManager` and add/remove/update taskbar buttons accordingly.
2. Listen for the existing `windowActivated` event to mark the correct button as active.
3. On button click: call `windowManager.bringToFront(id)` — and also un-hide the window if
   it was hidden with `hideWindow()`.

---

## Questions for the User

**Q1 — Which windows appear in the taskbar?**
- Option A: All registered windows (including the main index window, BG control, etc.)

**Q2 — Minimize / toggle behaviour**
When the user clicks a taskbar button for the *currently active* window:
- Option B: Minimize/hide the window (toggle — click again to restore)

**Q3 — Window label**
What text should appear on each taskbar button?
- Option A: The text content of the window's `<h4>` in the title bar

**Q4 — Start button**
Should the taskbar include a "Start" button on the left (W98 style), or just window buttons?
- Yes, leave a placeholder for the start button image. Have this button replace the main index window's button.

**Q5 — Always visible**
Should the taskbar always be shown (even when no windows are open), or only appear when at
least one window is registered/visible?
- Always visible

**Q6 — Static windows**
The `index_container` (main Araxia window) and `disable-bg-container` (BG control) are
registered at page load. Should they appear in the taskbar alongside dynamically opened
windows like item search and price graphs?
- Yes, they should appear, but see question 4 about using the 'Start' button for the main index window.