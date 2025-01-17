from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import serial
import serial.tools.list_ports
from pymavlink import mavutil  # Import pymavlink for MAVLink protocol

app = FastAPI()

# Model for selecting communication parameters
class CommunicationConfig(BaseModel):
    port: str
    baud_rate: int = 57600

# Model for changing drone mode
class DroneMode(BaseModel):
    mode_name: str

# Serial connection object (global)
ser = None
mav_connection = None  # MAVLink connection object

# Placeholder for real-time telemetry data
telemetry_data = {}

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
    global ser, mav_connection
    try:
        # Close any existing connections
        if ser and ser.is_open:
            ser.close()
        
        # Open a new serial connection
        ser = serial.Serial(port=config.port, baudrate=config.baud_rate, timeout=1)
        mav_connection = mavutil.mavlink_connection(config.port, baud=config.baud_rate)
        
        # Wait for the heartbeat to ensure communication
        mav_connection.wait_heartbeat()
        
        return {"message": f"Connected to {config.port} at {config.baud_rate} bps"}
    
    except serial.SerialException as e:
        raise HTTPException(status_code=500, detail=f"Connection error: {e}")

@app.get("/telemetry", tags=["Communication"])
def get_telemetry():
    """
    Get real-time telemetry data from the drone.
    """
    global mav_connection
    if not mav_connection:
        raise HTTPException(status_code=500, detail="No MAVLink connection established.")
    
    try:
        msg = mav_connection.recv_match(blocking=True)
        if msg:
            return {"telemetry": msg.to_dict()}
        else:
            raise HTTPException(status_code=404, detail="No telemetry data available.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching telemetry: {e}")

@app.post("/change_mode", tags=["Communication"])
def change_mode(drone_mode: DroneMode):
    """
    Change the flight mode of the drone.
    """
    global mav_connection
    if not mav_connection:
        raise HTTPException(status_code=500, detail="No MAVLink connection established.")
    
    try:
        # Set the mode using the MAVLink protocol
        mode_id = mav_connection.mode_mapping()[drone_mode.mode_name]
        mav_connection.set_mode(mode_id)
        return {"message": f"Flight mode changed to '{drone_mode.mode_name}'"}
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: '{drone_mode.mode_name}'")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error changing mode: {e}")

@app.post("/send_command", tags=["Communication"])
def send_command(command: str):
    """
    Send a command to the drone via the MAVLink connection.
    """
    global mav_connection
    if not mav_connection:
        raise HTTPException(status_code=500, detail="No active connection. Please connect first.")
    
    try:
        # Send the custom MAVLink command if supported
        mav_connection.mav.command_long_send(
            mav_connection.target_system,
            mav_connection.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_MODE,
            0,  # Confirmation
            command,
            0, 0, 0, 0, 0, 0
        )
        return {"message": f"Command '{command}' sent successfully"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending command: {e}")

@app.post("/disconnect_drone", tags=["Communication"])
def disconnect_drone():
    """
    Close the connection to the drone.
    """
    global ser, mav_connection
    if ser and ser.is_open:
        ser.close()
    if mav_connection:
        mav_connection.close()
        mav_connection = None
    return {"message": "Connection closed successfully"}
