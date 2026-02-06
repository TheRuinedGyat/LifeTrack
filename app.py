from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, date
from utils import *
import json
import os
import secrets

# Import blueprints
from auth import auth_bp
from food import food_bp
from workout import workout_bp
from admin import admin_bp
from user_profile import user_profile_bp
from templates import templates_bp

app = Flask(__name__)
# Use environment variable for secret key, fallback to random secret for dev
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(food_bp)
app.register_blueprint(workout_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(user_profile_bp)
app.register_blueprint(templates_bp)

# Data file paths
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
ENTRIES_FILE = os.path.join(DATA_DIR, 'entries.json')

# ADD THIS: Make is_admin function available in all templates
@app.context_processor
def inject_template_functions():
    return dict(is_admin=is_admin)

@app.before_request
def check_session():
    """Validate session before each request"""
    if request.endpoint and not request.endpoint.startswith('auth.'):
        if not validate_session() and request.endpoint not in ['auth.login', 'auth.signup']:
            return redirect(url_for('auth.login'))

@app.route('/')
def home():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    entries = load_json(ENTRIES_FILE)
    # Filter entries for display and add index for deletion
    display_entries = []
    for i, e in enumerate(entries):
        if (e['privacy'] == 'Public' and not e.get('pending_approval', False)) or (e['user'] == session['user']):
            e['actual_index'] = i  # Add the real index for deletion
            display_entries.append(e)
    
    # Calculate user stats
    user_entries = [e for e in entries if e['user'] == session['user']]
    stats = calculate_user_stats(user_entries)
    
    # Calculate macros for display entries
    display_entries = [calc_macros(e) for e in display_entries]
    
    user = get_user(session['user'])
    
    # FIX: Convert any string values to integers in profile
    if user and 'profile' in user:
        for key in ['height', 'weight', 'calorie_goal', 'protein_goal', 'carb_goal', 'fat_goal']:
            if key in user['profile']:
                try:
                    user['profile'][key] = int(float(user['profile'][key]))
                except (ValueError, TypeError):
                    user['profile'][key] = 0
    
    return render_template('home.html', 
                         entries=display_entries, 
                         user=user,
                         **stats)

@app.route('/log')
def log():
    return render_template('log.html')

@app.route('/delete_log/<int:log_id>', methods=['POST'])
def delete_log(log_id):
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    # Rate limiting for delete operations
    rate_ok, rate_msg = check_rate_limit(session['user'], 'delete_log', max_actions=10, time_window=3600)
    if not rate_ok:
        flash(rate_msg, 'error')
        return redirect(url_for('home'))
    
    entries = load_json(ENTRIES_FILE)
    
    if 0 <= log_id < len(entries):
        if entries[log_id].get('user') == session.get('user'):
            try:
                del entries[log_id]
                save_json(ENTRIES_FILE, entries)
                flash('Log deleted successfully.', 'success')
            except Exception:
                flash('Error deleting log.', 'error')
        else:
            flash('You can only delete your own logs.', 'error')
    else:
        flash('Log not found.', 'error')
        
    return redirect(url_for('home'))

@app.route('/edit_log_date/<int:log_id>', methods=['POST'])
def edit_log_date(log_id):
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    # Rate limiting
    rate_ok, rate_msg = check_rate_limit(session['user'], 'edit_log', max_actions=20, time_window=3600)
    if not rate_ok:
        flash(rate_msg, 'error')
        return redirect(url_for('home'))
    
    entries = load_json(ENTRIES_FILE)
    if 0 <= log_id < len(entries) and entries[log_id]['user'] == session['user']:
        new_date = request.form.get('date')
        if new_date and len(new_date) == 10:  # Basic date format validation
            try:
                entries[log_id]['date'] = new_date
                save_json(ENTRIES_FILE, entries)
                flash('Log date updated.', 'success')
            except Exception:
                flash('Error updating log date.', 'error')
        else:
            flash('Invalid date.', 'error')
    else:
        flash('You can only edit your own logs.', 'error')
    return redirect(url_for('home'))

@app.route('/toggle_log_privacy/<int:log_id>', methods=['POST'])
def toggle_log_privacy(log_id):
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    # Rate limiting
    rate_ok, rate_msg = check_rate_limit(session['user'], 'toggle_privacy', max_actions=20, time_window=3600)
    if not rate_ok:
        flash(rate_msg, 'error')
        return redirect(url_for('home'))
    
    entries = load_json(ENTRIES_FILE)
    if 0 <= log_id < len(entries) and entries[log_id]['user'] == session['user']:
        try:
            entries[log_id]['privacy'] = 'Public' if entries[log_id]['privacy'] != 'Public' else 'Private'
            save_json(ENTRIES_FILE, entries)
            flash('Privacy updated.', 'success')
        except Exception:
            flash('Error updating privacy.', 'error')
    else:
        flash('You can only change privacy for your own logs.', 'error')
    return redirect(url_for('home'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    user = get_user(session['user'])
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        # Ensure profile dict exists
        if 'profile' not in user:
            user['profile'] = {}
        
        # Update user profile with form data - convert numeric values
        try:
            # Use int(float()) to handle decimal strings like "170.0"
            user['profile']['height'] = int(float(request.form.get('height', 0)))
            user['profile']['weight'] = int(float(request.form.get('weight', 0)))
            user['profile']['goal'] = request.form.get('goal')
            user['profile']['activity_level'] = request.form.get('activity_level', '1.5')  # NEW: Save activity level
            user['profile']['calorie_goal'] = int(float(request.form.get('calorie_goal', 0)))
            user['profile']['protein_goal'] = int(float(request.form.get('protein_goal', 0)))
            user['profile']['carb_goal'] = int(float(request.form.get('carb_goal', 0)))
            user['profile']['fat_goal'] = int(float(request.form.get('fat_goal', 0)))
            user['profile']['birthday'] = request.form.get('birthday')
            
            # Save the updated user!
            from utils import update_user
            update_user(user)
            
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile'))
        except (ValueError, TypeError) as e:
            flash(f'Please enter valid numbers for all numeric fields. Error: {str(e)}', 'error')
            return redirect(url_for('profile'))
    
    # RELOAD user data from file to get the freshest data
    user = get_user(session['user'])
    
    # Convert any string values to integers in profile (for old data)
    if user and 'profile' in user:
        for key in ['height', 'weight', 'calorie_goal', 'protein_goal', 'carb_goal', 'fat_goal']:
            if key in user['profile']:
                try:
                    user['profile'][key] = int(float(user['profile'][key]))
                except (ValueError, TypeError):
                    user['profile'][key] = 0
    
    # Calculate recommended macros for display
    recommended_macros = None
    if user and user.get('profile', {}).get('weight'):
        try:
            weight = float(user['profile']['weight'])
            goal = user.get('profile', {}).get('goal', 'maintain')
            
            if goal == 'gain':
                recommended_macros = {'protein': int(weight * 2.2), 'carbs': int(weight * 4), 'fat': int(weight * 1)}
            elif goal == 'lose':
                recommended_macros = {'protein': int(weight * 2.3), 'carbs': int(weight * 2), 'fat': int(weight * 0.8)}
            else:
                recommended_macros = {'protein': int(weight * 1.8), 'carbs': int(weight * 3), 'fat': int(weight * 0.9)}
        except (ValueError, TypeError):
            recommended_macros = None
    
    return render_template('profile.html', user=user, recommended_macros=recommended_macros)

def calculate_user_stats(user_entries):
    """Calculate user statistics from entries"""
    # Calculate streak
    streak = 0
    today = get_tbilisi_date()
    dates = sorted({e['date'] for e in user_entries}, reverse=True)
    for d in dates:
        try:
            dt = date.fromisoformat(d)
            if dt == today:
                streak += 1
                today = today.fromordinal(today.toordinal() - 1)
            else:
                break
        except:
            continue
    
    # Calculate other stats
    total_entries = len(user_entries)
    cal_per_day = {}
    cal_list = []
    workouts = []
    foods = []
    
    # TODAY'S MACROS ONLY
    today_str = get_tbilisi_date().isoformat()
    today_macros = {"protein": 0, "carbs": 0, "fat": 0}
    
    for e in user_entries:
        for w in e.get('workouts', []):
            workouts.append(w.get('name', ''))
        for f in e.get('foods', []):
            foods.append(f.get('name', ''))
        
        cals = sum([f.get('calories', 0) * (f.get('amount', 100) / 100) for f in e.get('foods', [])])
        if cals:
            cal_list.append(cals)
            cal_per_day.setdefault(e['date'], 0)
            cal_per_day[e['date']] += cals
        
        # ONLY ADD TO TODAY'S MACROS IF IT'S TODAY'S ENTRY
        if e.get('date') == today_str:
            for f in e.get('foods', []):
                amount = f.get('amount', 100) or 100
                factor = amount / 100
                today_macros["protein"] += (f.get("protein", 0) or 0) * factor
                today_macros["carbs"] += (f.get("carbs", 0) or 0) * factor
                today_macros["fat"] += (f.get("fat", 0) or 0) * factor
    
    avg_calories = sum(cal_list) // len(cal_per_day) if cal_per_day else 0
    favorite_workout = max(set(workouts), key=workouts.count) if workouts else 'N/A'
    favorite_food = max(set(foods), key=foods.count) if foods else 'N/A'
    today_calories = cal_per_day.get(today_str, 0)
    
    # Round today's macros for display
    today_macros = {k: round(v, 1) for k, v in today_macros.items()}
    
    return {
        'streak': streak,
        'total_entries': total_entries,
        'avg_calories': avg_calories,
        'today_calories': today_calories,
        'favorite_workout': favorite_workout,
        'favorite_food': favorite_food,
        'macros': today_macros
    }

def calculate_date_macros(user_entries, target_date):
    """Calculate macros for a specific date"""
    date_macros = {"protein": 0, "carbs": 0, "fat": 0, "calories": 0}
    
    for e in user_entries:
        if e.get('date') == target_date:
            for f in e.get('foods', []):
                amount = f.get('amount', 100) or 100
                factor = amount / 100
                date_macros["protein"] += (f.get("protein", 0) or 0) * factor
                date_macros["carbs"] += (f.get("carbs", 0) or 0) * factor
                date_macros["fat"] += (f.get("fat", 0) or 0) * factor
                date_macros["calories"] += (f.get("calories", 0) or 0) * factor
    
    # Round for display
    return {k: round(v, 1) for k, v in date_macros.items()}

@app.route('/get_date_macros/<date_str>')
def get_date_macros(date_str):
    if 'user' not in session:
        return {'error': 'Not logged in'}, 401
    
    # Basic date validation
    if len(date_str) != 10:
        return {'error': 'Invalid date format'}, 400
    
    entries = load_json(ENTRIES_FILE)
    user_entries = [e for e in entries if e['user'] == session['user']]
    macros = calculate_date_macros(user_entries, date_str)
    
    return macros

@app.route('/api/templates', methods=['GET'])
def api_get_templates():
    """API endpoint to get all templates"""
    try:
        templates_file = os.path.join('data', 'templates.json')
        if os.path.exists(templates_file):
            with open(templates_file, 'r') as f:
                templates = json.load(f)
        else:
            templates = []
        return jsonify(templates)
    except Exception as e:
        return jsonify([]), 500

@app.route('/api/templates', methods=['POST'])
def api_create_template():
    """API endpoint to create a new template"""
    try:
        template_data = request.get_json()
        
        # Validate required fields
        if not template_data.get('name'):
            return jsonify({'success': False, 'error': 'Template name is required'}), 400
        
        # Add creator and timestamp
        template_data['creator'] = session.get('user', 'unknown')
        template_data['created_at'] = datetime.now().isoformat()
        
        # Load existing templates
        templates_file = os.path.join('data', 'templates.json')
        if os.path.exists(templates_file):
            with open(templates_file, 'r') as f:
                templates = json.load(f)
        else:
            templates = []
        
        # Check for duplicate names
        if any(t['name'] == template_data['name'] for t in templates):
            return jsonify({'success': False, 'error': 'Template name already exists'}), 400
        
        # Add new template
        templates.append(template_data)
        
        # Save templates
        with open(templates_file, 'w') as f:
            json.dump(templates, f, indent=2)
        
        return jsonify({'success': True, 'message': 'Template created successfully'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/templates/<template_name>', methods=['DELETE'])
def api_delete_template(template_name):
    """API endpoint to delete a template"""
    try:
        templates_file = os.path.join('data', 'templates.json')
        if not os.path.exists(templates_file):
            return jsonify({'success': False, 'error': 'No templates found'}), 404
        
        with open(templates_file, 'r') as f:
            templates = json.load(f)
        
        # Find and remove template
        original_length = len(templates)
        templates = [t for t in templates if t['name'] != template_name]
        
        if len(templates) == original_length:
            return jsonify({'success': False, 'error': 'Template not found'}), 404
        
        # Save updated templates
        with open(templates_file, 'w') as f:
            json.dump(templates, f, indent=2)
        
        return jsonify({'success': True, 'message': 'Template deleted successfully'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/templates/<template_name>/use', methods=['POST'])
def api_use_template(template_name):
    """API endpoint to use a template (log its items)"""
    try:
        if 'user' not in session:
            return jsonify({'success': False, 'error': 'Please log in first'}), 401
        
        # Load template
        templates_file = os.path.join('data', 'templates.json')
        if not os.path.exists(templates_file):
            return jsonify({'success': False, 'error': 'No templates found'}), 404
        
        with open(templates_file, 'r') as f:
            templates = json.load(f)
        
        template = next((t for t in templates if t['name'] == template_name), None)
        if not template:
            return jsonify({'success': False, 'error': 'Template not found'}), 404
        
        # Load existing entries
        entries = load_json(ENTRIES_FILE)
        
        # Create entries for template items
        logged_items = []
        
        # Log foods if present
        if template.get('foods') and len(template['foods']) > 0:
            foods_db = load_json(FOODS_FILE)
            foods_to_log = []
            
            for food_name in template['foods']:
                food = next((f for f in foods_db if f['name'] == food_name), None)
                if food:
                    food_entry = food.copy()
                    food_entry['amount'] = 100  # Default amount
                    foods_to_log.append(food_entry)
            
            if foods_to_log:
                food_entry = {
                    "user": session['user'],
                    "date": get_tbilisi_date().isoformat(),
                    "foods": foods_to_log,
                    "workouts": [],
                    "privacy": "Private"
                }
                entries.append(food_entry)
                logged_items.extend([f['name'] for f in foods_to_log])
        
        # Log workouts if present
        if template.get('workouts') and len(template['workouts']) > 0:
            workouts_db = load_json(WORKOUTS_FILE)
            workouts_to_log = []
            
            for workout_name in template['workouts']:
                workout = next((w for w in workouts_db if w['name'] == workout_name), None)
                if workout:
                    workout_entry = workout.copy()
                    # Add default values
                    workout_entry['sets'] = 3
                    workout_entry['reps'] = 10
                    workout_entry['weight'] = 0
                    workouts_to_log.append(workout_entry)
            
            if workouts_to_log:
                workout_entry = {
                    "user": session['user'],
                    "date": get_tbilisi_date().isoformat(),
                    "foods": [],
                    "workouts": workouts_to_log,
                    "privacy": "Private"
                }
                entries.append(workout_entry)
                logged_items.extend([w['name'] for w in workouts_to_log])
        
        # Save entries
        save_json(ENTRIES_FILE, entries)
        
        if logged_items:
            return jsonify({
                'success': True, 
                'message': f'Successfully logged {len(logged_items)} items from template "{template_name}": {", ".join(logged_items)}'
            })
        else:
            return jsonify({'success': False, 'error': 'Template is empty or items not found'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True)