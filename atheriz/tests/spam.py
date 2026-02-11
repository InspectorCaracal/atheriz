import asyncio
import json
import random
import time
import statistics
import websockets
from pathlib import Path

# Configuration
URI = "ws://127.0.0.1:8000/ws"
SPAM_ACCOUNTS_FILE = Path(__file__).parent.parent.parent / "save" / "spam_accounts.txt"
MOVEMENT_INTERVAL = 1.0  # seconds between movement commands
DIRECTIONS = ["n", "s", "e", "w"]
CHARACTER_SELECT_DELAY = 0.1  # seconds to wait before selecting character
# BUILD_COMMANDS = [
#     "build --room --double -n",
#     "build --room --double -e",
#     "build --room --double -s",
#     "build --room --double -w",
# ]
BUILD_COMMANDS = [
    "n",
    "s",
    "e",
    "w",
]


class SpamClient:
    """Represents a single spam client connection."""

    # Map full direction names to short commands
    DIRECTION_MAP = {
        "north": "n",
        "south": "s",
        "east": "e",
        "west": "w",
        "northeast": "ne",
        "northwest": "nw",
        "southeast": "se",
        "southwest": "sw",
        "up": "u",
        "down": "d",
    }

    def __init__(self, account_name: str, password: str, char_name: str):
        self.account_name = account_name
        self.password = password
        self.char_name = char_name
        self.websocket = None
        self.connected = False
        self.in_game = False
        self.pending_command = None
        self.pending_time = None
        self.last_response_time = 0.0
        self.available_exits: list[str] = []  # Available exit directions
        self.disconnect_reason = None
        self._recv_task = None
        self.rtt_results = []  # Internal list to store RTTs

    def parse_exits(self, text: str):
        """Parse available exits from room description text."""
        # Reset available exits so we don't get stuck with stale ones
        self.available_exits = []

        # Look for "Exits:" or "exits:" followed by direction names
        text_lower = text.lower()
        if "exits:" in text_lower or "exit:" in text_lower:
            # Find the exits section
            for line in text.split("\n"):
                if "exit" in line.lower():
                    # Extract directions from this line
                    exits = []
                    for full_name, short in self.DIRECTION_MAP.items():
                        if full_name in line.lower():
                            exits.append(short)
                    if exits:
                        self.available_exits = exits
                        return

        # Fallback: look for cardinal directions anywhere in text
        exits = []
        for full_name, short in self.DIRECTION_MAP.items():
            if full_name in text_lower:
                exits.append(short)
        if exits:
            self.available_exits = exits

    def get_random_exit(self) -> str | None:
        """Get a random available exit direction."""
        if self.available_exits:
            return random.choice(self.available_exits)
        # Fallback to cardinal directions if no exits parsed
        return random.choice(["n", "s", "e", "w"])

    async def send_random_build(self):
        """Send a random build command after logging in."""
        try:
            build_cmd = random.choice(BUILD_COMMANDS)
            payload = json.dumps(["text", [build_cmd], {}])
            await self.websocket.send(payload)
        except Exception as e:
            print(f"Error sending build command for {self.account_name}: {e}")

    async def connect(self) -> bool:
        """Establish websocket connection."""
        try:
            self.websocket = await websockets.connect(URI, ping_timeout=60)
            self.connected = True
            return True
        except Exception as e:
            print(f"Failed to connect {self.account_name}: {e}")
            return False

    async def recv_loop(self):
        """Dedicated receive loop to drain the websocket buffer quickly."""
        try:
            while self.connected:
                try:
                    response = await self.websocket.recv()
                    self.last_response_time = time.time()

                    if self.pending_time:
                        rtt = (time.perf_counter() - self.pending_time) * 1000
                        self.rtt_results.append(rtt)
                        self.pending_time = None

                    data = json.loads(response)
                    if isinstance(data, list) and len(data) >= 2:
                        msg_type = data[0]
                        if msg_type == "text" and data[1]:
                            msg_text = data[1][0] if data[1] else ""
                            self.parse_exits(msg_text)
                        elif msg_type == "logged_in":
                            self.in_game = True
                except websockets.exceptions.ConnectionClosed as e:
                    self.connected = False
                    self.disconnect_reason = f"connection closed: {e}"
                    break
                except Exception as e:
                    # Generic error in loop
                    pass
        finally:
            self.connected = False
            self.in_game = False

    async def login(self) -> bool:
        """Send login command and wait for response."""
        if not self.connected:
            return False

        try:
            # Send connect command
            cmd = f"connect {self.account_name} {self.password}"
            payload = json.dumps(["text", [cmd], {}])
            await self.websocket.send(payload)

            # Wait for response
            while True:
                try:
                    response = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
                    data = json.loads(response)
                    if isinstance(data, list) and len(data) >= 2:
                        if data[0] == "text":
                            msg_text = data[1][0] if data[1] else ""
                            # Look for character selection prompt
                            if (
                                "select a character" in msg_text.lower()
                                or "0:" in msg_text
                                or self.char_name in msg_text
                            ):
                                return True
                            if "invalid" in msg_text.lower() or "error" in msg_text.lower():
                                print(f"Login failed for {self.account_name}: {msg_text}")
                                return False
                except asyncio.TimeoutError:
                    print(f"Login timeout for {self.account_name}")
                    return False
        except Exception as e:
            print(f"Error during login for {self.account_name}: {e}")
            return False

    async def select_character(self) -> bool:
        """Select the first character (index 0)."""
        if not self.connected:
            return False

        try:
            # Wait a fraction of a second
            await asyncio.sleep(CHARACTER_SELECT_DELAY)

            # Send "0" to select first character
            payload = json.dumps(["text", ["0"], {}])
            await self.websocket.send(payload)

            # Wait for response indicating we're in the game
            while True:
                try:
                    response = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
                    data = json.loads(response)
                    if isinstance(data, list) and len(data) >= 2:
                        if data[0] == "text":
                            msg_text = data[1][0] if data[1] else ""
                            # Parse exits from room description
                            self.parse_exits(msg_text)
                            # Look for room description or welcome message
                            if (
                                "exits" in msg_text.lower()
                                or "you are" in msg_text.lower()
                                or len(msg_text) > 50
                            ):
                                self.in_game = True
                                await self.send_random_build()
                                return True
                        elif data[0] == "logged_in":
                            self.in_game = True
                            await self.send_random_build()
                            return True
                except asyncio.TimeoutError:
                    # Assume we're in if we got this far
                    self.in_game = True
                    await self.send_random_build()
                    return True
        except Exception as e:
            print(f"Error selecting character for {self.account_name}: {e}")
            return False
        finally:
            if self.in_game and self.connected:
                # Start background receive task once we are fully in game
                self._recv_task = asyncio.create_task(self.recv_loop())

    async def close(self):
        """Close the websocket connection."""
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
        if self.websocket:
            try:
                await asyncio.wait_for(self.websocket.close(), timeout=1.0)
            except:
                pass
        self.connected = False
        self.in_game = False


def load_accounts() -> list[tuple[str, str, str]]:
    """Load accounts from spam_accounts.txt."""
    accounts = []

    if not SPAM_ACCOUNTS_FILE.exists():
        print(f"Error: {SPAM_ACCOUNTS_FILE} not found.")
        print("Run 'spam <count>' command in-game first to create accounts.")
        return accounts

    with open(SPAM_ACCOUNTS_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) >= 3:
                accounts.append((parts[0], parts[1], parts[2]))

    return accounts


async def movement_worker(
    client: SpamClient,
    rtt_list: list,
    stop_event: asyncio.Event,
    error_count: list,
    disconnect_log: list,
):
    """
    Worker task for a single client.
    Sends random movement command every second and records RTT.
    """
    while not stop_event.is_set() and client.in_game:
        start_loop = time.perf_counter()

        # Pull any new RTTs from the client's internal list
        while client.rtt_results:
            rtt_list.append(client.rtt_results.pop(0))

        # Choose random build command
        # Mix movement and build
        # if random.random() < 0.7:
        #      cmd = client.get_random_exit()
        # else:
        #      cmd = random.choice(BUILD_COMMANDS)
        cmd = random.choice(BUILD_COMMANDS)

        payload = json.dumps(["text", [cmd], {}])

        # Record pending command
        client.pending_command = cmd
        client.pending_time = time.perf_counter()

        try:
            await client.websocket.send(payload)
        except websockets.exceptions.ConnectionClosed as e:
            client.disconnect_reason = f"send connection closed: {e}"
            disconnect_log.append(f"{client.account_name}: {client.disconnect_reason}")
            client.in_game = False
            return
        except Exception as e:
            error_count.append(1)
            client.disconnect_reason = f"send error: {type(e).__name__}: {e}"

        elapsed = time.perf_counter() - start_loop
        target_interval = random.uniform(0.5, 1.5)
        sleep_time = max(0.0, target_interval - elapsed)
        if stop_event.is_set():
            break
        await asyncio.sleep(sleep_time)


async def print_stats_periodically(
    rtt_list: list, stop_event: asyncio.Event, active_clients: list, error_count: list
):
    """Print stats every 5 seconds."""
    last_count = 0
    last_error_count = 0

    while not stop_event.is_set():
        await asyncio.sleep(5.0)

        if stop_event.is_set():
            break

        current_count = len(rtt_list)
        new_samples = current_count - last_count
        last_count = current_count

        last_count = current_count

        now = time.time()
        in_game_count = sum(1 for c in active_clients if c.in_game)
        # Consider active if response received in last 10 seconds
        really_active_count = 0
        stalled_clients = []
        for c in active_clients:
            if c.in_game:
                if now - c.last_response_time < 10.0:
                    really_active_count += 1
                else:
                    stalled_clients.append(c)

        if stalled_clients:
            print(f"\n[Debug] {len(stalled_clients)} stalled clients. Sample:")
            for c in stalled_clients[:3]:  # Show first 3 stalled
                waited = now - c.last_response_time
                print(
                    f"  {c.account_name}: Last response {waited:.1f}s ago. Pending cmd: {c.pending_command} (sent {now - c.pending_time:.1f}s ago)"
                )

        current_errors = len(error_count)
        new_errors = current_errors - last_error_count
        last_error_count = current_errors

        if rtt_list:
            recent = rtt_list[-100:] if len(rtt_list) > 100 else rtt_list
            print(
                f"\n[Stats] Active: {really_active_count}/{in_game_count} | Samples: {current_count} (+{new_samples}) | Errors: {current_errors} (+{new_errors}) | "
                f"Min: {min(recent):.1f}ms | Max: {max(recent):.1f}ms | Avg: {statistics.mean(recent):.1f}ms"
            )
        else:
            print(
                f"\n[Stats] Active: {really_active_count}/{in_game_count} | Errors: {current_errors} | No samples yet..."
            )


async def spam_test():
    """Main spam test function."""
    # Load accounts
    accounts = load_accounts()
    if not accounts:
        return

    print(f"Loaded {len(accounts)} accounts from {SPAM_ACCOUNTS_FILE}")

    clients = []
    rtts = []
    errors = []
    disconnect_log = []
    stop_event = asyncio.Event()
    tasks = []

    try:
        # Phase 1: Connect all clients
        print(f"\nPhase 1: Connecting {len(accounts)} clients...")
        for i, (account, password, char) in enumerate(accounts, 1):
            client = SpamClient(account, password, char)
            if await client.connect():
                clients.append(client)
            if i % 50 == 0:
                print(f"Connected: {len(clients)}/{i}")

        print(f"Established {len(clients)} connections.")

        # Phase 2: Login all clients
        print(f"\nPhase 2: Logging in {len(clients)} clients...")
        logged_in = 0
        for i, client in enumerate(clients, 1):
            if await client.login():
                logged_in += 1
            if i % 50 == 0:
                print(f"Logged in: {logged_in}/{i}")

        print(f"Logged in {logged_in} clients.")

        # Phase 3: Select characters
        print(f"\nPhase 3: Selecting characters...")
        in_game = 0
        for i, client in enumerate(clients, 1):
            if await client.select_character():
                in_game += 1
            if i % 50 == 0:
                print(f"In game: {in_game}/{i}")

        print(f"{in_game} clients now in game.")

        if in_game == 0:
            print("No clients made it into the game. Aborting.")
            return

        # Phase 4: Movement test
        print(f"\nPhase 4: Starting movement test (Ctrl+C to stop)...")
        print("Clients will send random n/s/e/w commands with 0.5-1.5s interval.")
        print("Stats will be printed every 5 seconds.\n")

        # Start movement workers for all in-game clients
        for client in clients:
            if client.in_game:
                tasks.append(
                    asyncio.create_task(
                        movement_worker(client, rtts, stop_event, errors, disconnect_log)
                    )
                )

        # Start stats printer
        stats_task = asyncio.create_task(
            print_stats_periodically(rtts, stop_event, clients, errors)
        )
        tasks.append(stats_task)

        # Run until interrupted
        try:
            while True:
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            pass

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")

    finally:
        # Set stop event
        stop_event.set()

        # Wait for tasks to finish
        if tasks:
            print("Cleaning up tasks...")
            await asyncio.sleep(0.5)
            for task in tasks:
                task.cancel()

        # Print final stats
        print("\n" + "=" * 50)
        print("FINAL RESULTS")
        print("=" * 50)
        print(f"Total Clients: {len(clients)}")
        print(f"Clients In Game: {sum(1 for c in clients if c.in_game)}")
        print(f"Total RTT Samples: {len(rtts)}")

        if rtts:
            print(f"\nLatency Statistics:")
            print(f"  Min: {min(rtts):.2f}ms")
            print(f"  Max: {max(rtts):.2f}ms")
            print(f"  Avg: {statistics.mean(rtts):.2f}ms")
            if len(rtts) > 1:
                print(f"  Stdev: {statistics.stdev(rtts):.2f}ms")

            rtts.sort()
            if len(rtts) >= 100:
                p50 = rtts[int(len(rtts) * 0.5)]
                p95 = rtts[int(len(rtts) * 0.95)]
                p99 = rtts[int(len(rtts) * 0.99)]
                print(f"\nPercentiles:")
                print(f"  p50: {p50:.2f}ms")
                print(f"  p95: {p95:.2f}ms")
                print(f"  p99: {p99:.2f}ms")

        # Print disconnect reasons if any
        if disconnect_log:
            print(f"\nDisconnection Log (showing first 20):")
            for reason in disconnect_log[:20]:
                print(f"  {reason}")
            if len(disconnect_log) > 20:
                print(f"  ... and {len(disconnect_log) - 20} more")

        # Close all connections in parallel
        print("\nClosing connections...")
        if clients:
            close_tasks = []
            for client in clients:
                close_tasks.append(client.close())
            await asyncio.gather(*close_tasks, return_exceptions=True)

        print("Done.")


if __name__ == "__main__":
    try:
        asyncio.run(spam_test())
    except KeyboardInterrupt:
        pass
