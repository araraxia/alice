# Draggable Window System

## Overview

The site's window management system provides a desktop-like experience in the browser, with draggable, focus-managing windows that can be opened, closed, and layered.

## Architecture

### Core Components

1. **WindowManager** (`window_manager.js`) - Central state manager
2. **OpenWindow** (`open_window.js`) - Individual window controller  
3. **WindowInitializer** (`window_initializer.js`) - Setup helper
4. **DragWindow** (`drag_window.js`) - Drag functionality

### Window Lifecycle

```
Initialize → Create → Load Content → Show → Interact → Hide/Destroy
```

## WindowManager Class

The heart of the system - manages all windows globally.

### Key Features

```javascript
class WindowManager {
  constructor() {
    this.windows = new Map();
    this.zIndexCounter = 1000;
    this.activeWindow = null;
  }
  
  // Auto-discovers windows marked with .draggable-window
  discoverWindows();
  
  // Creates and registers a new window
  createWindow(config);
  
  // Manages z-index layering
  bringToFront(windowElement);
  
  // Centers window on screen
  centerWindow(windowId);
}
```

### Z-Index Management

Automatically handles window layering:

```javascript
bringToFront(element) {
  element.style.zIndex = ++this.zIndexCounter;
  this.activeWindow = element;
  
  // Dispatch custom event
  document.dispatchEvent(new CustomEvent('windowActivated', {
    detail: { windowId: element.id, zIndex: this.zIndexCounter }
  }));
}
```

## OpenWindow Class

Handles individual window operations:

```javascript
class OpenWindow {
  constructor(windowManager, endpoint, containerClass) {
    this.windowManager = windowManager;
    this.endpoint = endpoint;
    this.container = null;
  }
  
  async open() {
    // Fetch HTML content
    const response = await fetch(this.endpoint);
    const data = await response.json();
    
    // Create window element
    this.createWindow(data.html);
    
    // Register with manager
    this.windowManager.registerWindow(this.container);
  }
  
  close() {
    this.container.remove();
    this.windowManager.unregisterWindow(this.container);
  }
}
```

## WindowInitializer Helper

Simplifies window setup:

```javascript
const loginWindow = new WindowInitializer(
  windowManager,
  'loginContainer',      // Global instance name
  'login-window',        // Window ID
  'login-container',     // Container class
  'index-login-btn',     // Trigger button
  'login-title-bar',     // Drag handle
  'close-login-button',  // Close button
  '/auth/login_modal',   // Content endpoint
  true                   // Auto-center
);
```

This automatically:
- Creates the OpenWindow instance
- Stores it globally
- Sets up event listeners
- Configures drag and close functionality

## Drag Functionality

### Implementation

Uses mouse events for dragging:

```javascript
titleBar.addEventListener('mousedown', (e) => {
  isDragging = true;
  
  // Calculate offset from mouse to window corner
  offsetX = e.clientX - window.offsetLeft;
  offsetY = e.clientY - window.offsetTop;
  
  // Bring to front
  windowManager.bringToFront(window);
});

document.addEventListener('mousemove', (e) => {
  if (!isDragging) return;
  
  // Update position
  window.style.left = (e.clientX - offsetX) + 'px';
  window.style.top = (e.clientY - offsetY) + 'px';
});
```

### Constraints

Windows are constrained to viewport bounds:

```javascript
// Prevent dragging off-screen
const maxX = window.innerWidth - windowWidth;
const maxY = window.innerHeight - windowHeight;

newX = Math.max(0, Math.min(newX, maxX));
newY = Math.max(0, Math.min(newY, maxY));
```

## Window Sizing

### Predefined Classes

```css
.small-window { width: 300px; height: 200px; }
.medium-window { width: 500px; height: 400px; }
.large-window { width: 800px; height: 600px; }
```

### Dynamic Sizing

Windows can adjust based on content:

```javascript
window.style.height = 'auto';
window.style.maxHeight = '80vh';
```

## State Management

### Window States

- **Hidden** - `display: none`
- **Visible** - `display: block`
- **Active** - Highest z-index, receives input focus
- **Inactive** - Lower z-index, visual feedback

### Global State Tracking

```javascript
window.openStates = {
  'login-window': false,
  'osrs-window': true,
  'showcase-window': false
};
```

Prevents duplicate windows and tracks state.

## Event System

### Custom Events

The system dispatches events for coordination:

```javascript
// Window activated
document.addEventListener('windowActivated', (e) => {
  console.log(`Window ${e.detail.windowId} activated`);
});

// Window manager ready
document.addEventListener('windowManagerReady', () => {
  initializeUI();
});
```

### Keyboard Shortcuts

Escape key closes top window:

```javascript
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && escapeWindowStack.length > 0) {
    const topWindow = escapeWindowStack.pop();
    topWindow.close();
  }
});
```

## Content Loading

### Dynamic HTML Injection

Windows load content from Flask endpoints:

```python
@blueprint.route('/modal', methods=['GET'])
def modal():
    html = render_template('component.html')
    return jsonify({'status': 'success', 'html': html})
```

### Script Execution

Injected content can include scripts:

```html
<div id="dynamic-content">
  <!-- Content here -->
</div>
<script>
  // Initialize component
  setupComponent();
</script>
```

## Memory Management

### Window Cleanup

Proper cleanup prevents memory leaks:

```javascript
close() {
  // Remove event listeners
  this.removeEventListeners();
  
  // Remove from DOM
  this.container.remove();
  
  // Unregister from manager
  this.windowManager.unregisterWindow(this.container);
  
  // Clear references
  this.container = null;
}
```

### Auto-Discovery Optimization

Initial window discovery runs once at page load:

```javascript
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    this.discoverWindows();
  });
} else {
  this.discoverWindows();
}
```

## Usage Example

### Creating a New Window Type

1. **Create Flask endpoint**:

```python
@app.route('/my-feature')
def my_feature():
    html = render_template('my_feature.html')
    return jsonify({'status': 'success', 'html': html})
```

2. **Add button to trigger**:

```html
<button id="my-feature-btn" class="w98-button">
  My Feature
</button>
```

3. **Initialize window**:

```javascript
const myFeature = new WindowInitializer(
  windowManager,
  'myFeatureContainer',
  'my-feature-window',
  'my-feature-container',
  'my-feature-btn',
  'my-feature-title-bar',
  'close-my-feature-button',
  '/my-feature',
  true
);
```

Done! The window system handles the rest.

## Browser Compatibility

Tested and working on:
- Chrome 90+
- Firefox 88+
- Edge 90+
- Safari 14+

Uses vanilla JavaScript - no framework dependencies.

## Performance Considerations

### Optimization Strategies

1. **Event delegation** - Mouse events on document, not per-window
2. **Lazy loading** - Content fetched only when opened
3. **Debouncing** - Drag updates throttled
4. **Memory cleanup** - Proper disposal when closed

### Bottlenecks Avoided

- ❌ Creating windows ahead of time
- ❌ Keeping closed windows in DOM
- ❌ Not cleaning up event listeners
- ❌ Excessive z-index calculation

## Accessibility

Current limitations:
- Keyboard navigation needs improvement
- Screen reader support not implemented
- Focus management could be enhanced

Future work:
- [ ] Tab navigation between windows
- [ ] Keyboard shortcuts for window operations
- [ ] ARIA labels and roles
- [ ] Focus trap within modal windows

## Related Files

- `static/js/window_manager.js` - Core manager
- `static/js/open_window.js` - Window controller
- `static/js/window_initializer.js` - Setup helper
- `static/js/drag_window.js` - Drag functionality
- `static/css/main.css` - Window styling

---

*A satisfying balance of modern functionality with retro aesthetics.*
