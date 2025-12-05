import csv

# 1) Read stations coordinate CSV into dictionary
station_coords = {}

with open("station_coordinates.csv", "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        code = row["code"]
        station_coords[code] = {
            "sta_latitude": row["latitude"],
            "sta_longitude": row["longitude"]
        }

# 2) Merge with event CSV
with open("acc_stations.csv", "r") as fin, open("merged_output.csv", "w", newline="") as fout:
    reader = csv.DictReader(fin)
    fieldnames = ["id", "latitude", "longitude", "station", "sta_latitude", "sta_longitude"]
    writer = csv.DictWriter(fout, fieldnames=fieldnames)
    writer.writeheader()

    for row in reader:
        sta = row["station"]

        if sta in station_coords:
            row.update(station_coords[sta])
        else:
            row.update({"sta_latitude": "", "sta_longitude": ""})  # Not found

        writer.writerow(row)
