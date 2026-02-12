from random import choice
from atheriz.objects.nodes import Node, NodeLink, NodeGrid, NodeArea
from atheriz.singletons.get import get_node_handler, get_map_handler
from atheriz.singletons.map import MapInfo, LegendEntry
from atheriz.commands.base_cmd import Command
from atheriz.singletons.objects import get_by_type
from atheriz.utils import wrap_xterm256
import atheriz.settings as settings
import time
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from atheriz.websocket import Connection
    from atheriz.objects.base_obj import Object


class MazeCommand(Command):
    key = "maze"
    desc = "Generate a maze."
    category = "Builder"
    hide = True
    aliases = ["-s", "-r"]

    # pyrefly: ignore
    def access(self, caller: Object) -> bool:
        return caller.is_builder

    def __init__(self):
        super().__init__()

    # pyrefly: ignore
    def run(self, caller: Object, args):
        nh = get_node_handler()
        width = 40
        height = 15
        
        placeholder = settings.ROAD_PLACEHOLDER
        if "-s" in args or "--single" in args:
            placeholder = settings.SINGLE_WALL_PLACEHOLDER
        elif "-r" in args or "--round" in args:
            placeholder = settings.PATH_PLACEHOLDER

        # map returned is a rectangular outline around grid, so actual map size returned is +2
        start = time.time()
        grid1, pre_grid1 = gen_map_and_grid(width, height, "maze1", placeholder)
        grid2, pre_grid2 = gen_map_and_grid(width, height, "maze2", placeholder)
        grid3, pre_grid3 = gen_map_and_grid(width, height, "maze3", placeholder)
        rooms = len(grid1) + len(grid2) + len(grid3)
        elapsed = (time.time() - start) * 1000
        caller.msg(
            f"created 3 {width} x {height} mazes, {rooms} rooms, and lots of exits in: {elapsed:.2f} milliseconds"
        )
        area1 = NodeArea("maze1")
        area2 = NodeArea("maze2")
        area3 = NodeArea("maze3")
        area1.add_grid(grid1)
        area2.add_grid(grid2)
        area3.add_grid(grid3)
        nh.add_area(area1)
        nh.add_area(area2)
        nh.add_area(area3)
        mh = get_map_handler()
        maze1_exit = grid1.get_random_node()
        maze2_exit = grid2.get_random_node()
        maze3_exit = grid3.get_random_node()
        
        # Helper to create map info with legend
        def create_map_info(name, pre_grid, exit_node, target_name):
            legend_entries = {
                -1: LegendEntry(
                    wrap_xterm256("!", fg=9), 
                    f"to {target_name}", 
                    (exit_node.coord[1], exit_node.coord[2])
                )
            }
            return MapInfo(
                name=name,
                pre_grid=pre_grid,
                legend_entries=legend_entries
            )

        mi1 = create_map_info("maze1", pre_grid1, maze1_exit, "maze2")
        mi2 = create_map_info("maze2", pre_grid2, maze2_exit, "maze3")
        mi3 = create_map_info("maze3", pre_grid3, maze3_exit, "maze1")

        mh.set_mapinfo("maze1", 0, mi1)
        mh.set_mapinfo("maze2", 0, mi2)
        mh.set_mapinfo("maze3", 0, mi3)
        
        maze1_exit.add_link(NodeLink("down", ("maze2", 0, 0, 0), ["d"]))
        maze2_exit.add_link(NodeLink("down", ("maze3", 0, 0, 0), ["d"]))
        maze3_exit.add_link(NodeLink("down", ("maze1", 0, 0, 0), ["d"]))
        
        node = nh.get_node(("maze1", 0, 0, 0))
        if node:
            caller.map_enabled = True
            caller.msg(f"moving to: {node} ...")
            caller.move_to(node)


def create_maze(width: int, height: int) -> dict:
    visited = {}

    def get_valid_neighbors(coord: tuple, width: int, height: int) -> list:
        coords_to_check = []
        if coord[0] > 0:
            coords_to_check.append((coord[0] - 1, coord[1]))
        if coord[0] < width - 1:
            coords_to_check.append((coord[0] + 1, coord[1]))
        if coord[1] > 0:
            coords_to_check.append((coord[0], coord[1] - 1))
        if coord[1] < height - 1:
            coords_to_check.append((coord[0], coord[1] + 1))
        results = []
        for c in coords_to_check:
            v = visited.get(c, False)
            if not v:
                results.append(c)
        return results

    start = (0, 0)
    valid = get_valid_neighbors(start, width, height)
    current = start
    path = []
    maze = {}
    nodes = maze.get(current, [])
    done = False
    while not done:
        c = choice(valid)
        visited[c] = True
        path.append(c)
        if len(nodes) == 0:
            maze[current] = [c]
        else:
            nodes.append(c)
            maze[current] = nodes
        current = c
        nodes = maze.get(current, [])
        valid = get_valid_neighbors(current, width, height)
        while not bool(valid):
            path = path[:-1]
            if not bool(path):
                done = True
                break
            current = path[-1]
            nodes = maze.get(current, [])
            valid = get_valid_neighbors(current, width, height)
    return maze


def create_map(maze: dict, width: int, height: int, area: str, placeholder: str) -> Tuple[NodeGrid, dict]:
    pre_grid = {}
    grid = NodeGrid(area, 0)
    
    def get_or_create_node(x, y):
        # check if node exists in grid first
        existing = grid.get_node((x, y))
        if existing:
            return existing
        
        node = Node((area, x, y, 0), "Somewhere in a mysterious maze.")
        grid.add_node(node)
        pre_grid[(x, y)] = placeholder
        return node

    # iterate through maze cells and create corresponding map nodes and links
    for cell, neighbors in maze.items():
        cx, cy = cell
        
        # Room node at 2x coordinates
        mx, my = cx * 2, cy * 2
        room_node = get_or_create_node(mx, my)
        
        for nx, ny in neighbors:
            mx_neighbor, my_neighbor = nx * 2, ny * 2
            
            # Intermediate "connector" node
            connector_x = mx + (nx - cx)
            connector_y = my + (ny - cy)
            
            connector_node = get_or_create_node(connector_x, connector_y)
            neighbor_node = get_or_create_node(mx_neighbor, my_neighbor)
            
            # Link Room <-> Connector
            if connector_x > mx:
                room_node.add_link(NodeLink("east", (area, connector_x, connector_y, 0), ["e"]))
                connector_node.add_link(NodeLink("west", (area, mx, my, 0), ["w"]))
            elif connector_x < mx:
                room_node.add_link(NodeLink("west", (area, connector_x, connector_y, 0), ["w"]))
                connector_node.add_link(NodeLink("east", (area, mx, my, 0), ["e"]))
            elif connector_y > my:
                room_node.add_link(NodeLink("north", (area, connector_x, connector_y, 0), ["n"]))
                connector_node.add_link(NodeLink("south", (area, mx, my, 0), ["s"]))
            elif connector_y < my:
                room_node.add_link(NodeLink("south", (area, connector_x, connector_y, 0), ["s"]))
                connector_node.add_link(NodeLink("north", (area, mx, my, 0), ["n"]))
                
            # Link Connector <-> Neighbor
            if mx_neighbor > connector_x:
                connector_node.add_link(NodeLink("east", (area, mx_neighbor, my_neighbor, 0), ["e"]))
                neighbor_node.add_link(NodeLink("west", (area, connector_x, connector_y, 0), ["w"]))
            elif mx_neighbor < connector_x:
                connector_node.add_link(NodeLink("west", (area, mx_neighbor, my_neighbor, 0), ["w"]))
                neighbor_node.add_link(NodeLink("east", (area, connector_x, connector_y, 0), ["e"]))
            elif my_neighbor > connector_y:
                connector_node.add_link(NodeLink("north", (area, mx_neighbor, my_neighbor, 0), ["n"]))
                neighbor_node.add_link(NodeLink("south", (area, connector_x, connector_y, 0), ["s"]))
            elif my_neighbor < connector_y:
                connector_node.add_link(NodeLink("south", (area, mx_neighbor, my_neighbor, 0), ["s"]))
                neighbor_node.add_link(NodeLink("north", (area, connector_x, connector_y, 0), ["n"]))
                
    return grid, pre_grid


def gen_map_and_grid(w: int, h: int, area: str, placeholder: str):
    maze = create_maze(w, h)
    grid, pre_grid = create_map(maze, w, h, area, placeholder)
    return grid, pre_grid

