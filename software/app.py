"""
Flask Application for Smart Organic Fertilizer System
Provides REST API endpoints for sensor data and system management
"""

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from datetime import datetime
import os
import json

app = Flask(__name__, template_folder='frontend_dashboard', static_folder='frontend_dashboard')
CORS(app)

# Import the serial reader module
from serial_reader import SerialDataReader


class DataManager:
    """Manages access to sensor data and system state"""
    
    def __init__(self):
        self.latest_data = {}
        self.system_state = {
            'status': 'idle',
            'plants': ['mint', 'basil'],
            'fertilizer_levels': {'mint': 75, 'basil': 65},
            'pump_status': {'mint': False, 'basil': False}
        }
    
    def update_data(self, data):
        """Update latest sensor data"""
        self.latest_data = data
    
    def get_current_data(self):
        """Get current sensor data"""
        return {
            'timestamp': datetime.now().isoformat(),
            'data': self.latest_data,
            'system_state': self.system_state
        }


# Initialize data manager and serial reader
data_manager = DataManager()
serial_reader = SerialDataReader(data_callback=data_manager.update_data)


@app.route('/', methods=['GET'])
def index():
    """Serve main dashboard"""
    return render_template('index.html')


@app.route('/data', methods=['GET'])
def get_data():
    """
    GET endpoint for retrieving current sensor data
    
    Query Parameters:
        - plant (optional): Filter data by plant name ('mint' or 'basil')
        - period (optional): Time period for data retrieval ('latest', '1h', '24h')
    
    Returns:
        JSON object with sensor readings and system state
    """
    try:
        plant = request.args.get('plant', None)
        period = request.args.get('period', 'latest')
        
        current_data = data_manager.get_current_data()
        
        # Filter by plant if specified
        if plant and plant.lower() in ['mint', 'basil']:
            current_data['plant_filter'] = plant.lower()
            # Filter data to requested plant only
            if plant.lower() in current_data['data']:
                current_data['data'] = {
                    plant.lower(): current_data['data'][plant.lower()]
                }
        
        return jsonify({
            'success': True,
            'timestamp': current_data['timestamp'],
            'data': current_data['data'],
            'system_state': current_data['system_state'],
            'period': period
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/data/history', methods=['GET'])
def get_data_history():
    """
    GET endpoint for historical sensor data
    
    Query Parameters:
        - start_time (optional): Start timestamp for history
        - end_time (optional): End timestamp for history
        - plant (optional): Filter by plant name
    
    Returns:
        JSON array of historical data points
    """
    try:
        plant = request.args.get('plant', None)
        start_time = request.args.get('start_time', None)
        end_time = request.args.get('end_time', None)
        
        history_data = serial_reader.get_csv_data(
            plant=plant,
            start_time=start_time,
            end_time=end_time
        )
        
        return jsonify({
            'success': True,
            'data': history_data,
            'plant': plant,
            'period': {
                'start': start_time,
                'end': end_time
            }
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/control/pump', methods=['POST'])
def control_pump():
    """
    POST endpoint for controlling fertilizer pump
    
    JSON Body:
        - plant (required): 'mint' or 'basil'
        - action (required): 'on' or 'off'
        - duration (optional): Duration in seconds for timed operation
    
    Returns:
        JSON with operation status
    """
    try:
        request_data = request.get_json()
        plant = request_data.get('plant')
        action = request_data.get('action')
        duration = request_data.get('duration', None)
        
        if plant not in ['mint', 'basil']:
            return jsonify({
                'success': False,
                'error': 'Invalid plant. Must be "mint" or "basil"'
            }), 400
        
        if action not in ['on', 'off']:
            return jsonify({
                'success': False,
                'error': 'Invalid action. Must be "on" or "off"'
            }), 400
        
        # Update system state
        data_manager.system_state['pump_status'][plant] = (action == 'on')
        
        return jsonify({
            'success': True,
            'plant': plant,
            'action': action,
            'duration': duration,
            'timestamp': datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/status', methods=['GET'])
def get_status():
    """Get system status"""
    return jsonify({
        'success': True,
        'status': 'running',
        'serial_connected': serial_reader.is_connected(),
        'plants': data_manager.system_state['plants'],
        'timestamp': datetime.now().isoformat()
    }), 200


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500


if __name__ == '__main__':
    # Start serial reader in background thread
    serial_reader.start()
    
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        threaded=True
    )
