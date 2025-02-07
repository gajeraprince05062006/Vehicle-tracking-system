from flask import Flask, render_template
import mysql.connector

app = Flask(__name__)

# MySQL Database configuration
db_config = {
    'host': 'localhost',   # Host (use 'localhost' or the IP of the server)
    'port': 3307,          # MySQL server port (default: 3306)
    'database': 'prince',  # Your database name
    'user': 'root',        # Your MySQL username
    'password': '',        # Your MySQL password
}

# Function to connect to the database
def get_db_connection():
    conn = mysql.connector.connect(**db_config)
    return conn

# Route to display data
@app.route('/')
def index():
    # Establish connection to the database
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)  # Ensures data is returned as dictionaries
    cursor.execute("SELECT * FROM vehicle")  # Replace 'vehicle' with your actual table name
    vehicles = cursor.fetchall()  # Fetch all data from the table
    cursor.close()
    conn.close()

    # Pass the data to the HTML template
    return render_template('index.html', vehicles=vehicles)

if __name__ == '__main__':
    app.run(debug=True)
