import sys, os
from obspy.clients.fdsn import Client
from obspy import UTCDateTime
import numpy as np
import logging
from logging.handlers import RotatingFileHandler
import csv

# სკრიპტის სამუშაო დირექტორია
SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))

# მიწისძვრის დრო, რომელიც გადაეცემა როგორც არგუმენტი
EVENT_ID = sys.argv[1]
LATITUDE = sys.argv[2]
LONGITUDE = sys.argv[3]
ORIGIN_TIME = UTCDateTime(sys.argv[4])

START_TIME = ORIGIN_TIME - 120  # 120 წამით ადრე
END_TIME = ORIGIN_TIME + 180  # 180 წამით გვიან

# დროებითი ფაილების დირექტორია
TEMP_DIR = f"{SCRIPT_PATH}/temp"
os.makedirs(TEMP_DIR, exist_ok=True)

# ლოგ ფაილების მისამართი
LOGS_DIR_PATH = f"{SCRIPT_PATH}/logs"
os.makedirs(LOGS_DIR_PATH, exist_ok=True)

# ლოგირების კონფიგურაცია
LOG_FILENAME = f'{LOGS_DIR_PATH}/print_acc.log'
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 3  # მაქსიმუმ 3 სარეზერვო ლოგ ფაილი

# ლოგ ფაილის როტაციის კონფიგურაცია
rotating_handler = RotatingFileHandler(LOG_FILENAME, maxBytes=MAX_LOG_SIZE, backupCount=BACKUP_COUNT)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
rotating_handler.setFormatter(formatter)

# ლოგერის კონფიგურაცია
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logger.addHandler(rotating_handler)

# სეისმური სადგურის მონაცემების მისაღები სერვერი
FDSN_CLIENT = Client("http://10.0.0.249:8080")

STATION_DICT = {'AKHA':'AKHN', 'ALIA':'ALIG', 'KHMA':'KHMG', 'LGDA':'LGDN', 'LPNA':'LPNG', 'MUGA':'MUGD', 'SHTA':'SHTL', 'VSHA':'VSHL'}
REVERSED_STATION_DICT = {value: key for key, value in STATION_DICT.items()}
CHANNEL_DICT = {'HHE':'HNE', 'HHN':'HNN', 'HHZ':'HNZ'}
EXPORT_ST_VELOCITY = set()
CHANNEL_VEL = 'HH*'
UNIT_VEL = "VEL"

MORE_G_THRESHOLD = {}
STANDALONE_STATIONS = ['BTNK', 'SC07', 'S007', 'S185', 'S186', 'SEAG', 'SHTB']

# მონაცემების პარამეტრები
NETWORK = 'GO'
STATIONS = '*'
LOCATION = '*'
CHANNEL_ACC = 'HN*'
UNIT_ACC = "ACC"
G_THRESHOLD = 0.001  # G ერთეულში

# ASCII ფაილის შენახვის ფუნქცია სწორი ჰედერით
def write_trace_as_ascii(tr, file_path, unit_code="VEL"):
    unit_map = {
        "VEL": "m/s",
        "ACC": "m/s**2"
    }
    unit_str = unit_map.get(unit_code.upper(), unit_code)

    starttime = tr.stats.starttime
    sampling_rate = tr.stats.sampling_rate
    npts = tr.stats.npts
    channel = tr.stats.channel
    network = tr.stats.network
    original_station = REVERSED_STATION_DICT.get(tr.stats.station, tr.stats.station)
    location = tr.stats.location or ""
    filename_id = f"{network}_{original_station}_{location}_{channel}_D".strip("_")

    # ჰედერის და მონაცემების ჩაწერა
    with open(file_path, "w") as f:
        header = (
            f"TIMESERIES {filename_id}, {npts} samples, {int(sampling_rate)} sps, "
            f"{starttime.strftime('%Y-%m-%dT%H:%M:%S.%f')}, TSPAIR, FLOAT, {unit_str}"
        )
        f.write(header + "\n")

        delta = 1.0 / sampling_rate
        for i, amp in enumerate(tr.data):
            current_time = starttime + i * delta
            f.write(f"{current_time.strftime('%Y-%m-%dT%H:%M:%S.%f')}  {amp:+.10e}\n")

# სიჩქარის მონაცემების ექსპორტის ფუნქცია
def export_velocity():
    if EXPORT_ST_VELOCITY:
        inventory_vel = FDSN_CLIENT.get_stations(network=NETWORK, station=STATIONS, location=LOCATION, channel=CHANNEL_VEL, starttime=START_TIME, endtime=END_TIME, level="response")
        for station in EXPORT_ST_VELOCITY:
            try:
                st_vel = FDSN_CLIENT.get_waveforms(NETWORK, station, LOCATION, CHANNEL_VEL, START_TIME, END_TIME)
                if len(st_vel) == 0:
                    logger.debug(f"არ არსებობს ჩანაწერი სადგურისთვის: {station}")
                    continue

                st_vel_inv = inventory_vel.select(network=NETWORK, station=station, channel=CHANNEL_VEL)

                if not st_vel_inv or len(st_vel_inv) == 0:
                    logger.warning(f"არ არის შესაბამისი response მონაცემები სადგურისთვის {station}. ვტოვებთ...")
                    continue

                st_vel.remove_response(inventory=st_vel_inv, output=UNIT_VEL.upper(), water_level=0.0)

                original_station = REVERSED_STATION_DICT.get(station, station)
                WORK_DIR = f'{TEMP_DIR}/{str(ORIGIN_TIME)[:4]}/{ORIGIN_TIME}/{original_station}'
                os.makedirs(WORK_DIR, exist_ok=True)
                logger.debug(f"ქვედირექტორია შექმნილია ან უკვე არსებობს: {WORK_DIR}")

                for tr in st_vel:
                    time = tr.times()
                    data = tr.data

                    acc_from_vel = np.gradient(data, time[1] - time[0])
                    max_acc_from_vel = np.max(np.abs(acc_from_vel))
                    max_g_from_vel = max_acc_from_vel / 9.81
                    # შენახვა MORE_G_THRESHOLD dict-ში
                    exported_key = f"{tr.stats.network}_{original_station}_{CHANNEL_DICT.get(tr.stats.channel)}"
                    MORE_G_THRESHOLD[exported_key]["acc_from_vel"].append(max_g_from_vel)
                    try:
                        filename = f'{ORIGIN_TIME}_{tr.stats.network}_{original_station}_{tr.stats.channel}'
                        st_file_path = os.path.join(WORK_DIR, f'{filename}.ascii')
                        logger.debug(f"ინახება: {st_file_path}")
                        write_trace_as_ascii(tr, st_file_path, unit_code=UNIT_VEL.upper())
                    except Exception as err:
                        logger.exception(f"შეცდომა ჩანაწერის ({original_station}) შენახვისას: {err}")
            except Exception as err:
                logger.warning(f"შეცდომა სადგურის ({station}) მონაცემების დამუშავებისას: {err}")
                continue
    else:
        logger.warning("არცერთი სადგურიდან არ ვიწერთ სიჩქარის მონაცემებს")

def collect_acceleration():
    try:
        # სადგურების ინფრომაციის წამოღება
        inventory = FDSN_CLIENT.get_stations(network=NETWORK, station=STATIONS, location=LOCATION, channel=CHANNEL_ACC, starttime=START_TIME, endtime=END_TIME, level="response")
        acceleration_data = []  # სიის შექმნა აჩქარების შესანახად

        for network in inventory:
            for station in network:
                try:
                    # თუ სადგურის კოდი არ არის, ვტოვებთ გამოტოვებით
                    if not station.code:
                        logger.warning("გამოტოვებულია სადგური, რომელსაც არ აქვს კოდი")
                        continue

                    # ვიღებთ ტალღის ფორმებს
                    st = FDSN_CLIENT.get_waveforms(NETWORK, station.code, LOCATION, CHANNEL_ACC, START_TIME, END_TIME)

                    if len(st) == 0:
                        logger.debug(f"არ არსებობს ჩანაწერი სადგურისთვის: {station.code}")
                        continue

                    # ვიღებთ სადგურის შესაბამის დეტალებს
                    station_inv = inventory.select(network=NETWORK, station=station.code, channel=CHANNEL_ACC)

                    if not station_inv or len(station_inv) == 0:
                        logger.warning(f"არ არის შესაბამისი response მონაცემები სადგურისთვის {station.code}. ვტოვებთ...")
                        continue

                    # ვშლით ინსტრუმენტულ პასუხს (response) და ვცვლით ერთეულს
                    st.remove_response(inventory=station_inv, output=UNIT_ACC.upper(), water_level=0.0)

                    export_station_data = False  # მონაცემების შენახვის საჭიროება
                    max_g = 0.0  # მაქსიმალური აჩქარების მნიშვნელობა

                    for tr in st:
                        g_acc = tr.data / 9.81  # აჩქარების გადაყვანა g ერთეულში
                        max_g = np.max(np.abs(g_acc))
                        logger.debug(f"სადგურზე {station.code} დაფიქსირდა აჩქარება G: {max_g}")

                        # ვამატებთ მონაცემს საბოლოო სიაში
                        acceleration_data.append(f"{tr.stats.network}_{tr.stats.station}_{tr.stats.channel}, {max_g}")
                        key = f"{tr.stats.network}_{tr.stats.station}_{tr.stats.channel}"
                        value = (max_g)

                        # If key doesn't exist, create a new dict
                        if key not in MORE_G_THRESHOLD:
                            MORE_G_THRESHOLD[key] = {
                                "values": [],
                                "exported": False,
                                "acc_from_vel": []
                            }

                        MORE_G_THRESHOLD[key]["values"].append(value)

                        if max_g > G_THRESHOLD and not export_station_data and tr.stats.station not in STANDALONE_STATIONS:
                            export_station_data = True
                            if tr.stats.station in STATION_DICT:
                                EXPORT_ST_VELOCITY.add(STATION_DICT[tr.stats.station])
                            else:
                                EXPORT_ST_VELOCITY.add(tr.stats.station)

                    if export_station_data:
                        WORK_DIR = f'{TEMP_DIR}/{str(ORIGIN_TIME)[:4]}/{ORIGIN_TIME}/{station.code}'
                        os.makedirs(WORK_DIR, exist_ok=True)
                        logger.debug(f"ქვედირექტორია შექმნილია ან უკვე არსებობს: {WORK_DIR}")

                        # **შენახვა XML ფაილში**
                        # station_inv_file = f"{WORK_DIR}/{station.code}_station_inv.xml"
                        # try:
                        #     station_inv.write(station_inv_file, format="STATIONXML")
                        #     logger.info(f"შენახულია სადგურის ინფო: {station_inv_file}")
                        # except Exception as err:
                        #     logger.exception(f"შეცდომა სადგურის ({station.code}) ინფოს შენახვისას: {err}")

                        for i, stream in enumerate(st[:3]):
                            plot_path = f'{WORK_DIR}/{station.code}_{stream.stats.channel}_plot.png'
                            stream.plot(outfile=plot_path, format="png")

                        for tr in st:
                            exported_key = f"{tr.stats.network}_{tr.stats.station}_{tr.stats.channel}"
                            MORE_G_THRESHOLD[exported_key]["exported"] = True

                            try:
                                filename = f'{ORIGIN_TIME}_{tr.stats.network}_{tr.stats.station}_{tr.stats.channel}'
                                st_file_path = os.path.join(WORK_DIR, f'{filename}.ascii')
                                logger.debug(f"ინახება: {st_file_path}")
                                write_trace_as_ascii(tr, st_file_path, unit_code=UNIT_ACC.upper())  # e.g. "VEL" or "ACC"
                            except Exception as err:
                                logger.exception(f"შეცდომა ჩანაწერის ({tr.stats.station}) შენახვისას: {err}")
                                
                except Exception as err:
                    logger.warning(f"შეცდომა სადგურის ({station.code}) მონაცემების დამუშავებისას: {err}")
                    continue

        # WORK_DIR = f'{TEMP_DIR}/{str(ORIGIN_TIME)[:4]}/{ORIGIN_TIME}'
        # os.makedirs(WORK_DIR, exist_ok=True)

        # acceleration_data_txt_path = os.path.join(WORK_DIR, "Accelerations.txt")
        # with open(acceleration_data_txt_path, "w") as file:
        #     file.write(f"{ORIGIN_TIME}\n")
        #     file.write("Station, Max G\n")
        #     file.write("\n".join(acceleration_data))

        # logger.info(f"Accelerations.txt ფაილი შეინახა: {acceleration_data_txt_path}")

    except Exception as err:
        logger.exception("მოულოდნელი შეცდომა collect_acceleration ფუნქციაში: " + str(err))

# More_G_Threshold.csv ფაილის შენახვა აქ
def write_csv():
    WORK_DIR = f'{TEMP_DIR}/{str(ORIGIN_TIME)[:4]}/{ORIGIN_TIME}'
    os.makedirs(WORK_DIR, exist_ok=True)

    more_g_threshold_csv_path = os.path.join(WORK_DIR, "g_accelerations.csv")

    stations_over_threshold = set()  # ერთზე მეტ არხს რომ არ გაუტოლდეს

    for station_key, data in MORE_G_THRESHOLD.items():
        if not data["exported"]:
            continue  # მხოლოდ ზღვარზე გადასულები

        # station_key ფორმატი: NET_STA_CHAN  -> "GO_MTAG_HNE"
        parts = station_key.split("_")
        if len(parts) >= 2:
            station_code = parts[1]  # MTAG, SHTA, etc.
            stations_over_threshold.add(station_code)

    # CSV ჩაწერა
    with open(more_g_threshold_csv_path, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["id", "latitude", "longitude", "station"])  # ჰედერი

        for station in sorted(stations_over_threshold):
            writer.writerow([EVENT_ID, LATITUDE, LONGITUDE, station])

    logger.info(f"g_accelerations.csv ფაილი შენახულია: {more_g_threshold_csv_path}")


# More_G_Threshold.txt ფაილის შენახვა აქ
def write_txt():
    WORK_DIR = f'{TEMP_DIR}/{str(ORIGIN_TIME)[:4]}/{ORIGIN_TIME}'
    os.makedirs(WORK_DIR, exist_ok=True)
    more_g_threshold_txt_path = os.path.join(WORK_DIR, "g_accelerations.txt")
    with open(more_g_threshold_txt_path, "w") as file:
        file.write(f"{ORIGIN_TIME}\n")
        # file.write("Station, Max g (from ACC), Max g (from VEL->ACC)\n")
        file.write("Station, Max g (from ACC/9.81)\n")
        for station_key, data in MORE_G_THRESHOLD.items():
            if data["exported"]:
                max_acc = max(data["values"]) if data["values"] else 0
                # max_acc_from_vel = max(data.get("acc_from_vel") or [0.0])
                # file.write(f"{station_key}, {max_acc:.6f}, {max_acc_from_vel:.6f}\n")
                file.write(f"{station_key}, {max_acc:.6f} g\n")
            else:
                logger.info(f"სადგური {station_key} არ გადაცდა ზღვარს, არ შეინახა.")

    logger.info(f"More_G_Threshold.txt ფაილი შენახულია: {more_g_threshold_txt_path}")

# სკრიპტის შესრულების ძირითადი ნაწილი
if __name__ == "__main__":
    try:
        collect_acceleration()
        export_velocity()
        write_txt()
        write_csv()  # <-- CSV-ს ჩაწერა
    except Exception as err:
        logger.exception("მოულოდნელი შეცდომა სკრიპტის შესრულებისას: " + str(err))