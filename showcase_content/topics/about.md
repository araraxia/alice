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

- `fort` - Authentication, user management and future website feature hosting (forum, live chat, etc.).
- `osrs` - Old School RuneScape tools
- `showcase` - Project documentation (you're here!)
- `wiki` - Future documentation hosting

### Data Flow

1. User clicks button
2. JavaScript fetches HTML from Flask endpoint
3. Window is created with loaded content
4. Additional scripts initialize the window's functionality
5. Window becomes interactive and managed by windowManager.

## Development Goals

This site serves multiple purposes:

1. **Portfolio** - Showcase my technical skills
2. **Tool Suite** - Host useful calculators and utilities
3. **Learning Platform** - Experiment with new technologies
4. **Fun Project** - Just enjoying building cool stuff!

## Open Source

Much of the code powering this site could be useful to others, and could not be made without the hard work of people before me. All the code powering this site and most of my projects is open source and free for anyone to utilize.

## Future Plans

Some ideas I'm considering:

- [ ] More OSRS calculators and tools (Primarily real-time gp/xp calculations for different skills. A lot of money can be made with the "buyable" skills with the right margins at the right time.)
- [ ] Interactive demos and visualizations
- [ ] Mobile-responsive window system
- [ ] Blog system with markdown support (partially done!)
- [ ] User forums with account customization. The aim is for the classic late 2000s forum style as counter form to the current trend of everything being on platforms such as reddit or discord, platforms with a dubious lifespan where the content can be lost at any moment.
- [ ] Write a blob post about the inevitable loss of a huge source of knowledge/data thanks to discord being used as a psuedo wiki/forum/documentation site.

---

~*Built with <3 by Aria Corona*~
