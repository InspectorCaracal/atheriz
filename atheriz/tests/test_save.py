import pytest
import shutil
import json
from pathlib import Path
from atheriz import settings
from atheriz.objects.base_obj import Object
from atheriz.objects.base_account import Account
from atheriz.objects.persist import save, save_iterable, get_save_path, save_object
from atheriz.singletons import objects as obj_singleton
from atheriz.singletons.node import NodeHandler
from atheriz.singletons.map import MapHandler, MapInfo
from atheriz.objects.nodes import NodeArea, Transition, Door, Node, NodeGrid

TEST_SAVE_DIR = Path("test_save_data")


@pytest.fixture(autouse=True)
def setup_teardown():
    # Setup
    original_save_path = settings.SAVE_PATH
    settings.SAVE_PATH = str(TEST_SAVE_DIR)
    if TEST_SAVE_DIR.exists():
        shutil.rmtree(TEST_SAVE_DIR)
    TEST_SAVE_DIR.mkdir()

    # Cleanup object registry
    obj_singleton._ALL_OBJECTS.clear()

    yield

    # Teardown
    settings.SAVE_PATH = original_save_path
    if TEST_SAVE_DIR.exists():
        shutil.rmtree(TEST_SAVE_DIR)


def test_save_load_account():
    # Test saving a single Account
    acc = Account.create("TestUser", "password")
    save(acc)

    path = get_save_path(acc)
    assert path.exists()

    with open(path, "r") as f:
        data = json.load(f)

    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "TestUser"
    assert data[0]["__import_path__"] == "atheriz.objects.base_account.Account"


def test_save_load_pc_object():
    # Test saving a PC Object (is_pc=True)
    # PC objects should save to individual files because group_save=True but they are often handled individually?
    # Actually wait, let's check base_obj.py:
    # defaults: group_save = True.
    # create(is_pc=True) set obj.group_save = True (from user diff).
    # wait, if is_sys=False it might put it in a group file?
    # Let's check persist.py logic:
    # save_iterable puts all objects in one file IF create_new_file is false?
    # save() automatically calls save_object or save_iterable.

    pc = Object.create(None, "PlayerChar", is_pc=True)
    save(pc)

    path = get_save_path(pc)
    assert path.exists()

    with open(path, "r") as f:
        data = json.load(f)

    assert len(data) == 1
    assert data[0]["name"] == "PlayerChar"
    assert data[0]["is_pc"] is True
    assert data[0]["__import_path__"] == "atheriz.objects.base_obj.Object"


def test_save_load_item_object():
    # Test saving an Item Object (is_pc=False, is_item=True)
    item = Object.create(None, "ShinySword", is_pc=False, is_item=True)
    # is_pc=False -> group_save=True by default now

    assert item.group_save is True
    save(item)

    path = get_save_path(item)
    assert path.exists()

    with open(path, "r") as f:
        data = json.load(f)

    assert len(data) == 1
    assert data[0]["name"] == "ShinySword"
    assert data[0]["is_item"] is True


def test_save_list_of_objects_individual():
    # Test saving a list of objects that have group_save=False
    # They should be saved to individual files
    item1 = Object.create(None, "Item1")
    item1.group_save = False
    item2 = Object.create(None, "Item2")
    item2.group_save = False

    save([item1, item2])

    path1 = get_save_path(item1)
    path2 = get_save_path(item2)

    assert path1.exists()
    assert path2.exists()
    assert path1 != path2


def test_save_list_of_group_objects():
    # Test saving a list of objects that have group_save=True
    # They should be grouped into one file
    o1 = Object.create(None, "GroupObj1")
    o1.group_save = True
    o2 = Object.create(None, "GroupObj2")
    o2.group_save = True

    save([o1, o2])

    # They should be in the same file (Class file)
    path = get_save_path(o1, append_id=False)

    assert path.exists()

    with open(path, "r") as f:
        data = json.load(f)

    assert len(data) == 2
    names = [d["name"] for d in data]
    assert "GroupObj1" in names
    assert "GroupObj2" in names


def test_nodehandler_save_load():
    # Setup - Create NodeHandler and confirm clean state (due to fixture)
    handler = NodeHandler()
    assert len(handler.areas) == 0
    assert len(handler.transitions) == 0
    assert len(handler.doors) == 0

    # Create Data
    area = NodeArea(name="TestHandlerArea")
    handler.areas["TestHandlerArea"] = area

    trans_key = ("DestArea", 0, 0, 0)
    trans = Transition(from_coord=("SrcArea", 0, 0, 0), to_coord=trans_key, from_link="north")
    handler.transitions[trans_key] = trans

    door_key = ("SrcArea", 0, 0, 0)
    door = Door(
        from_coord=door_key, to_coord=("DestArea", 0, 0, 0), from_exit="north", to_exit="south"
    )
    handler.doors[door_key] = {"north": door}

    # SAVE
    handler.save()

    # Check files exist
    assert (TEST_SAVE_DIR / "areas").exists()
    assert (TEST_SAVE_DIR / "transitions").exists()
    assert (TEST_SAVE_DIR / "doors").exists()

    # LOAD - New NodeHandler
    new_handler = NodeHandler()

    # Verify Areas
    assert "TestHandlerArea" in new_handler.areas
    assert new_handler.areas["TestHandlerArea"].name == "TestHandlerArea"

    # Verify Transitions
    assert trans_key in new_handler.transitions
    t = new_handler.transitions[trans_key]
    assert t.from_coord == ("SrcArea", 0, 0, 0)

    # Verify Doors
    assert door_key in new_handler.doors
    assert "north" in new_handler.doors[door_key]
    d = new_handler.doors[door_key]["north"]
    assert d.to_exit == "south"


def test_save_load_object_with_locks():
    """Test saving and loading an object with locks."""
    obj = Object.create(None, "LockedObj")
    obj.group_save = False
    obj.add_lock("control", lambda x: x.is_builder or x.is_superuser)
    obj.add_lock("view", lambda x: True)
    obj.add_lock("edit", lambda x: x.privilege_level >= 3)
    save(obj)
    path = get_save_path(obj)
    assert path.exists()

    with open(path, "r") as f:
        data = json.load(f)

    assert len(data) == 1
    assert data[0]["name"] == "LockedObj"
    assert "locks" in data[0]

    new_obj = Object()
    new_obj.__setstate__(data[0])

    # Verify lock structure
    assert "control" in new_obj.locks
    assert "view" in new_obj.locks
    assert "edit" in new_obj.locks
    assert len(new_obj.locks["control"]) == 1

    # Verify locks function correctly
    accessor = Object()
    accessor.privilege_level = 3  # builder
    accessor.quelled = False

    assert new_obj.access(accessor, "view") is True
    assert new_obj.access(accessor, "edit") is True
    assert new_obj.access(accessor, "control") is True


def test_node_locks_persistence():
    """Test that Node locks persist correctly through NodeHandler save/load."""
    # Setup NodeHandler
    handler = NodeHandler()

    # Create hierarchy: Area -> Grid -> Node
    area = NodeArea(name="LockTestArea")
    grid = NodeGrid(z=0)

    # Create Node with locks
    node = Node(coord=("LockTestArea", 0, 0, 0), desc="Locked Node")
    node.add_lock("enter", lambda x: getattr(x, "is_builder", False))
    node.add_lock("view", lambda x: True)

    grid.nodes[(0, 0)] = node
    area.grids[0] = grid
    handler.areas["LockTestArea"] = area

    # Save
    handler.save()

    # Load new handler
    new_handler = NodeHandler()

    # Verify Node and Locks
    assert "LockTestArea" in new_handler.areas
    restored_area = new_handler.areas["LockTestArea"]
    assert 0 in restored_area.grids
    restored_grid = restored_area.grids[0]
    assert (0, 0) in restored_grid.nodes
    restored_node = restored_grid.nodes[(0, 0)]

    # Verify structure
    assert "enter" in restored_node.locks
    assert "view" in restored_node.locks

    # Verify behavior
    # Use real Objects for access checks to satisfy type hints if needed,
    # or just objects with the right attributes.
    class MockAccessor:
        def __init__(self, is_builder=False, is_superuser=False):
            self.is_builder = is_builder
            self.is_superuser = is_superuser

    builder = MockAccessor(is_builder=True)
    player = MockAccessor(is_builder=False)

    assert restored_node.access(builder, "enter") is True
    assert restored_node.access(player, "enter") is False
    assert restored_node.access(player, "view") is True


def test_maphandler_save_init():
    """Test saving and loading MapHandler (mapdata)."""
    # Setup
    handler = MapHandler()

    # Create a MapInfo and set attributes (new API)
    map_info = MapInfo(name="TestMapHandlerArea")
    map_info.pre_grid = {(0, 0): ".", (1, 0): "#"}

    # MapHandler stores by (area_name, z)
    handler.data[("TestMapHandlerArea", 0)] = map_info

    # Save
    handler.save()

    # Verify file exists
    assert (TEST_SAVE_DIR / "mapdata").exists()

    # Load new handler
    new_handler = MapHandler()

    # Verify data restoration
    key = ("TestMapHandlerArea", 0)
    assert key in new_handler.data

    restored_map = new_handler.data[key]
    assert restored_map.name == "TestMapHandlerArea"
    assert restored_map.pre_grid == {(0, 0): ".", (1, 0): "#"}

    # Verify lock re-initialization
    assert restored_map.lock is not None
    assert new_handler.lock is not None
