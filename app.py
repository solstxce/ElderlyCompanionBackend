from flask import Flask, render_template, request, jsonify, session
from datetime import datetime, timedelta
import json
import random
import logging
from functools import wraps
import sqlite3
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
app.secret_key = os.urandom(24)  # For session management

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='companion_app.log'
)
logger = logging.getLogger(__name__)

# Database initialization
def init_db():
    with sqlite3.connect('companion.db') as conn:
        c = conn.cursor()
        # Create necessary tables
        c.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                age INTEGER,
                emergency_contact TEXT,
                medical_conditions TEXT
            );

            CREATE TABLE IF NOT EXISTS medications (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                name TEXT NOT NULL,
                dosage TEXT,
                time_of_day TEXT,
                instructions TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );

            CREATE TABLE IF NOT EXISTS medical_history (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                event_date DATE,
                event_type TEXT,
                description TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );

            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                timestamp DATETIME,
                user_input TEXT,
                response TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
        ''')
        conn.commit()

# Initialize database on startup
init_db()

# Load configuration
class Config:
    MEDICATION_SCHEDULE = {
        'morning': {
            'time_range': (6, 11),
            'medications': [
                {'name': 'Blood Pressure Medication', 'dosage': '10mg', 'instructions': 'Take with water'},
                {'name': 'Vitamin D', 'dosage': '1000IU', 'instructions': 'Take with food'}
            ]
        },
        'afternoon': {
            'time_range': (12, 16),
            'medications': [
                {'name': 'Diabetes Medication', 'dosage': '500mg', 'instructions': 'Take after lunch'},
            ]
        },
        'evening': {
            'time_range': (17, 22),
            'medications': [
                {'name': 'Heart Medication', 'dosage': '25mg', 'instructions': 'Take with dinner'},
                {'name': 'Calcium Supplement', 'dosage': '500mg', 'instructions': 'Take before bed'}
            ]
        }
    }

    EMERGENCY_CONTACTS = {
        'primary': {'name': 'John Doe', 'relationship': 'Son', 'phone': '123-456-7890'},
        'secondary': {'name': 'Jane Doe', 'relationship': 'Daughter', 'phone': '098-765-4321'},
        'doctor': {'name': 'Dr. Smith', 'phone': '111-222-3333'}
    }

    CONVERSATION_PATTERNS = {
        'greetings': ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening'],
        'farewells': ['goodbye', 'bye', 'see you', 'good night'],
        'emergencies': ['emergency', 'help', 'fall', 'pain', 'chest', 'breathing'],
        'wellness': ['feel', 'feeling', 'tired', 'dizzy', 'sick'],
        'medication': ['medicine', 'medication', 'pill', 'drug', 'prescription'],
        'time': ['time', 'when', 'schedule', 'reminder']
    }

# Utility Functions
def get_time_period():
    hour = datetime.now().hour
    if 6 <= hour < 12:
        return 'morning'
    elif 12 <= hour < 17:
        return 'afternoon'
    elif 17 <= hour < 23:
        return 'evening'
    else:
        return 'night'

def log_conversation(user_input, response):
    """Log conversation to database"""
    try:
        with sqlite3.connect('companion.db') as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO conversation_history (user_id, timestamp, user_input, response)
                VALUES (?, ?, ?, ?)
            ''', (session.get('user_id', 1), datetime.now(), user_input, response))
            conn.commit()
    except Exception as e:
        logger.error(f"Error logging conversation: {e}")

def get_medication_details(time_period):
    """Get detailed medication information for a specific time period"""
    if time_period in Config.MEDICATION_SCHEDULE:
        meds = Config.MEDICATION_SCHEDULE[time_period]['medications']
        return "\n".join([
            f"- {med['name']} ({med['dosage']}): {med['instructions']}"
            for med in meds
        ])
    return "No medications scheduled for this time period."

# Conversation Handler Class
class ConversationHandler:
    def __init__(self):
        self.context = {}
    
    def detect_intent(self, user_input):
        """Detect the user's intent from input"""
        user_input = user_input.lower()
        
        # Check for emergencies first
        if any(word in user_input for word in Config.CONVERSATION_PATTERNS['emergencies']):
            return 'emergency'
            
        # Check for medication-related queries
        if any(word in user_input for word in Config.CONVERSATION_PATTERNS['medication']):
            return 'medication'
            
        # Check for greetings
        if any(word in user_input for word in Config.CONVERSATION_PATTERNS['greetings']):
            return 'greeting'
            
        # Check for wellness queries
        if any(word in user_input for word in Config.CONVERSATION_PATTERNS['wellness']):
            return 'wellness'
            
        return 'general'

    def handle_emergency(self):
        """Handle emergency situations"""
        emergency_contact = Config.EMERGENCY_CONTACTS['primary']
        return {
            'response': f"I'm contacting emergency services and your emergency contact {emergency_contact['name']} ({emergency_contact['phone']}). Stay calm and don't move.",
            'priority': 'high',
            'action': 'notify_emergency'
        }

    def handle_medication_query(self, user_input):
        """Handle medication-related queries"""
        time_period = get_time_period()
        
        if 'schedule' in user_input or 'what' in user_input:
            return {
                'response': f"Here's your medication schedule for {time_period}:\n{get_medication_details(time_period)}",
                'priority': 'normal'
            }
        elif 'remind' in user_input:
            return {
                'response': "I'll remind you when it's time for your next medication. Would you like me to set up regular reminders?",
                'priority': 'normal'
            }
        return {
            'response': f"Your current medications for {time_period} are ready. Click 'Get Medication Reminder' button to get more details!",
            'priority': 'normal'
        }

    def handle_wellness_query(self, user_input):
        """Handle wellness-related queries"""
        responses = {
            'tired': "I understand you're feeling tired. Have you been getting enough rest? Would you like to review your sleep schedule?",
            'pain': "I'm sorry you're in pain. Can you tell me where it hurts and how long you've been feeling this way?",
            'dizzy': "Feeling dizzy can be serious. Have you taken your blood pressure medication today? Should I contact your doctor?",
            'sick': "I'm sorry you're not feeling well. Would you like me to check your symptoms or contact your doctor?"
        }
        
        for keyword, response in responses.items():
            if keyword in user_input:
                return {'response': response, 'priority': 'high'}
        
        return {
            'response': "How are you feeling? Would you like to talk about any specific symptoms?",
            'priority': 'normal'
        }

    def generate_response(self, user_input):
        """Generate appropriate response based on user input"""
        intent = self.detect_intent(user_input)
        
        if intent == 'emergency':
            return self.handle_emergency()
        elif intent == 'medication':
            return self.handle_medication_query(user_input)
        elif intent == 'wellness':
            return self.handle_wellness_query(user_input)
        elif intent == 'greeting':
            time_period = get_time_period()
            return {
                'response': f"Good {time_period}! How are you feeling today? Would you like to review your medication schedule?",
                'priority': 'normal'
            }
        else:
            return {
                'response': "I'm here to help. We can talk about your medications, health, or any concerns you have.",
                'priority': 'normal'
            }

# Initialize conversation handler
conversation_handler = ConversationHandler()

# Routes
@app.route('/')
def home():
    return render_template('index2.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_input = request.form['message']
        response_data = conversation_handler.generate_response(user_input)
        
        # Log the conversation
        log_conversation(user_input, response_data['response'])
        
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({
            'response': "I apologize, but I'm having trouble processing your request. Please try again.",
            'priority': 'normal'
        })

@app.route('/remind', methods=['GET'])
def remind():
    try:
        time_period = get_time_period()
        medication_details = get_medication_details(time_period)
        
        reminder = f"Time for your {time_period} medications!\n{medication_details}"
        
        return jsonify({
            'reminder': reminder,
            'priority': 'normal',
            'time_period': time_period
        })
    except Exception as e:
        logger.error(f"Error in remind endpoint: {e}")
        return jsonify({
            'reminder': "I apologize, but I'm having trouble accessing your medication schedule.",
            'priority': 'normal'
        })

@app.route('/history', methods=['GET'])
def get_history():
    """Endpoint to retrieve conversation history"""
    try:
        with sqlite3.connect('companion.db') as conn:
            c = conn.cursor()
            c.execute('''
                SELECT timestamp, user_input, response 
                FROM conversation_history 
                WHERE user_id = ? 
                ORDER BY timestamp DESC 
                LIMIT 50
            ''', (session.get('user_id', 1),))
            history = c.fetchall()
            
        return jsonify({
            'history': [
                {
                    'timestamp': row[0],
                    'user_input': row[1],
                    'response': row[2]
                }
                for row in history
            ]
        })
    except Exception as e:
        logger.error(f"Error retrieving history: {e}")
        return jsonify({'error': 'Unable to retrieve conversation history'})

@app.route('/medication_schedule', methods=['GET'])
def get_medication_schedule():
    """Endpoint to get full medication schedule"""
    return jsonify({'schedule': Config.MEDICATION_SCHEDULE})

# Error Handlers
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=True)