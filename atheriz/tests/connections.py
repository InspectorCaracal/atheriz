import asyncio
import json
import random
import string
import time
import statistics
import websockets
import sys

CONNECTION_LIMIT = 5000
URI = "ws://127.0.0.1:8000/ws"
DURATION = 10.0  # seconds


def generate_random_string(length=10):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


async def worker(websocket, rtt_list, stop_event):
    """
    Worker task for a single connection.
    Sends 1 command/sec and records RTT until stop_event is set.
    """
    cmd_str = generate_random_string()
    payload = json.dumps(["text", [cmd_str], {}])

    while not stop_event.is_set():
        start_loop = time.perf_counter()

        # Send command
        t0 = time.perf_counter()
        try:
            await websocket.send(payload)

            # Wait for response
            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(response)
                    if isinstance(data, list) and len(data) >= 2:
                        if data[0] == "text":
                            msg_text = data[1][0] if data[1] else ""
                            if f"unknown command: {cmd_str.lower()}" in msg_text.lower():
                                t1 = time.perf_counter()
                                rtt = (t1 - t0) * 1000  # ms
                                rtt_list.append(rtt)
                                break  # Success, move to next cycle
                        # Ignore other messages (e.g. broadcasts, logged_in)
                except asyncio.TimeoutError:
                    # print("Timeout in worker")
                    break
                except Exception as e:
                    # print(f"Error in worker recv: {e}")
                    break
        except Exception as e:
            # print(f"Error in worker send: {e}")
            break

        # Maintain 1 second interval
        elapsed = time.perf_counter() - start_loop
        sleep_time = max(0, 1.0 - elapsed)
        if stop_event.is_set():
            break
        await asyncio.sleep(sleep_time)


async def stress_test():
    connections = []
    rtts = []

    print(f"Starting connection stress test to {URI}...")
    print(f"Phase 1: Establishing {CONNECTION_LIMIT} connections...")

    start_time = time.time()

    try:
        # Phase 1: Connect
        for i in range(1, CONNECTION_LIMIT + 1):
            try:
                websocket = await websockets.connect(URI, ping_interval=None)
                # disable ping_interval to avoid extra traffic logic if not needed, or keep default
                connections.append(websocket)
                if i % 100 == 0:
                    print(f"Connected: {i}/{CONNECTION_LIMIT}")
            except Exception as e:
                print(f"Failed to connect at iteration {i}: {e}")
                # Don't break, try to continue with what we have? or break?
                # User might want 5000 exactly. Let's try to get as many as possible.
                pass

        print(f"established {len(connections)} connections. Starting load test for {DURATION}s...")

        # Phase 2: Load Test
        stop_event = asyncio.Event()
        tasks = []
        for ws in connections:
            tasks.append(asyncio.create_task(worker(ws, rtts, stop_event)))

        # Run for DURATION
        await asyncio.sleep(DURATION)

        # Stop
        stop_event.set()
        print("Stopping workers...")
        await asyncio.gather(*tasks)

    except KeyboardInterrupt:
        print("\nTest interrupted by user.")

    final_time = time.time()

    print("\n--- Test Results ---")
    print(f"Total Connections: {len(connections)}")
    print(f"Total RTT Samples: {len(rtts)}")

    if rtts:
        print(f"Min RTT: {min(rtts):.2f}ms")
        print(f"Max RTT: {max(rtts):.2f}ms")
        print(f"Avg RTT: {statistics.mean(rtts):.2f}ms")
        if len(rtts) > 1:
            print(f"Stdev RTT: {statistics.stdev(rtts):.2f}ms")

        # Analyze distribution if many samples
        # Simple percentile?
        rtts.sort()
        p50 = rtts[int(len(rtts) * 0.5)]
        p95 = rtts[int(len(rtts) * 0.95)]
        p99 = rtts[int(len(rtts) * 0.99)]
        print(f"p50: {p50:.2f}ms")
        print(f"p95: {p95:.2f}ms")
        print(f"p99: {p99:.2f}ms")

    # Close all
    print("Closing connections...")
    for ws in connections:
        await ws.close()


if __name__ == "__main__":
    # Check if server is running? The test assumes it is.
    try:
        asyncio.run(stress_test())
    except KeyboardInterrupt:
        pass
