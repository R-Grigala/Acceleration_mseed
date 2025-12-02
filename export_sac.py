from obspy import UTCDateTime
from obspy.clients.fdsn import Client
import os

# სკრიპტის სამუშაო დირექტორია
SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))

FDSN_CLIENT = Client("http://192.168.11.250:8080")

ORIGIN_TIME = UTCDateTime("2024-07-22T08:08:09.660")
START_TIME = ORIGIN_TIME - 120
END_TIME  = ORIGIN_TIME + 180

NETWORK = "GO"
STATION = "MTAG"
LOCATIONS = "*"
CHANNEL_ACC = "HN*"
CHANNEL_VEL = "HH*"

# დროებითი ფაილების დირექტორია
TEMP_DIR = os.path.join(SCRIPT_PATH, "export")
os.makedirs(TEMP_DIR, exist_ok=True)

# 1) RESPONSE ამოღება
acc_inventory = FDSN_CLIENT.get_stations(
    network=NETWORK,
    station=STATION,
    location=LOCATIONS,
    channel=CHANNEL_ACC,
    starttime=START_TIME,
    endtime=END_TIME,
    level="response"
)

# 2) RAW ტრეისის გამოთხოვა
acc_stream = FDSN_CLIENT.get_waveforms(
    NETWORK, STATION, LOCATIONS, CHANNEL_ACC, START_TIME, END_TIME
)

# 3) RESPONSE-ის მოშლა → ACC იმპულსური რეაქცია
acc_stream.remove_response(
    inventory=acc_inventory,
    output="ACC",
    pre_filt=[0.1, 0.2, 30.0, 40.0],
    zero_mean=True,
    water_level=0.0
)

# 4) ფილტრი
acc_stream.filter(
    "bandpass",
    freqmin=1,
    freqmax=10.0,
    corners=4,
    zerophase=True,
)

# 5) შენახვა SAC ფორმატში
for tr in acc_stream:
    sac_filename = os.path.join(TEMP_DIR, f"{tr.id}_{START_TIME.strftime('%Y%m%d%H%M%S')}.SAC")
    tr.write(sac_filename, format="SAC")

    print("Saved:", sac_filename)


# --------------------------
# 2) VEL არხებიდან დიფერენცირებით
# --------------------------
vel_inventory = FDSN_CLIENT.get_stations(
    network=NETWORK,
    station=STATION,
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

vel_stream.filter("bandpass", freqmin=1, freqmax=10.0, corners=4, zerophase=True)

# 5) შენახვა SAC ფორმატში
for tr in vel_stream:
    sac_filename = os.path.join(TEMP_DIR, f"{tr.id}_{START_TIME.strftime('%Y%m%d%H%M%S')}.SAC")
    tr.write(sac_filename, format="SAC")

    print("Saved:", sac_filename)
