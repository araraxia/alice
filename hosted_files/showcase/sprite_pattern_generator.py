#!/usr/bin/env python3
"""
Sprite Pattern Generator for GLSL Shader
Creates 6x8 pixel patterns and outputs hex values for vec2 format
"""

import tkinter as tk
from tkinter import messagebox, simpledialog
import re

class SpritePatternGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("Sprite Pattern Generator (6x8)")
        
        # 6 wide x 8 tall grid
        self.width = 6
        self.height = 8
        self.cell_size = 50
        
        # Grid state (0 = off, 1 = on)
        self.grid = [[0 for _ in range(self.width)] for _ in range(self.height)]
        
        # Create canvas
        self.canvas = tk.Canvas(
            root, 
            width=self.width * self.cell_size, 
            height=self.height * self.cell_size,
            bg='white'
        )
        self.canvas.pack(pady=10)
        
        # Draw grid
        self.cells = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                x1 = x * self.cell_size
                y1 = y * self.cell_size
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size
                
                cell = self.canvas.create_rectangle(
                    x1, y1, x2, y2,
                    fill='white',
                    outline='gray',
                    width=2
                )
                row.append(cell)
            self.cells.append(row)
        
        # Bind click event
        self.canvas.bind('<Button-1>', self.on_click)
        
        # Create buttons frame
        button_frame = tk.Frame(root)
        button_frame.pack(pady=10)
        
        tk.Button(button_frame, text="Import vec2", command=self.import_vec2).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Clear All", command=self.clear_all).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Fill All", command=self.fill_all).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Generate Hex", command=self.generate_hex).pack(side=tk.LEFT, padx=5)
        
        # Output frame
        output_frame = tk.Frame(root)
        output_frame.pack(pady=10)
        
        tk.Label(output_frame, text="GLSL vec2 Output:").pack()
        self.output_text = tk.Text(output_frame, height=3, width=50)
        self.output_text.pack(pady=5)
        
        # Info label
        info = tk.Label(root, text="Click cells to toggle on/off", fg='gray')
        info.pack(pady=5)
        self.update_display()
    
    def on_click(self, event):
        """Handle cell clicks"""
        x = event.x // self.cell_size
        y = event.y // self.cell_size
        
        if 0 <= x < self.width and 0 <= y < self.height:
            # Toggle cell
            self.grid[y][x] = 1 - self.grid[y][x]
            self.update_display()
    
    def update_display(self):
        """Update the visual display of the grid"""
        for y in range(self.height):
            for x in range(self.width):
                color = 'white' if self.grid[y][x] == 1 else 'black'
                self.canvas.itemconfig(self.cells[y][x], fill=color)
    
    def import_vec2(self):
        """Import pattern from vec2 hex values"""
        # Create custom dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Import vec2 Pattern")
        dialog.geometry("400x150")
        
        tk.Label(dialog, text="Paste vec2 value (e.g., vec2(0x404040, 0x404040)):").pack(pady=10)
        
        entry = tk.Entry(dialog, width=50)
        entry.pack(pady=5)
        entry.focus()
        
        def parse_and_load():
            input_text = entry.get().strip()
            
            # Try to parse vec2 format
            # Accepts: vec2(0x123456, 0xABCDEF) or just 0x123456, 0xABCDEF
            pattern = r'(?:vec2\s*\(\s*)?0x([0-9A-Fa-f]+)\s*,\s*0x([0-9A-Fa-f]+)'
            match = re.search(pattern, input_text)
            
            if match:
                try:
                    upper_hex = int(match.group(1), 16)
                    lower_hex = int(match.group(2), 16)
                    
                    # Validate ranges
                    if upper_hex > 0xFFFFFF or lower_hex > 0xFFFFFF:
                        messagebox.showerror("Error", "Hex values must be 24-bit (0x000000 to 0xFFFFFF)")
                        return
                    
                    self.load_pattern_from_hex(upper_hex, lower_hex)
                    dialog.destroy()
                    messagebox.showinfo("Success", "Pattern imported successfully!")
                except ValueError:
                    messagebox.showerror("Error", "Invalid hex values")
            else:
                messagebox.showerror("Error", "Invalid format. Use: vec2(0xXXXXXX, 0xXXXXXX)")
        
        tk.Button(dialog, text="Import", command=parse_and_load).pack(pady=10)
        
        # Bind Enter key
        entry.bind('<Return>', lambda e: parse_and_load())
    
    def clear_all(self):
        """Clear all cells"""
        self.grid = [[0 for _ in range(self.width)] for _ in range(self.height)]
        self.update_display()
    
    def fill_all(self):
        """Fill all cells"""
        self.grid = [[1 for _ in range(self.width)] for _ in range(self.height)]
        self.update_display()
    
    def generate_hex(self):
        """Generate hex values for the current pattern"""
        # Convert grid to bit pattern
        # The shader reads bits in a specific order:
        # Rows 0-3: bits 0-23 (second vec2 component)
        # Rows 4-7: bits 24-47 (first vec2 component)
        # Within each row: right to left (bit 5 to 0, 11 to 6, etc.)
        
        bits = 0
        
        for y in range(self.height):
            for x in range(self.width):
                # Calculate bit position
                # Shader uses: bitX = 6.0 - uv.x - 1.0 (reverse X)
                bit_x = self.width - x - 1
                bit_y = y * self.width
                bit_position = bit_x + bit_y
                
                # Set bit if pixel is on
                if self.grid[y][x] == 1:
                    bits |= (1 << bit_position)
        
        # Split into two 24-bit values
        lower_24 = bits & 0xFFFFFF  # Bits 0-23 (second component)
        upper_24 = (bits >> 24) & 0xFFFFFF  # Bits 24-47 (first component)
        
        # Format output
        output = f"vec2(0x{upper_24:06X}, 0x{lower_24:06X});"
        
        self.output_text.delete('1.0', tk.END)
        self.output_text.insert('1.0', output)
        
        # Also copy to clipboard
        self.root.clipboard_clear()
        self.root.clipboard_append(output)
        
        # Show info
        messagebox.showinfo("Generated", f"Hex values generated and copied to clipboard!\n\n{output}")
    
    def load_pattern_from_hex(self, upper_hex, lower_hex):
        """Load a pattern from hex values (for testing)"""
        # Combine into single 48-bit value
        bits = (upper_hex << 24) | lower_hex
        
        # Extract pixel values
        for y in range(self.height):
            for x in range(self.width):
                bit_x = self.width - x - 1
                bit_y = y * self.width
                bit_position = bit_x + bit_y
                
                self.grid[y][x] = 1 if (bits & (1 << bit_position)) else 0
        
        self.update_display()

def main():
    root = tk.Tk()
    app = SpritePatternGenerator(root)
    
    # Example: Load existing pattern for testing
    # app.load_pattern_from_hex(0x404040, 0x404040)
    
    root.mainloop()

if __name__ == "__main__":
    main()
