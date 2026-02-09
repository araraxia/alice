# About This Site

## Overview

Araxia.xyz is my personal website and digital playground. It's designed to be a space where I can experiment with new technologies, showcase my work, and share useful tools with others.

## Design Philosophy

### Retro Aesthetics

The site draws inspiration from Windows 98's interface design, featuring:

- Draggable windows
- Classic button styling
- Nostalgic color schemes

But with modern web technologies underneath:

- WebGL shaders for dynamic backgrounds
- Responsive layouts
- Smooth animations

### Modular Architecture

The site is built with a modular window system that allows:

- Multiple windows open simultaneously
- Z-index management for layering
- Dynamic content loading
- Memory-efficient component lifecycle

## Technical Details

### Frontend Architecture

```javascript
// Window management system
windowManager.createWindow({
  id: 'example-window',
  title: 'Example',
  content: dynamicHTML
});
```

The window system handles:
- Window creation and destruction
- Focus management
- Drag functionality
- Content loading

### Backend Structure

The Flask backend is organized into blueprints:

- `fort` - Authentication and user management
- `osrs` - Old School RuneScape tools
- `showcase` - Project documentation (you're here!)
- `wiki` - Wiki integration

### Data Flow

1. User clicks button
2. JavaScript fetches HTML from Flask endpoint
3. Window is created with loaded content
4. Additional scripts initialize the window's functionality
5. Window becomes interactive

## Development Goals

This site serves multiple purposes:

1. **Portfolio** - Showcase my technical skills
2. **Tool Suite** - Host useful calculators and utilities
3. **Learning Platform** - Experiment with new technologies
4. **Fun Project** - Just enjoying building cool stuff!

## Open Source

Much of the code powering this site could be useful to others. If there's interest, I may open-source certain components. Feel free to reach out if you're curious about specific implementations!

## Future Plans

Some ideas I'm considering:

- [ ] Blog system with markdown support (partially done!)
- [ ] More OSRS calculators and tools
- [ ] Interactive demos and visualizations
- [ ] User-contributed content system
- [ ] Dark/light theme toggle
- [ ] Mobile-responsive window system

---

*Built with ❤️ by Aria Corona*
