"""
PySerial Reader Module for Smart Organic Fertilizer System
Handles serial communication with sensor hardware and CSV logging
"""

import serial
import threading
import queue
import csv
import os
from datetime import datetime
from typing import Optional, Callable, Dict, List


class SerialDataReader:
    """Manages serial communication with sensors and data logging"""
    
    def __init__(
        self,
        port: str = '/dev/ttyUSB0',
        baudrate: int = 9600,
        timeout: float = 1.0,
        data_callback: Optional[Callable] = None,
        csv_path: str = 'sensor_data.csv'
    ):
        """
        Initialize Serial Reader
        
        Args:
            port: Serial port (e.g., '/dev/ttyUSB0', 'COM3')
            baudrate: Baud rate for serial communication
            timeout: Read timeout in seconds
            data_callback: Callback function when data is received
            csv_path: Path to CSV file for logging
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.data_callback = data_callback
        self.csv_path = csv_path
        
        self.serial_conn = None
        self.data_queue = queue.Queue(maxsize=100)
        self.is_running = False
        self.reader_thread = None
        self.processor_thread = None
        
        # Initialize CSV file
        self._initialize_csv()
    
    def _initialize_csv(self) -> None:
        """Initialize CSV file with headers if it doesn't exist"""
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp',
                    'plant',
                    'ph',
                    'ec',
                    'temperature',
                    'water_level',
                    'humidity'
                ])
    
    def _connect(self) -> bool:
        """Establish serial connection"""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            print(f"Connected to {self.port} at {self.baudrate} baud")
            return True
        except serial.SerialException as e:
            print(f"Failed to connect to serial port: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if serial connection is active"""
        return self.serial_conn is not None and self.serial_conn.is_open
    
    def _read_serial(self) -> None:
        """Read data from serial port in a separate thread"""
        while self.is_running:
            try:
                if self.serial_conn and self.serial_conn.in_waiting:
                    line = self.serial_conn.readline().decode('utf-8').strip()
                    if line:
                        self.data_queue.put(line)
            except Exception as e:
                print(f"Error reading from serial: {e}")
    
    def _process_data(self) -> None:
        """Process data from queue and log to CSV"""
        while self.is_running:
            try:
                line = self.data_queue.get(timeout=1)
                data = self._parse_sensor_data(line)
                
                if data:
                    # Log to CSV
                    self._log_to_csv(data)
                    
                    # Call callback if provided
                    if self.data_callback:
                        self.data_callback(data)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error processing data: {e}")
    
    def _parse_sensor_data(self, line: str) -> Optional[Dict]:
        """
        Parse sensor data from serial line
        Expected format: PLANT,PH,EC,TEMP,WATER,HUMIDITY
        Example: mint,6.4,1.8,24.5,84,65
        """
        try:
            parts = line.split(',')
            if len(parts) < 6:
                return None
            
            data = {
                'timestamp': datetime.now().isoformat(),
                'plant': parts[0].lower(),
                'ph': float(parts[1]),
                'ec': float(parts[2]),
                'temperature': float(parts[3]),
                'water_level': float(parts[4]),
                'humidity': float(parts[5])
            }
            return data
        except (ValueError, IndexError):
            return None
    
    def _log_to_csv(self, data: Dict) -> None:
        """Log sensor data to CSV file"""
        try:
            with open(self.csv_path, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    data['timestamp'],
                    data['plant'],
                    data['ph'],
                    data['ec'],
                    data['temperature'],
                    data['water_level'],
                    data['humidity']
                ])
        except Exception as e:
            print(f"Error logging to CSV: {e}")
    
    def start(self) -> bool:
        """
        Start the serial reader and data processor threads
        
        Returns:
            True if started successfully, False otherwise
        """
        if self.is_running:
            print("Reader is already running")
            return False
        
        if not self._connect():
            return False
        
        self.is_running = True
        
        # Start reader thread
        self.reader_thread = threading.Thread(target=self._read_serial, daemon=True)
        self.reader_thread.start()
        
        # Start processor thread
        self.processor_thread = threading.Thread(target=self._process_data, daemon=True)
        self.processor_thread.start()
        
        print("Serial reader started")
        return True
    
    def stop(self) -> None:
        """Stop the serial reader and close connection"""
        self.is_running = False
        
        if self.reader_thread:
            self.reader_thread.join(timeout=2)
        
        if self.processor_thread:
            self.processor_thread.join(timeout=2)
        
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        
        print("Serial reader stopped")
    
    def get_csv_data(
        self,
        plant: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> List[Dict]:
        """
        Retrieve historical data from CSV
        
        Args:
            plant: Filter by plant name (optional)
            start_time: ISO format timestamp (optional)
            end_time: ISO format timestamp (optional)
        
        Returns:
            List of data dictionaries matching criteria
        """
        data = []
        try:
            with open(self.csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Filter by plant if specified
                    if plant and row['plant'].lower() != plant.lower():
                        continue
                    
                    # Filter by time range if specified
                    if start_time and row['timestamp'] < start_time:
                        continue
                    if end_time and row['timestamp'] > end_time:
                        continue
                    
                    data.append(row)
        except FileNotFoundError:
            print("CSV file not found")
        except Exception as e:
            print(f"Error reading CSV: {e}")
        
        return data
    
    def send_command(self, command: str) -> None:
        """
        Send command to serial device
        
        Args:
            command: Command string to send
        """
        try:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.write((command + '\n').encode('utf-8'))
                print(f"Sent command: {command}")
        except Exception as e:
            print(f"Error sending command: {e}")
