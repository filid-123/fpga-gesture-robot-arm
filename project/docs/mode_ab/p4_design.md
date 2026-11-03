# AB p4 development contract — 2026-10-30

Status: implementation contract; release evidence is in the package validation summary.
Physical testing remains NOT_RUN. Original p3/a8 and rollback remain intact.

## Confirmed scope

- Human confirmed B follows Giao per-phase speed/time law; A unchanged.
- Giao fast references are 1d3fa84d. New full-workspace policy is reviewed
  3d66aeb8 from origin/codex/mode-b-full-workspace-20261030.
- B retains hand delivery, two HOMEs, shared red inventory, PL digit selection,
  PRE/PALM and FIST policies. The latest user-authorized full rectangle replaces
  the historical empirical anchor radii; mechanical and geometry limits remain.
- Human confirmed whole-PL structural wrappers, retain original BIT. A subsequent
  clarification explicitly permits a NEW BIT for functional B fast support.
- No unattended camera, JTAG, actuator or physical test. All new hardware NOT_RUN.

## Diagnosed differences

- Latest field ab_20261030_115055: one red task committed then FIST-returned;
  43 background red failures have 0.242–0.267 mm residual against the host's
  artificial 0.05 mm local-TCP condition. This is not the source-radius gate.
- One canister mask fit was rejected at 9.8078% residual vs frozen 9%; preserve
  model/metric gates and distinguish them from IK/domain failures.
- p3 regenerated transport/placement then split into stop/start quintics and
  applied A limits; it does not reproduce Giao's reference time law.
- p3 replaced Giao's class-specific corrected release TCP by common H=(285,195,175).
  Giao central red TCP is approximately (278.23,190.84,163.90), eraser
  (285.93,195.07,172.91), canister (280.89,192.23,174.17). Preserve corrected
  attachment/placement semantics for hand delivery; do not erase corrections.
- Existing UART template has literal spd/acc and S4 blocks host writes while it
  owns the task. Python-only changes cannot reproduce per-phase Giao commands.

## Structural layer

12 wrappers in native_motion/rtl/wrappers consolidate 34 existing instances
across vision, AXI ownership, task control, hand target, actuator and display.
No new procedural statements or state are introduced by this extraction.
scripts/verify_pl_wrappers.py inlines identity port/parameter bindings and checks
the complete concurrent AST against the saved four original parents. First
pure-wrapper proof PASSED. This proof precedes functional B changes and must
never be presented as proof that NEW B functionality equals the old design.

Deliver exact hierarchy/port mapping plus editable Draw.io, SVG, PDF and PNG;
show actual RAM/ROM/FIFO/arithmetic/FSM/CDC/protocol blocks and clock boundaries.

## Functional B implementation direction

Use original Giao phase samples and T106 events as the numerical reference.
At each empirical anchor the reference samples/timing/speed/events must match;
new sources use Giao's updated bounded adaptive source IK. Preserve the checked
joint chords for the source adaptation; regenerate and check its INNER connector.
Keep each class correction applied exactly once.
Keep original corrected release geometry. Human hand is the destination;
the old physical support fixture is absent.

The existing P2P-only stop/start conversion cannot exactly represent arbitrary
PCHIP reference phases. Implement bounded PL program playback under S4 ownership
with frame timing and reverse/cancel handling, preserving the A path.
Implemented storage: absolute Q16 positions encoded as six signed 18-bit offsets
from six programmable Q16 bases, up to 2048 points, six true dual-port 18x2048
BRAMs. Class routes span less than 4 rad per channel; reject overflow. This keeps
Q16 precision and supports random-access three-bank hand interpolation. Phase
descriptors and speed profiles live in small LUTRAM. Validate actual Vivado
utilization against 85%; do not assume mapping/resource success.

Guarded bulk program loading/readback uses 0x43C20000 / ABI B001 and TASK340E;
the root s_axi_route connects through the actual fifth SmartConnect master.
Data are immutable after
COMMIT. Phase descriptors distinguish T102/T106, period, speed/acc profile and
reverse gripper profile. Old A P2P, FIFO, limits, watchdog and D5 behavior remain.
New formatter DEC scalar channels 6/7 and additional T102/T106 programs fit the
existing 256-word template RAM: original A command 91 words + query11,
new T102 at112 and T106 at208 (<256). Keep A literal program and
request addresses unchanged. B context is latched before mapping/check/TX.
Native segments require both flags[7] and profile=0, avoiding old A settling
flags. A completed native ownership fence returns the sample source to host P2P
for the fixed B-to-A HOME transition; the acknowledgement is consumed first.

Before release verify native phase vectors, compressed decode, bank interpolation,
real formatter bytes, packet/period backpressure, FIST before/after release,
partial reverse, no host mutation during motion, A regression, full synthesis,
timing/CDC/resource/DRC and same-build artifact hashes. New physical acceptance
and true latency remain NOT_RUN until supervised testing.
