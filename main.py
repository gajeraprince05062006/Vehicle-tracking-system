import cv2
import dlib
import time
import math
import mysql.connector

# MySQL Database configuration
db_config = {
    'host': 'localhost',   
    'port': 3307,          
    'database': 'prince',  
    'user': 'root',       
    'password': ''         
}

# Establish connection to the database
def connect_to_db():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

# Create vehicle table in the database
def create_vehicle_table(cursor):
    create_table_query = """
    CREATE TABLE IF NOT EXISTS vehicle (
        VehicleID INT,
        Speed FLOAT,
        Penalty FLOAT
    );
    """
    cursor.execute(create_table_query)

# Insert vehicle data (Speed, Penalty, and VehicleID) into the database
def insert_vehicle_data(cursor, vehicle_id, speed, penalty):
    insert_query = "INSERT INTO vehicle (VehicleID, Speed, Penalty) VALUES (%s, %s, %s)"
    cursor.execute(insert_query, (vehicle_id, speed, penalty))
    #cursor.connection.commit()  # Commit the transaction to save data to the database
    print(f"Vehicle ID {vehicle_id} data inserted into the database.")

# Vehicle Speed Estimation Function
def estimateSpeed(location1, location2):
    d_pixels = math.sqrt(math.pow(location2[0] - location1[0], 2) + math.pow(location2[1] - location1[1], 2))
    ppm = 8.8  # Pixels per meter
    d_meters = d_pixels / ppm
    fps = 14  # Frames per second of the video
    speed = d_meters * fps * 3.6  # Convert m/s to km/h
    return speed

# Main function to track vehicles and insert data into the database
def trackMultipleObjects():
    carCascade = cv2.CascadeClassifier('vech.xml')
    video = cv2.VideoCapture('carsVid.mp4')

    WIDTH = 1000
    HEIGHT = 600
    rectangleColor = (0, 255, 0)
    frameCounter = 0
    currentCarID = 0

    Vehicle_Tracker = {}
    carLocation1 = {}
    carLocation2 = {}
    speed = [None] * 1000
    reportedCars = set()

    out = cv2.VideoWriter('outNew.avi', cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'), 10, (WIDTH, HEIGHT))

    # Connect to the database and create table if it doesn't exist
    conn = connect_to_db()
    if conn is None:
        print("Database connection failed.")
        return
    cursor = conn.cursor()
    create_vehicle_table(cursor)

    while True:
        start_time = time.time()
        rc, image = video.read()
        if type(image) == type(None):
            break

        image = cv2.resize(image, (WIDTH, HEIGHT))
        resultImage = image.copy()

        frameCounter += 1
        carIDtoDelete = []

        # Remove trackers with low quality
        for VehicleID in Vehicle_Tracker.keys():
            trackingQuality = Vehicle_Tracker[VehicleID].update(image)
            if trackingQuality < 7:
                carIDtoDelete.append(VehicleID)

        for VehicleID in carIDtoDelete:
            Vehicle_Tracker.pop(VehicleID, None)
            carLocation1.pop(VehicleID, None)
            carLocation2.pop(VehicleID, None)

        # Detect cars every 10 frames
        if not (frameCounter % 10):
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            cars = carCascade.detectMultiScale(gray, 1.1, 13, 18, (24, 24))

            for (_x, _y, _w, _h) in cars:
                x, y, w, h = int(_x), int(_y), int(_w), int(_h)
                x_bar = x + 0.5 * w
                y_bar = y + 0.5 * h

                matchCarID = None

                for VehicleID in Vehicle_Tracker.keys():
                    trackedPosition = Vehicle_Tracker[VehicleID].get_position()
                    X_Tracker, Y_Tracker = int(trackedPosition.left()), int(trackedPosition.top())
                    Width_Tracker, Height_Tracker = int(trackedPosition.width()), int(trackedPosition.height())

                    t_x_bar = X_Tracker + 0.5 * Width_Tracker
                    t_y_bar = Y_Tracker + 0.5 * Height_Tracker

                    if ((X_Tracker <= x_bar <= (X_Tracker + Width_Tracker)) and
                            (Y_Tracker <= y_bar <= (Y_Tracker + Height_Tracker)) and
                            (x <= t_x_bar <= (x + w)) and
                            (y <= t_y_bar <= (y + h))):
                        matchCarID = VehicleID

                if matchCarID is None:
                    print('Creating new tracker' + str(currentCarID))
                    tracker = dlib.correlation_tracker()
                    tracker.start_track(image, dlib.rectangle(x, y, x + w, y + h))
                    Vehicle_Tracker[currentCarID] = tracker
                    carLocation1[currentCarID] = [x, y, w, h]
                    currentCarID += 1

        # Update tracker and estimate speed
        for VehicleID in Vehicle_Tracker.keys():
            trackedPosition = Vehicle_Tracker[VehicleID].get_position()
            X_Tracker, Y_Tracker = int(trackedPosition.left()), int(trackedPosition.top())
            Width_Tracker, Height_Tracker = int(trackedPosition.width()), int(trackedPosition.height())

            cv2.rectangle(resultImage, (X_Tracker, Y_Tracker), (X_Tracker + Width_Tracker, Y_Tracker + Height_Tracker),
                          rectangleColor, 2)

            carLocation2[VehicleID] = [X_Tracker, Y_Tracker, Width_Tracker, Height_Tracker]

        end_time = time.time()

        # Calculate FPS
        fps = 1.0 / (end_time - start_time) if (end_time - start_time) > 0 else 0

        # Estimate speed and log if > 50
        for i in carLocation1.keys():
            if frameCounter % 1 == 0:
                [x1, y1, w1, h1] = carLocation1[i]
                [x2, y2, w2, h2] = carLocation2[i]

                carLocation1[i] = [x2, y2, w2, h2]

                if [x1, y1, w1, h1] != [x2, y2, w2, h2]:
                    if (speed[i] is None or speed[i] == 0) and 275 <= y1 <= 285:
                        speed[i] = estimateSpeed([x1, y1, w1, h1], [x2, y2, w2, h2])

                    if speed[i] is not None and i not in reportedCars:
                        if speed[i] > 50:  # Speed limit condition
                            reportedCars.add(i)
                            print(f"Vehicle ID {i} exceeded speed limit with {speed[i]:.2f} km/h")
                            
                            # Store the VehicleID, Speed, and Penalty in the database
                            insert_vehicle_data(cursor, i, speed[i], 100)  # Assuming penalty is 50

                    # Only show speed if it's not None
                    if speed[i] is not None:
                        if y1 >= 180:
                            cv2.putText(resultImage, f"ID: {i} {int(speed[i])} km/h", 
                                        (int(x1 + w1 / 2), int(y1 - 5)),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 255), 2)
                    else:
                        if y1 >= 180:
                            cv2.putText(resultImage, f"ID: {i} Speed Not Available", 
                                        (int(x1 + w1 / 2), int(y1 - 5)),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 255), 2)

        # Display the results and save to file
        cv2.imshow('Analysis Video', resultImage)
        out.write(resultImage)

        if cv2.waitKey(1) == 27:  # Exit on 'ESC'
            break

    # Close the database connection and release resources
    cursor.close()
    conn.commit()
    conn.close()
    cv2.destroyAllWindows()
    out.release()


if __name__ == '__main__':
    trackMultipleObjects()
