import os
import json
from datetime import datetime, timedelta, timezone
from flask import session
import re
import tempfile
import shutil

# Tbilisi timezone (UTC+4, no DST in Georgia)
TBILISI_TZ = timezone(timedelta(hours=4))

def get_tbilisi_date():
    """Get today's date in Tbilisi timezone"""
    return datetime.now(TBILISI_TZ).date()

def get_tbilisi_datetime():
    """Get current datetime in Tbilisi timezone"""
    return datetime.now(TBILISI_TZ)

# Data paths
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
FOODS_FILE = os.path.join(DATA_DIR, 'foods.json')
WORKOUTS_FILE = os.path.join(DATA_DIR, 'workouts.json')
ENTRIES_FILE = os.path.join(DATA_DIR, 'entries.json')

def load_json(path):
    """Load JSON file, create empty array if doesn't exist"""
    if not os.path.exists(path):
        # Return appropriate default based on filename
        if 'rate_limits' in path:
            return {}  # Dictionary for rate limits
        return []  # List for other files
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Validate data type based on filename
            if 'rate_limits' in path and not isinstance(data, dict):
                return {}
            elif 'rate_limits' not in path and not isinstance(data, list):
                return []
            return data
    except (json.JSONDecodeError, IOError):
        # Return appropriate default on error
        if 'rate_limits' in path:
            return {}
        return []

def save_json(path, data):
    """Save data to JSON file with backup protection"""
    return safe_save_json(path, data)

def safe_save_json(filepath, data):
    """Safely save JSON with backup and validation"""
    try:
        # Create backup
        backup_path = f"{filepath}.backup"
        if os.path.exists(filepath):
            shutil.copy2(filepath, backup_path)
        
        # Write to temporary file first
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.tmp') as tmp_file:
            json.dump(data, tmp_file, indent=2)
            temp_path = tmp_file.name
        
        # Validate the temporary file
        with open(temp_path, 'r') as f:
            json.load(f)  # This will raise an exception if invalid
        
        # Move temp file to final location
        shutil.move(temp_path, filepath)
        
        # Remove backup if successful
        if os.path.exists(backup_path):
            os.remove(backup_path)
            
        return True
    except Exception as e:
        # Restore from backup if it exists
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, filepath)
        
        # Clean up temp file
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
            
        return False

def get_user(username):
    """Get user by username"""
    if not username:
        return None
    users = load_json(USERS_FILE)
    if not isinstance(users, list):
        return None
    return next((u for u in users if u['username'] == username), None)

def update_user(user):
    """Update user in database"""
    users = load_json(USERS_FILE)
    if not isinstance(users, list):
        return
    for i, u in enumerate(users):
        if u['username'] == user['username']:
            users[i] = user
            break
    save_json(USERS_FILE, users)

def is_admin():
    """Check if current user is admin"""
    user = get_user(session.get('user'))
    return user and user.get('role') == 'admin'

def safe_float(val):
    """Convert value to float safely"""
    try:
        return float(val) if val else 0.0
    except (TypeError, ValueError):
        return 0.0

def calc_macros(entry):
    """Calculate macros based on entry"""
    totals = {'protein': 0, 'carbs': 0, 'fat': 0, 'calories': 0}
    
    for food in entry.get('foods', []):
        amount = food.get('amount', 100) or 100
        factor = amount / 100
        
        totals['protein'] += (food.get('protein', 0) or 0) * factor
        totals['carbs'] += (food.get('carbs', 0) or 0) * factor
        totals['fat'] += (food.get('fat', 0) or 0) * factor
        totals['calories'] += (food.get('calories', 0) or 0) * factor
    
    entry.update({
        'total_protein': round(totals['protein'], 1),
        'total_carbs': round(totals['carbs'], 1),
        'total_fat': round(totals['fat'], 1),
        'total_cal': round(totals['calories'], 0)
    })
    return entry

def calculate_recommended_macros(weight=70, height=175, age=25, gender='male', goal='maintain', activity_level=1.5):
    """Calculate recommended macros based on user profile"""
    # BMR calculation (Mifflin-St Jeor Equation)
    s = 5 if gender.lower() == 'male' else -161
    bmr = 10 * weight + 6.25 * height - 5 * age + s
    
    # TDEE calculation
    tdee = bmr * activity_level
    
    # Goal modifiers
    goal_modifiers = {'lose': 0.8, 'maintain': 1.0, 'gain': 1.15}
    target_calories = tdee * goal_modifiers.get(goal.lower(), 1.0)
    
    # Protein calculation
    protein_per_kg = {'lose': 2.0, 'maintain': 1.8, 'gain': 2.0}
    protein_grams = weight * protein_per_kg.get(goal.lower(), 1.8)
    protein_calories = protein_grams * 4
    
    # Fat calculation
    fat_grams = weight * 0.9
    fat_calories = fat_grams * 9
    
    # Carbs calculation
    remaining_calories = target_calories - protein_calories - fat_calories
    carb_grams = max(remaining_calories / 4, 0)
    
    return {
        'protein': round(protein_grams, 1),
        'carbs': round(carb_grams, 1),
        'fat': round(fat_grams, 1),
        'calories': round(target_calories, 0),
        'tdee': round(tdee, 0),
        'bmr': round(bmr, 0)
    }

def is_birthday_today(birthday_str):
    """Check if today is the user's birthday"""
    if not birthday_str:
        return False
    try:
        today = datetime.today()
        bday = datetime.strptime(birthday_str, "%Y-%m-%d")
        return bday.month == today.month and bday.day == today.day
    except:
        return False

def find_duplicate(items, name):
    """Find duplicate items based on name"""
    return [item for item in items if item['name'].lower() == name.lower()]

# NEW SECURITY FUNCTIONS

def validate_name(name, item_type="item"):
    """Comprehensive name validation"""
    if not name or not isinstance(name, str):
        return False, f"{item_type} name is required"
    
    # Length limits
    name = name.strip()
    if len(name) < 2:
        return False, f"{item_type} name must be at least 2 characters"
    if len(name) > 100:
        return False, f"{item_type} name must be less than 100 characters"
    
    # Character validation
    if not re.match(r"^[a-zA-Z0-9\s\-']+$", name):
        return False, f"{item_type} name can only contain letters, numbers, spaces, hyphens, and apostrophes"
    
    # Prevent only whitespace
    if not name.strip():
        return False, f"{item_type} name cannot be empty or only spaces"
    
    # Prevent system impersonation
    if name.lower().startswith(('system', 'admin', 'default')):
        return False, f"{item_type} name cannot start with reserved words"
    
    return True, ""

def validate_numeric_input(value, field_name, min_val=0, max_val=10000):
    """Validate numeric inputs for sets, reps, weight, etc."""
    try:
        if value == '' or value is None:
            return True, 0
        num_val = float(value)
        if num_val < min_val or num_val > max_val:
            return False, f"{field_name} must be between {min_val} and {max_val}"
        return True, num_val
    except (ValueError, TypeError):
        return False, f"{field_name} must be a valid number"

def check_rate_limit(user, action_type, max_actions=10, time_window=3600):
    """Prevent spam by limiting actions per hour - TEMPORARILY DISABLED"""
    # Temporarily return True to bypass rate limiting
    return True, ""

def sanitize_entry_data(entry):
    """Clean entry data before saving"""
    sanitized = {
        'user': str(entry.get('user', ''))[:50],
        'date': str(entry.get('date', ''))[:10],
        'privacy': entry.get('privacy', 'Private'),
        'foods': [],
        'workouts': []
    }
    
    # Validate foods
    for food in entry.get('foods', []):
        if isinstance(food, dict) and food.get('name'):
            clean_food = {
                'name': str(food.get('name', ''))[:100],
                'amount': max(0, min(10000, float(food.get('amount', 0)))),
                'calories': max(0, min(10000, float(food.get('calories', 0)))),
                'protein': max(0, min(1000, float(food.get('protein', 0)))),
                'carbs': max(0, min(1000, float(food.get('carbs', 0)))),
                'fat': max(0, min(1000, float(food.get('fat', 0))))
            }
            sanitized['foods'].append(clean_food)
    
    # Validate workouts
    for workout in entry.get('workouts', []):
        if isinstance(workout, dict) and workout.get('name'):
            clean_workout = {
                'name': str(workout.get('name', ''))[:100],
                'sets': max(0, min(100, int(workout.get('sets', 0)))),
                'reps': max(0, min(1000, int(workout.get('reps', 0)))),
                'weight': max(0, min(1000, float(workout.get('weight', 0)))),
                'duration': max(0, min(1440, float(workout.get('duration', 0)))),
                'categories': workout.get('categories', [])[:5]
            }
            sanitized['workouts'].append(clean_workout)
    
    return sanitized

def validate_session():
    """Ensure session integrity"""
    if 'user' not in session:
        return False
    
    user = get_user(session['user'])
    if not user:
        session.clear()
        return False
    
    return True

def sanitize_categories(categories_raw):
    """Validate and sanitize categories"""
    try:
        categories = json.loads(categories_raw) if isinstance(categories_raw, str) else categories_raw
        if not isinstance(categories, list):
            return []
        # Limit number and validate each category
        categories = categories[:5]  # Max 5 categories
        return [cat for cat in categories if isinstance(cat, str) and len(cat.strip()) > 0 and len(cat.strip()) <= 50]
    except:
        return []