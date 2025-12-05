from obspy.clients.fdsn import Client
from obspy import UTCDateTime
import numpy as np
import sys

G = 9.81

FDSN_CLIENT = Client("http://192.168.11.250:8080")

NETWORK = "GO"
STATION = "SHTL"
CHANNEL_ACC = "HN*"
CHANNEL_VEL = "HH*"



# გამოყენება: python pga_calc.py "2024-07-22T08:08:09.660"
if len(sys.argv) > 1:
    origin_time_str = sys.argv[1]
else:
    origin_time_str = "2025-03-08 11:28:25.120"  # fallback/hardcode

ORIGIN_TIME = UTCDateTime(origin_time_str)
START_TIME = ORIGIN_TIME - 120
END_TIME = ORIGIN_TIME + 180

# --------------------------
# 1) პირდაპირი ACC არხებიდან
# --------------------------
acc_inventory = FDSN_CLIENT.get_stations(
    network=NETWORK,
    station=STATION,
    location="*",
    channel=CHANNEL_ACC,
    starttime=START_TIME,
    endtime=END_TIME,
    level="response"
)

acc_stream = FDSN_CLIENT.get_waveforms(
    NETWORK, STATION, "*", CHANNEL_ACC, START_TIME, END_TIME
)

acc_stream.remove_response(
    inventory=acc_inventory,
    output="ACC",
    pre_filt=[0.1, 0.2, 30.0, 40.0],
    zero_mean=True,
    water_level=0.0
)

acc_stream.filter(
    "bandpass",
    freqmin=1,
    freqmax=10.0,
    corners=4,
    zerophase=True,
)

print("=== PGA from ACC channels (HN*) ===")
for tr in acc_stream:
    g_acc = tr.data / G
    max_g = np.max(np.abs(g_acc))
    pga_percent = max_g * 100   # %g
    print(f"{tr.id} : {max_g:.6f} g  PGA: ({pga_percent:.2f} %g)")

# --------------------------
# 2) VEL არხებიდან დიფერენცირებით
# --------------------------
vel_inventory = FDSN_CLIENT.get_stations(
    network=NETWORK,
    station='SHTL',
    location="*",
    channel=CHANNEL_VEL,
    starttime=START_TIME,
    endtime=END_TIME,
    level="response"
)

vel_stream = FDSN_CLIENT.get_waveforms(
    NETWORK, STATION, "*", CHANNEL_VEL, START_TIME, END_TIME
)

vel_stream.remove_response(
    inventory=vel_inventory,
    output="VEL",
    pre_filt=[0.1, 0.2, 30.0, 40.0],
    zero_mean=True,
    water_level=0.0
)

vel_stream.detrend("linear")
vel_stream.detrend("demean")
vel_stream.filter("bandpass", freqmin=1, freqmax=10.0, corners=4, zerophase=True)

print("\n=== PGA from VEL channels (HH*) -> ACC (d/dt) ===")
for tr in vel_stream:
    tr.differentiate()  # ახლა tr.data უკვე ACC (m/s²)-ია
    acc = tr.data
    max_acc = np.max(np.abs(acc))
    max_g = max_acc / G
    pga_percent = max_g * 100
    print(f"{tr.id} -> PGA: {max_g:.6f} g PGA: ({pga_percent:.2f} %g)")