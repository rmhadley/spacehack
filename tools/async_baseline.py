"""Loop-primitive baselines for doc 46 phase 1 (pre/post async A/B).

Drives the REAL pygame runtime under SDL's dummy video driver and
times the loop primitives the async conversion touches:

1. idle cadence  — wait_events(timeout_ms=200) x N with no events
   (the timeout poll path: 16 ms sleep per iteration)
2. throughput    — pre-posted KEYDOWNs drained through
   wait_events(timeout_ms=None) (the event.wait() path)

Run pre-conversion for the baseline and post-conversion with
--async for the A/B comparison. Numbers are recorded in
docs/design/in_progress/46_DESIGN_BROWSER_BUILD.md.
"""
import argparse
import asyncio
import os
import statistics
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

N_IDLE = 5
N_EVENTS = 100
IDLE_TIMEOUT_MS = 200


def _time_calls(fn, n):
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
    return samples


def _report(name, samples, unit="s"):
    total = statistics.mean(samples)
    print(f"{name}: mean {total:.4f}{unit}  min {min(samples):.4f}  "
          f"max {max(samples):.4f}  n={len(samples)}")
    return total


def measure_sync(context):
    import pygame

    idle = _time_calls(
        lambda: context.wait_events(timeout_ms=IDLE_TIMEOUT_MS), N_IDLE
    )
    idle_mean = _report("idle cadence (200ms timeout)", idle)

    for _ in range(N_EVENTS):
        pygame.event.post(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
        )
    t0 = time.perf_counter()
    for _ in range(N_EVENTS):
        context.wait_events(timeout_ms=None)
    wait_mean = (time.perf_counter() - t0) / N_EVENTS
    print(f"event throughput: {wait_mean * 1000:.3f} ms/event  n={N_EVENTS}")

    print(f"BASELINE[sync]  idle_mean={idle_mean:.4f}  "
          f"wait_ms_per_event={wait_mean * 1000:.3f}")


async def measure_async(context):
    import pygame

    idle = _time_calls(
        lambda: asyncio.run(context.wait_events(timeout_ms=IDLE_TIMEOUT_MS)),
        N_IDLE,
    )
    idle_mean = _report("idle cadence (200ms timeout)", idle)

    for _ in range(N_EVENTS):
        pygame.event.post(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
        )

    async def drain():
        t0 = time.perf_counter()
        for _ in range(N_EVENTS):
            await context.wait_events(timeout_ms=None)
        return (time.perf_counter() - t0) / N_EVENTS

    wait_mean = asyncio.run(drain())
    print(f"event throughput: {wait_mean * 1000:.3f} ms/event  n={N_EVENTS}")

    print(f"BASELINE[async]  idle_mean={idle_mean:.4f}  "
          f"wait_ms_per_event={wait_mean * 1000:.3f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--async", action="store_true", dest="use_async")
    args = parser.parse_args()

    from spacehack.engine import load_tileset
    from spacehack.pygame_runtime import open_runtime

    tileset = load_tileset()
    with open_runtime(tileset) as context:
        if args.use_async:
            asyncio.run(measure_async(context))
        else:
            measure_sync(context)


if __name__ == "__main__":
    main()
