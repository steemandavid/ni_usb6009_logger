import sys, nidaqmx
from nidaqmx.system import System
from nidaqmx.constants import TerminalConfiguration

print("✅ nidaqmx imported. Scanning for devices...")
sys_obj = System.local()
devs = list(sys_obj.devices)

if not devs:
    print("❌ No NI-DAQmx devices found. Check USB/cable, drivers, or NI MAX.")
    sys.exit(1)

print("Found devices:")
for d in devs:
    try:
        print(f" - {d.name}: {d.product_type}")
    except Exception as e:
        print(f" - (error reading device info): {e}")

# Pick the first device by default; change if needed
dev = devs[0]
phys_chan = f"{dev.name}/ai0"
print(f"\nTrying single on-demand read from {phys_chan} (RSE, ±10 V) with 1s timeout...")

try:
    with nidaqmx.Task() as task:
        task.ai_channels.add_ai_voltage_chan(
            phys_chan,
            min_val=-10.0,
            max_val=10.0,
            terminal_config=TerminalConfiguration.RSE
        )
        v = task.read(timeout=1.0)     # <-- will raise after 1 second if it can’t read
        print(f"✅ Read OK: {phys_chan} = {v:.6f} V")
except Exception as e:
    print("❌ Read failed with exception:")
    print(repr(e))
