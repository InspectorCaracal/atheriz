import sys
import os

# Add repo root to sys.path
sys.path.append(r"c:\Users\anon\repos\atheriz")

from atheriz.commands.loggedin.maze import gen_map_and_grid
from atheriz.objects.nodes import NodeGrid

def verify():
    print("Testing gen_map_and_grid...")
    width = 10
    height = 10
    placeholder = "X"
    
    grid, pre_grid = gen_map_and_grid(width, height, "test_area", placeholder)
    
    if not isinstance(grid, NodeGrid):
        print("FAIL: grid is not NodeGrid")
        return
        
    if not isinstance(pre_grid, dict):
        print("FAIL: pre_grid is not dict")
        return
        
    if len(pre_grid) == 0:
        print("FAIL: pre_grid is empty")
        return
        
    # Check if placeholder is correct
    first_val = next(iter(pre_grid.values()))
    if first_val != placeholder:
         print(f"FAIL: placeholder mismatch. Expected {placeholder}, got {first_val}")
         return

    print(f"SUCCESS: Generated {len(pre_grid)} rooms/path segments.")
    # For a 10x10 maze, scaling 2x means 100 rooms + (spanning tree edges = 99) = 199 nodes
    if len(pre_grid) < 190:
        print(f"FAIL: Too few nodes generated ({len(pre_grid)}) for a 10x10 scaled maze.")
        return
    
    print("Verification passed.")

if __name__ == "__main__":
    verify()
