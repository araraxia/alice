# Showcase Content Directory

This directory contains all the markdown content and navigation structure for the showcase window.

## Structure

```
showcase_content/
├── navigation.json          # Sidebar navigation structure
└── topics/                  # Individual topic markdown files
    ├── welcome.md
    ├── about.md
    ├── sprite-pattern-generator.md
    ├── shader-background.md
    └── window-system.md
```

## Adding New Topics

### 1. Create Markdown File

Create a new `.md` file in `topics/` directory:

```markdown
# My New Project

## Overview
Description of your project...

## Technical Details
Implementation details...
```

### 2. Update Navigation

Edit `navigation.json` to add your topic to a category:

```json
{
  "categories": [
    {
      "name": "Your Category",
      "items": [
        {
          "id": "my-new-project",
          "title": "My New Project"
        }
      ]
    }
  ]
}
```

**Important**: The `id` must match the filename (without `.md` extension).

### 3. Reload Page

The showcase window will automatically load your new topic!

## Markdown Features

### Supported Syntax

- **Headers**: `# H1`, `## H2`, `### H3`, etc.
- **Bold**: `**bold text**`
- **Italic**: `*italic text*`
- **Links**: `[text](url)`
- **Images**: `![alt](url)`
- **Code**: `` `inline code` ``
- **Code Blocks**: ` ```language\ncode\n``` `
- **Lists**: Unordered (`-`, `*`) and ordered (`1.`)
- **Blockquotes**: `> quote`
- **Tables**: GitHub-flavored markdown tables
- **Horizontal Rules**: `---`

### Code Highlighting

Code blocks with language specification get proper formatting:

````markdown
```python
def hello():
    print("Hello, world!")
```
````

```javascript
function hello() {
  console.log("Hello, world!");
}
```

## Navigation Structure

### Categories

Each category has:
- `name` - Display name in sidebar
- `items` - Array of topics in this category

### Items

Each item has:
- `id` - Unique identifier (matches filename)
- `title` - Display name in sidebar

### Example

```json
{
  "categories": [
    {
      "name": "Python Projects",
      "items": [
        {
          "id": "project-one",
          "title": "Project One"
        },
        {
          "id": "project-two",
          "title": "Project Two"
        }
      ]
    }
  ]
}
```

## File Naming

- Use kebab-case: `my-project-name.md`
- Match the `id` in `navigation.json`
- Use descriptive names

## Best Practices

### Topic Organization

- Group related topics in categories
- Keep topics focused on one subject
- Use clear, descriptive titles

### Content Structure

1. **Title** - Main H1 header
2. **Overview** - Brief introduction
3. **Sections** - Logical content divisions
4. **Code Examples** - Illustrate concepts
5. **Future Plans** - Optional roadmap

### Writing Style

- Clear and concise
- Technical but accessible
- Include code examples
- Link to related topics
- Add images/diagrams when helpful

## Tips

### Cross-Referencing

Link to other topics using hash navigation:

```markdown
See the [Sprite Pattern Generator](/#sprite-pattern-generator) for details.
```

### External Links

```markdown
Check out [GitHub](https://github.com/araraxia) for source code.
```

### Images

Store images in `static/images/showcase/` and reference them:

```markdown
![Diagram](/static/images/showcase/diagram.png)
```

### Task Lists

```markdown
- [x] Completed task
- [ ] Pending task
```

## Collapsible Categories

Categories in the sidebar can be collapsed by clicking the header. This is handled automatically by the JavaScript.

## URL Hash Navigation

Topics can be linked directly:
- `/#welcome` - Opens showcase with welcome topic
- `/#sprite-pattern-generator` - Opens specific project

## Troubleshooting

### Topic Not Loading

- Check filename matches ID in navigation.json
- Ensure file is in `topics/` directory
- Verify JSON syntax is valid
- Check browser console for errors

### Navigation Not Updating

- Verify `navigation.json` is valid JSON
- Refresh the page to reload navigation
- Check Flask logs for errors

### Markdown Not Rendering

- Ensure marked.js is loaded (CDN)
- Check browser console for JavaScript errors
- Test markdown syntax at [markdownlivepreview.com](https://markdownlivepreview.com/)

## Maintenance

### Regular Updates

- Keep content current
- Update technical details
- Add new projects
- Archive old/deprecated topics

### Version Control

All content should be committed to git:
- Track changes to topics
- Version navigation structure
- Maintain history

---

Happy documenting! 📝
