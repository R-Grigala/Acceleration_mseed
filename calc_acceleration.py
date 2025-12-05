import csv
import subprocess

CSV_FILE = "test_eq.csv"    # შენი csv ფაილის სახელი
ACCELERATION_SCRIPT = "acceleration.py"  # acceleration.py-ის ფაილი

# გახსენი CSV ფაილი
with open(CSV_FILE, newline='') as csvfile:
    reader = csv.DictReader(csvfile)  # DictReader რომ ველს სახელებით მივწვდეთ
    for row in reader:
        event_id = row['id'].strip()  # აქედან იღებ 
        origin_time = row['origin_time'].strip()  # აქედან იღებ origin_time-ს
        latitude = row['latitude'].strip()
        longitude = row['longitude'].strip()
        try:
            subprocess.run(["python3", ACCELERATION_SCRIPT, event_id, latitude, longitude, origin_time], check=True)
            print(f"წარმატებით დამუშავდა {origin_time}")
        except subprocess.CalledProcessError as e:
            print(f"შეცდომა დამუშვებისას {origin_time}: {e}")
