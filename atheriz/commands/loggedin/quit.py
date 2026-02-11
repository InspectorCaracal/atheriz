from atheriz.commands.base_cmd import Command
from atheriz.websocket import websocket_manager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from atheriz.objects.base_obj import Object
    from atheriz.websocket import Connection


class QuitCommand(Command):
    key = "quit"
    desc = "Quit."
    use_parser = False

    # pyrefly: ignore
    def run(self, caller: Object, args):
        caller.msg("Goodbye!")
        connection: Connection = caller.session.connection
        connection.close()
