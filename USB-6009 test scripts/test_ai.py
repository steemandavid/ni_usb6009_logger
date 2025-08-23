import nidaqmx

# Change "Dev1/ai0" to match your device name in NI MAX
with nidaqmx.Task() as task:
    task.ai_channels.add_ai_voltage_chan("Dev1/ai0")
    value = task.read()
    print(f"AI0 = {value:.3f} V")
