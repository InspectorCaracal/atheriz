from typing import TYPE_CHECKING
from atheriz.settings import THREADPOOL_LIMIT
from atheriz.logger import logger
from threading import RLock

if TYPE_CHECKING:
    from atheriz.commands.loggedin.cmdset import LoggedinCmdSet
    from atheriz.singletons.asyncthreadpool import AsyncThreadPool
    from atheriz.commands.unloggedin.cmdset import UnloggedinCmdSet
    from atheriz.singletons.node import NodeHandler
    from atheriz.singletons.map import MapHandler
    from inflect import engine
    from atheriz.objects.base_channel import Channel

_ASYNC_THREAD_POOL: AsyncThreadPool | None = None
_UNLOGGEDIN_CMDSET: UnloggedinCmdSet | None = None
_LOGGEDIN_CMDSET: LoggedinCmdSet | None = None
_NODE_HANDLER: NodeHandler | None = None
_MAP_HANDLER: MapHandler | None = None
_SERVER_CHANNEL: Channel | None = None
# _INFLECT_ENGINE: engine | None = None


# def GetInflectEngine() -> engine:
#     global _INFLECT_ENGINE
#     if not _INFLECT_ENGINE:
#         from inflect import engine
#         _INFLECT_ENGINE = engine()
#     return _INFLECT_ENGINE

_ID_LOCK = RLock()
_ID = -1


def set_id(id: int) -> None:
    """Set the global ID to the given value."""
    with _ID_LOCK:
        global _ID
        _ID = id


def get_unique_id() -> int:
    """Get a unique ID."""
    with _ID_LOCK:
        global _ID
        _ID += 1
        return _ID


def get_server_channel() -> Channel | None:
    global _SERVER_CHANNEL
    if not _SERVER_CHANNEL:
        from atheriz.singletons.objects import filter_by_type

        c = filter_by_type("channel", lambda x: x.name.lower() == "server")
        if c:
            _SERVER_CHANNEL = c[0]
        else:
            logger.error("Server channel not found.")
    return _SERVER_CHANNEL


def get_map_handler() -> MapHandler:
    global _MAP_HANDLER
    if not _MAP_HANDLER:
        from atheriz.singletons.map import MapHandler

        _MAP_HANDLER = MapHandler()
    return _MAP_HANDLER


def get_loggedin_cmdset() -> LoggedinCmdSet:
    global _LOGGEDIN_CMDSET
    if not _LOGGEDIN_CMDSET:
        from atheriz.commands.loggedin.cmdset import LoggedinCmdSet

        _LOGGEDIN_CMDSET = LoggedinCmdSet()
    return _LOGGEDIN_CMDSET


def get_async_threadpool() -> AsyncThreadPool:
    global _ASYNC_THREAD_POOL
    if not _ASYNC_THREAD_POOL:
        from atheriz.singletons.asyncthreadpool import AsyncThreadPool

        _ASYNC_THREAD_POOL = AsyncThreadPool(THREADPOOL_LIMIT)
    return _ASYNC_THREAD_POOL


def get_unloggedin_cmdset() -> UnloggedinCmdSet:
    global _UNLOGGEDIN_CMDSET
    if not _UNLOGGEDIN_CMDSET:
        from atheriz.commands.unloggedin.cmdset import UnloggedinCmdSet

        _UNLOGGEDIN_CMDSET = UnloggedinCmdSet()
    return _UNLOGGEDIN_CMDSET


def get_node_handler() -> NodeHandler:
    global _NODE_HANDLER
    if not _NODE_HANDLER:
        from atheriz.singletons.node import NodeHandler

        _NODE_HANDLER = NodeHandler()
    return _NODE_HANDLER
