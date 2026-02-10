# Sprite Pattern Generator

## Introduction

The Sprite Pattern Generator is a Python/Tkinter GUI tool for creating tiny 6×8 pixel sprites and converting them into hexadecimal values that can be used in GLSL shaders.

## The Problem

The dithering patterns are created manually instead of algorithmically because of the awkward grid size used in [Demonin's Original Script](https://demonin.com/script.js) and my lack of knowledge on dither patterns outside of [bayer matrix dithers](https://blog.kaetemi.be/2015/04/01/practical-bayer-dithering/). When working with GLSL shader used to make this background, I needed a way to define small pixel patterns for procedural texture generation. The shader uses bit-packed data to efficiently store sprite patterns, but manually calculating hex values for 6×8 pixel grids is tedious and error-prone.

## The Solution

A visual editor that lets you:

1. Click cells to toggle pixels on/off
2. See your pattern in real-time
3. Generate the correct hex values automatically
4. Import existing patterns for editing

## Technical Details

### Bit Packing Strategy

The 6×8 grid requires 48 bits total (6 pixels × 8 rows). We store this as a `vec2` in GLSL:

```glsl
vec2 sprite = vec2(0x404040, 0x404040);
```

- **First component**: Upper 24 bits (rows 4-7)
- **Second component**: Lower 24 bits (rows 0-3)

### Bit Position Mapping

The shader reads bits in reverse X order:

```python
bit_x = width - x - 1  # Right to left
bit_y = y * width       # Row offset
bit_position = bit_x + bit_y
```

This matches how the GLSL shader extracts pixel data:

```glsl
float bitX = SPR_SIZE.x - uv.x - 1.0;
float bitY = uv.y * SPR_SIZE.x;
vec2 bitPosition = vec2(bitX + bitY) - vec2(24.0, 0.0);
```

### Example Grid

Here's how a simple pattern maps to bits:

```
Row 0: [0][0][1][0][0][0]  → bits 0-5
Row 1: [0][1][0][1][0][0]  → bits 6-11
Row 2: [1][0][0][0][1][0]  → bits 12-17
...and so on
```

## Features

### Visual Editor

- 6×8 clickable grid
- White = pixel on, Black = pixel off
- Instant visual feedback

### Import/Export

- **Generate**: Creates `vec2(0xXXXXXX, 0xXXXXXX)` format
- **Import**: Load existing hex values for editing
- **Copy**: Auto-copies to clipboard

## Usage Example

1. **Create Pattern**: Click cells to design your sprite
2. **Generate Hex**: Click "Generate Hex" button
3. **Copy Output**: `vec2(0x123456, 0xABCDEF);`
4. **Use in Shader**: Paste into your GLSL code

```glsl
vec2 sprite_custom = vec2(0x404040, 0x404040);
```

## Code Highlights

### Bit Extraction

```python
def generate_hex(self):
    bits = 0
    for y in range(self.height):
        for x in range(self.width):
            bit_position = (self.width - x - 1) + (y * self.width)
            if self.grid[y][x] == 1:
                bits |= (1 << bit_position)
    
    # Split into 24-bit values
    lower_24 = bits & 0xFFFFFF
    upper_24 = (bits >> 24) & 0xFFFFFF
```

### Pattern Import

```python
def import_vec2(self):
    # Parse: vec2(0x123456, 0xABCDEF)
    pattern = r'0x([0-9A-Fa-f]+)\\s*,\\s*0x([0-9A-Fa-f]+)'
    match = re.search(pattern, input_text)
    
    if match:
        upper_hex = int(match.group(1), 16)
        lower_hex = int(match.group(2), 16)
        self.load_pattern_from_hex(upper_hex, lower_hex)
```

## Limitations

The current version is limited to 6×8 sprites because:

- Storage is constrained to 48 bits (vec2)
- 8×8 would need 64 bits (requires vec3 or vec4)
- All existing patterns use 6×8 encoding

Expanding to 8×8 would require:

1. Changing storage format
2. Updating bit extraction logic
3. Re-encoding all existing patterns

## Future Improvements

Potential enhancements:

- [ ] Support for different sprite sizes (4×4, 8×8, 16×16)
- [ ] Pattern library with presets
- [ ] Export to different formats (PNG, C array, etc.)
- [ ] Import from different formats
- [ ] Undo/redo functionality
- [ ] Pattern symmetry tools

## Files

- [sprite_pattern_generator.py](https://araxia.xyz/files/showcase/sprite_pattern_generator.py)

## Try It!

Run the generator:
```bash
python sprite_pattern_generator.py
```

No additional dependencies required beyond Python's built-in `tkinter`!
