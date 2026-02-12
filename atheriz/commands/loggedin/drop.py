from atheriz.commands.base_cmd import Command
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from atheriz.objects.base_obj import Object
    from atheriz.singletons.node import Node


class DropCommand(Command):
    key = "drop"
    desc = "Drop an object."

    def setup_parser(self):
        self.parser.add_argument("object", type=str, help="object to drop or all", nargs="*")

    # pyrefly: ignore
    def run(self, caller: Object, args):
        if not args:
            caller.msg(self.print_help())
            return
        loc: Node | None = caller.location
        if not loc:
            caller.msg("You can't drop something here!")
            return
        if not loc.access(caller, "put"):
            caller.msg("You can't drop something here!")
            return
        if args.object:
            obj = " ".join(args.object)
            if obj == "all":
                for obj in list(caller.contents):
                    obj.move_to(loc)
                    loc.msg_contents(
                        text=(f"{caller.name} dropped {obj.name}.", {"type": "drop"}),
                        from_obj=caller,
                        exclude=caller,
                    )
                    caller.msg(f"You dropped: {obj.name}")
                return
            found = caller.search(obj)
            if not found:
                caller.msg("Object not found.")
                return
            for f in found:
                f.move_to(loc)
                loc.msg_contents(
                    text=(f"{caller.name} dropped {f.name}.", {"type": "drop"}),
                    from_obj=caller,
                    exclude=caller,
                )
                caller.msg(f"You dropped: {f.name}")
        else:
            caller.msg(self.print_help())
