from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from utils import (
    load_json, save_json, get_user, is_admin, validate_name, 
    validate_numeric_input, check_rate_limit, sanitize_categories
)
from utils import get_tbilisi_date
import json
import os
from datetime import date

workout_bp = Blueprint('workout', __name__)

# Data file paths
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
WORKOUTS_FILE = os.path.join(DATA_DIR, 'workouts.json')
ENTRIES_FILE = os.path.join(DATA_DIR, 'entries.json')
FOODS_FILE = os.path.join(DATA_DIR, 'foods.json')

@workout_bp.route('/log_workout', methods=['GET', 'POST'])
def log_workout():
    if 'user' not in session:
        return redirect(url_for('auth.login'))

    user = get_user(session.get('user'))
    is_admin_flag = is_admin()

    try:
        all_workouts = load_json(WORKOUTS_FILE)
        workouts = []
        
        for w in all_workouts:
            if w.get('public', True):
                if not w.get('pending_approval', False):
                    workouts.append(w)
            else:
                if w.get('creator') == session.get('user'):
                    workouts.append(w)
    except Exception:
        workouts = []

    if request.method == 'POST':
        # Rate limiting
        rate_ok, rate_msg = check_rate_limit(session['user'], 'log_workout', max_actions=10, time_window=3600)
        if not rate_ok:
            flash(rate_msg, 'error')
            return redirect(url_for('workout.log_workout'))
        
        try:
            entries = load_json(ENTRIES_FILE)
            workouts_db = load_json(WORKOUTS_FILE)
            
            selected_workouts = request.form.getlist('workouts')
            if not selected_workouts:
                flash('Please select at least one workout.', 'error')
                return redirect(url_for('workout.log_workout'))
            
            logged_workouts = []
            
            # CREATE SEPARATE ENTRY FOR EACH WORKOUT
            for workout_name in selected_workouts:
                workout = next((w for w in workouts_db if w['name'] == workout_name), None)
                if workout:
                    workout_entry = workout.copy()
                    
                    # Get workout data from form
                    sets = request.form.get(f'sets_{workout_name}')
                    reps = request.form.get(f'reps_{workout_name}')
                    weight = request.form.get(f'weight_{workout_name}')
                    duration = request.form.get(f'duration_{workout_name}')
                    speed = request.form.get(f'speed_{workout_name}')
                    
                    # Add the values if they exist
                    if sets: workout_entry['sets'] = int(sets)
                    if reps: workout_entry['reps'] = int(reps)
                    if weight: workout_entry['weight'] = float(weight)
                    if duration: workout_entry['duration'] = float(duration)
                    if speed: workout_entry['speed'] = float(speed)
                    
                    # Create individual entry for this workout
                    entry = {
                        "user": session['user'],
                        "date": get_tbilisi_date().isoformat(),
                        "foods": [],  # Empty foods for workout entry
                        "workouts": [workout_entry],  # Single workout in array
                        "privacy": "Private"
                    }
                    
                    entries.append(entry)
                    logged_workouts.append(workout_name)
        
            if logged_workouts:
                save_json(ENTRIES_FILE, entries)
                flash(f'✅ Successfully logged {len(logged_workouts)} workout(s): {", ".join(logged_workouts)}!', 'success')
        
            return redirect(url_for('home'))
            
        except Exception as e:
            flash('❌ Error logging workouts. Please try again.', 'error')
            return redirect(url_for('workout.log_workout'))

    return render_template('log_workout.html', workouts=workouts, user=user, is_admin=is_admin_flag)

@workout_bp.route('/add_workout', methods=['GET', 'POST'])
def add_workout():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        # Rate limiting
        rate_ok, rate_msg = check_rate_limit(session['user'], 'add_workout', max_actions=5, time_window=3600)
        if not rate_ok:
            flash(rate_msg, 'error')
            return render_template('add_workout.html')
        
        name = request.form.get('name', '').strip()
        
        # Comprehensive validation
        valid, error_msg = validate_name(name, "Workout")
        if not valid:
            flash(error_msg, 'error')
            return render_template('add_workout.html')
        
        workouts = load_json(WORKOUTS_FILE)
        
        # Get visibility setting with validation
        public = request.form.get('public') == 'true'
        
        # Only check for duplicates if it's a PUBLIC workout
        if public and find_duplicate(workouts, name):
            flash('A public workout with this name already exists or is pending approval.', 'error')
            return render_template('add_workout.html')
        
        # Validate categories
        categories_raw = request.form.get('categories', '[]')
        categories = sanitize_categories(categories_raw)

        new_workout = {
            'name': name,
            'creator': session.get('user'),
            'public': public,
            'categories': categories,
            'pending_approval': public
        }
        
        try:
            workouts.append(new_workout)
            save_json(WORKOUTS_FILE, workouts)
            
            if public:
                flash('Public workout submitted for approval!', 'info')
            else:
                flash('Private workout added!', 'success')
        except Exception:
            flash('Error saving workout. Please try again.', 'error')
            
        return redirect(url_for('workout.log_workout'))

    return render_template('add_workout.html')

def find_duplicate(workouts, name):
    """Return True if a public workout with the same name exists or is pending approval."""
    name_lower = name.strip().lower()
    for w in workouts:
        if (w.get('name', '').strip().lower() == name_lower and 
            w.get('public', True) and 
            (not w.get('pending_approval', False) or w.get('pending_approval', False))):
            return True
    return False

@workout_bp.route('/delete_workout/<name>', methods=['POST'])
def delete_workout(name):
    if 'user' not in session:
        return redirect(url_for('auth.login'))

    # Rate limiting for delete operations
    rate_ok, rate_msg = check_rate_limit(session['user'], 'delete_workout', max_actions=10, time_window=3600)
    if not rate_ok:
        flash(rate_msg, 'error')
        return redirect(request.referrer or url_for('workout.log_workout'))

    user = get_user(session.get('user'))
    admin = is_admin()
    
    try:
        workouts = load_json(WORKOUTS_FILE)
        
        # Find the workout to check permissions
        workout_to_delete = next((w for w in workouts if w['name'].lower() == name.lower()), None)
        
        if not workout_to_delete:
            flash("Workout not found", "error")
            return redirect(request.referrer or url_for('workout.log_workout'))
        
        # Permission check:
        # - Creator can always delete their own workout
        # - Admin can delete any APPROVED PUBLIC workout (for removing false information)
        # - Admin can also delete their own workouts (as a creator)
        is_creator = user and workout_to_delete.get('creator') == user['username']
        is_approved_public = workout_to_delete.get('public', True) and not workout_to_delete.get('pending_approval', False)
        
        can_delete = is_creator or (admin and is_approved_public)
        
        if can_delete:
            original_count = len(workouts)
            workouts = [w for w in workouts if w['name'].lower() != name.lower()]
            
            if len(workouts) < original_count:
                save_json(WORKOUTS_FILE, workouts)
                flash(f"{name} deleted", "success")
            else:
                flash("Error deleting workout", "error")
        else:
            flash("You don't have permission to delete this workout", "error")
            
    except Exception:
        flash("Error deleting workout", "error")

    return redirect(request.referrer or url_for('workout.log_workout'))

@workout_bp.route('/api/workouts', methods=['GET'])
def api_workouts():
    """API endpoint to get all workouts as JSON"""
    try:
        workouts = load_json(WORKOUTS_FILE)
        return jsonify(workouts)
    except Exception as e:
        return jsonify([]), 500

@workout_bp.route('/api/workouts/<workout_name>', methods=['GET'])
def api_workout_details(workout_name):
    """API endpoint to get specific workout details"""
    try:
        workouts = load_json(WORKOUTS_FILE)
        workout = next((w for w in workouts if w['name'] == workout_name), None)
        if workout:
            return jsonify(workout)
        return jsonify({'error': 'Workout not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
