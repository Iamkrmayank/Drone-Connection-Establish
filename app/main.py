from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import serial
import serial.tools.list_ports
import time
from pymavlink import mavutil  # Import pymavlink for MAVLink protocol

app = FastAPI()

# Model for selecting communication parameters
class CommunicationConfig(BaseModel):
    port: str
    baud_rate: int = 57600

# Serial connection object (global)
ser = None

# Placeholder for real-time telemetry data
telemetry_data = {}

# Function to fetch telemetry from the drone using MAVLink
def fetch_telemetry():
    global telemetry_data
    while ser and ser.is_open:
        try:
            # Establish MAVLink connection
            connection = mavutil.mavlink_connection(ser)
            
            # Continuously fetch data from the drone
            while True:
                msg = connection.recv_match(blocking=True)  # Blocking wait for new message
                if msg:
                    if msg.get_type() == "ATTITUDE":
                        telemetry_data = {
                            "pitch": msg.pitch,
                            "roll": msg.roll,
                            "yaw": msg.yaw,
                            "time_boot_ms": msg.time_boot_ms
                        }
                    elif msg.get_type() == "GPS_RAW_INT":
                        telemetry_data = {
                            "latitude": msg.lat,
                            "longitude": msg.lon,
                            "altitude": msg.alt,
                            "time_boot_ms": msg.time_boot_ms
                        }
        except serial.SerialException as e:
            break
        time.sleep(1)

@app.get("/com_ports", tags=["Communication"])
def list_com_ports():
    """
    List all available COM ports on the system.
    """
    ports = serial.tools.list_ports.comports()
    if not ports:
        return {"message": "No COM ports found."}
    return {"ports": [port.device for port in ports]}

@app.post("/connect_drone", tags=["Communication"])
def connect_drone(config: CommunicationConfig, background_tasks: BackgroundTasks):
    """
    Establish a connection with the drone via the selected COM port and baud rate.
    """
    global ser
    try:
        # Close any existing connections
        if ser and ser.is_open:
            ser.close()
        
        # Open a new serial connection
        ser = serial.Serial(port=config.port, baudrate=config.baud_rate, timeout=1)
        
        # Start background task to listen for telemetry data
        background_tasks.add_task(fetch_telemetry)
        
        return {"message": f"Connected to {config.port} at {config.baud_rate} bps"}
    
    except serial.SerialException as e:
        raise HTTPException(status_code=500, detail=f"Connection error: {e}")

@app.get("/telemetry", tags=["Communication"])
def get_telemetry():
    """
    Get real-time telemetry data from the drone.
    """
    if not telemetry_data:
        raise HTTPException(status_code=404, detail="No telemetry data available.")
    return telemetry_data

@app.post("/send_command", tags=["Communication"])
def send_command(command: str):
    """
    Send a command to the drone via the established USB connection.
    """
    global ser
    if not ser or not ser.is_open:
        raise HTTPException(status_code=500, detail="No active connection. Please connect first.")
    
    try:
        # Send the command to the drone
        ser.write(command.encode())
        return {"message": f"Command '{command}' sent successfully"}
    
    except serial.SerialException as e:
        raise HTTPException(status_code=500, detail=f"Error sending command: {e}")

@app.post("/disconnect_drone", tags=["Communication"])
def disconnect_drone():
    """
    Close the connection to the drone.
    """
    global ser
    if ser and ser.is_open:
        ser.close()
        return {"message": "Connection closed successfully"}
    
    return {"message": "No active connection to close"}
