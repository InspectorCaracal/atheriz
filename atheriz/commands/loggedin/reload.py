from atheriz.commands.base_cmd import Command
from atheriz.reloader import reload_game_logic
from atheriz.singletons.get import get_server_channel
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from atheriz.objects.base_obj import Object
    from atheriz.websocket import Connection
    from atheriz.objects.base_channel import Channel


class ReloadCommand(Command):
    key = "reload"
    desc = "Reload game logic and modules."
    use_parser = False

    def access(self, caller: Object | Connection) -> bool:
        return caller.is_superuser

    def run(self, caller: Object | Connection, args):
        channel: Channel | None = get_server_channel()
        if channel:
            channel.msg("Server is reloading...")
        result = reload_game_logic()
        if channel:
            channel.msg(f"{result}")
        else:
            caller.msg(f"{result}")
