#!/usr/bin/env python3
"""Generate PNG versions of the FlashPilot logo at various sizes."""

from PIL import Image, ImageDraw
import xml.etree.ElementTree as ET

def svg_to_png(svg_path, output_path, size):
    """Simple SVG to PNG conversion using PIL."""
    # Parse SVG to get dimensions
    tree = ET.parse(svg_path)
    root = tree.getroot()
    
    # Create a new image
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw background circle
    center = size // 2
    radius = int(size * 0.47)
    draw.ellipse([center - radius, center - radius, center + radius, center + radius],
                 fill=(26, 26, 46, 255), outline=(0, 212, 255, 255), width=2)
    
    # Draw inner ring
    inner_radius = int(size * 0.39)
    draw.ellipse([center - inner_radius, center - inner_radius, center + inner_radius, center + inner_radius],
                 fill=None, outline=(0, 212, 255, 153), width=2)
    
    # Draw lightning bolt (simplified)
    bolt_points = [
        (center, int(size * 0.156)),
        (int(center - size * 0.148), int(size * 0.469)),
        (center, int(size * 0.469)),
        (int(center - size * 0.109), int(size * 0.742)),
        (int(center + size * 0.148), int(size * 0.391)),
        (center, int(size * 0.391)),
        (int(center + size * 0.125), int(size * 0.156))
    ]
    draw.polygon(bolt_points, fill=(255, 107, 53, 255), outline=(255, 107, 53, 255))
    
    # Draw crosshair elements
    crosshair_color = (0, 212, 255, 204)
    line_width = max(2, size // 170)
    
    # Horizontal lines
    draw.line([(int(size * 0.234), center), (int(size * 0.352), center)], fill=crosshair_color, width=line_width)
    draw.line([(int(size * 0.648), center), (int(size * 0.766), center)], fill=crosshair_color, width=line_width)
    
    # Vertical lines  
    draw.line([(center, int(size * 0.234)), (center, int(size * 0.352))], fill=crosshair_color, width=line_width)
    draw.line([(center, int(size * 0.648)), (center, int(size * 0.766))], fill=crosshair_color, width=line_width)
    
    # Draw corner brackets
    bracket_color = (0, 212, 255, 179)
    bracket_width = max(3, size // 128)
    
    # Top-left
    draw.line([(int(size * 0.156), int(size * 0.352)), (int(size * 0.156), int(size * 0.156)), (int(size * 0.352), int(size * 0.156))], 
              fill=bracket_color, width=bracket_width)
    # Top-right
    draw.line([(int(size * 0.648), int(size * 0.156)), (int(size * 0.766), int(size * 0.156)), (int(size * 0.766), int(size * 0.352))], 
              fill=bracket_color, width=bracket_width)
    # Bottom-left
    draw.line([(int(size * 0.156), int(size * 0.648)), (int(size * 0.156), int(size * 0.766)), (int(size * 0.352), int(size * 0.766))], 
              fill=bracket_color, width=bracket_width)
    # Bottom-right
    draw.line([(int(size * 0.648), int(size * 0.766)), (int(size * 0.766), int(size * 0.766)), (int(size * 0.766), int(size * 0.648))], 
              fill=bracket_color, width=bracket_width)
    
    # Draw data dots
    dot_color = (0, 212, 255, 153)
    dot_radius = max(3, size // 85)
    dot_positions = [
        (int(size * 0.293), int(size * 0.293)),
        (int(size * 0.707), int(size * 0.293)),
        (int(size * 0.293), int(size * 0.707)),
        (int(size * 0.707), int(size * 0.707))
    ]
    for x, y in dot_positions:
        draw.ellipse([x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius], fill=dot_color)
    
    img.save(output_path, 'PNG')
    print(f"Generated {output_path} ({size}x{size})")

if __name__ == "__main__":
    svg_path = "/home/elijah/brilliant/docs/logo_flashpilot.svg"
    
    # Generate different sizes
    sizes = [64, 128, 256, 512, 1024]
    for size in sizes:
        output_path = f"/home/elijah/brilliant/docs/logo_flashpilot_{size}.png"
        svg_to_png(svg_path, output_path, size)
