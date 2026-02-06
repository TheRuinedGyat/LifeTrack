from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from utils import load_json, save_json, get_user, check_rate_limit, get_tbilisi_date
import os
from datetime import date

templates_bp = Blueprint('templates', __name__)

# Data file paths
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
TEMPLATES_FILE = os.path.join(DATA_DIR, 'templates.json')
FOODS_FILE = os.path.join(DATA_DIR, 'foods.json')
WORKOUTS_FILE = os.path.join(DATA_DIR, 'workouts.json')
ENTRIES_FILE = os.path.join(DATA_DIR, 'entries.json')

@templates_bp.route('/api/templates', methods=['GET'])
def get_templates():
    """Get user's templates - lightweight summary"""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        templates = load_json(TEMPLATES_FILE)
        user_templates = [t for t in templates if t.get('user') == session['user']]
        
        # Return lightweight summaries instead of full objects
        summaries = []
        for t in user_templates:
            summary = {
                'name': t.get('name'),
                'foods_count': len(t.get('foods', [])),
                'workouts_count': len(t.get('workouts', [])),
                'created_at': t.get('created_at')
            }
            summaries.append(summary)
        
        return jsonify(summaries)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@templates_bp.route('/api/templates/<template_name>/details', methods=['GET'])
def get_template_details(template_name):
    """Get full template details (for use/manage)"""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        templates = load_json(TEMPLATES_FILE)
        template = next((t for t in templates if 
                        t.get('user') == session['user'] and 
                        t.get('name') == template_name), None)
        
        if not template:
            return jsonify({'error': 'Template not found'}), 404
        
        return jsonify(template)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@templates_bp.route('/api/templates', methods=['POST'])
def create_template():
    """Create a new template"""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Rate limiting
    rate_ok, rate_msg = check_rate_limit(session['user'], 'create_template', max_actions=10, time_window=3600)
    if not rate_ok:
        return jsonify({'error': rate_msg}), 429
    
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name') or not data.get('name').strip():
            return jsonify({'error': 'Template name is required'}), 400
        
        templates = load_json(TEMPLATES_FILE)
        
        # Check for duplicate template names for this user
        existing = [t for t in templates if t.get('user') == session['user'] and t.get('name') == data['name']]
        if existing:
            return jsonify({'error': 'Template name already exists'}), 400
        
        # Validate foods - ensure user has permission to use each food
        foods_data = data.get('foods', []) if data.get('includeFoods', True) else []
        if foods_data:
            all_foods = load_json(FOODS_FILE)
            for food_item in foods_data:
                # Get the food name - could be string or object
                food_name = food_item.get('name') if isinstance(food_item, dict) else food_item
                food = next((f for f in all_foods if f.get('name') == food_name), None)
                
                if not food:
                    return jsonify({'error': f'Food "{food_name}" not found'}), 400
                
                # Check if user has permission to use this food
                is_public_approved = food.get('public', True) and not food.get('pending_approval', False)
                is_creator = food.get('creator') == session['user']
                
                if not (is_public_approved or is_creator):
                    return jsonify({'error': f'You don\'t have permission to use "{food_name}" in templates'}), 403
        
        # Validate workouts - ensure user has permission to use each workout
        workouts_data = data.get('workouts', []) if data.get('includeWorkouts', True) else []
        if workouts_data:
            all_workouts = load_json(WORKOUTS_FILE)
            for workout_item in workouts_data:
                # Get the workout name - could be string or object
                workout_name = workout_item.get('name') if isinstance(workout_item, dict) else workout_item
                workout = next((w for w in all_workouts if w.get('name') == workout_name), None)
                
                if not workout:
                    return jsonify({'error': f'Workout "{workout_name}" not found'}), 400
                
                # Check if user has permission to use this workout
                is_public_approved = workout.get('public', True) and not workout.get('pending_approval', False)
                is_creator = workout.get('creator') == session['user']
                
                if not (is_public_approved or is_creator):
                    return jsonify({'error': f'You don\'t have permission to use "{workout_name}" in templates'}), 403
        
        # Create new template
        new_template = {
            'name': data['name'].strip(),
            'user': session['user'],
            'foods': foods_data,
            'workouts': workouts_data,
            'created_at': get_tbilisi_date().isoformat()
        }
        
        templates.append(new_template)
        save_json(TEMPLATES_FILE, templates)
        
        return jsonify({'success': True, 'message': 'Template created successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@templates_bp.route('/api/templates/<template_name>', methods=['DELETE'])
def delete_template(template_name):
    """Delete a template"""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        templates = load_json(TEMPLATES_FILE)
        
        # Find and remove the template
        original_count = len(templates)
        templates = [t for t in templates if not (
            t.get('user') == session['user'] and 
            t.get('name') == template_name
        )]
        
        if len(templates) < original_count:
            save_json(TEMPLATES_FILE, templates)
            return jsonify({'success': True, 'message': 'Template deleted successfully'})
        else:
            return jsonify({'error': 'Template not found or access denied'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@templates_bp.route('/api/templates/<template_name>', methods=['PUT'])
def update_template(template_name):
    """Update a template"""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        templates = load_json(TEMPLATES_FILE)
        
        # Find and update the template
        template = next((t for t in templates if 
                        t.get('user') == session['user'] and 
                        t.get('name') == template_name), None)
        
        if not template:
            return jsonify({'error': 'Template not found'}), 404
        
        # Validate foods if being updated
        if 'foods' in data and data['foods']:
            all_foods = load_json(FOODS_FILE)
            for food_item in data['foods']:
                # Get the food name - could be string or object
                food_name = food_item.get('name') if isinstance(food_item, dict) else food_item
                food = next((f for f in all_foods if f.get('name') == food_name), None)
                
                if not food:
                    return jsonify({'error': f'Food "{food_name}" not found'}), 400
                
                # Check if user has permission to use this food
                is_public_approved = food.get('public', True) and not food.get('pending_approval', False)
                is_creator = food.get('creator') == session['user']
                
                if not (is_public_approved or is_creator):
                    return jsonify({'error': f'You don\'t have permission to use "{food_name}" in templates'}), 403
        
        # Validate workouts if being updated
        if 'workouts' in data and data['workouts']:
            all_workouts = load_json(WORKOUTS_FILE)
            for workout_item in data['workouts']:
                # Get the workout name - could be string or object
                workout_name = workout_item.get('name') if isinstance(workout_item, dict) else workout_item
                workout = next((w for w in all_workouts if w.get('name') == workout_name), None)
                
                if not workout:
                    return jsonify({'error': f'Workout "{workout_name}" not found'}), 400
                
                # Check if user has permission to use this workout
                is_public_approved = workout.get('public', True) and not workout.get('pending_approval', False)
                is_creator = workout.get('creator') == session['user']
                
                if not (is_public_approved or is_creator):
                    return jsonify({'error': f'You don\'t have permission to use "{workout_name}" in templates'}), 403
        
        # Update foods and workouts
        if 'foods' in data:
            template['foods'] = data['foods']
        if 'workouts' in data:
            template['workouts'] = data['workouts']
        
        save_json(TEMPLATES_FILE, templates)
        return jsonify({'success': True, 'message': 'Template updated successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@templates_bp.route('/api/templates/<template_name>/use', methods=['POST'])
def use_template(template_name):
    """Use a template to log entries"""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Rate limiting
    rate_ok, rate_msg = check_rate_limit(session['user'], 'use_template', max_actions=20, time_window=3600)
    if not rate_ok:
        return jsonify({'error': rate_msg}), 429
    
    try:
        templates = load_json(TEMPLATES_FILE)
        
        # Find the template
        template = next((t for t in templates if 
                        t.get('user') == session['user'] and 
                        t.get('name') == template_name), None)
        
        if not template:
            return jsonify({'error': 'Template not found'}), 404
        
        # Load necessary data
        foods_db = load_json(FOODS_FILE)
        workouts_db = load_json(WORKOUTS_FILE)
        entries = load_json(ENTRIES_FILE)
        
        today = get_tbilisi_date().isoformat()
        
        # Process foods
        foods_to_log = []
        if template.get('foods'):
            for food_item in template['foods']:
                # Handle both string names and full food objects
                if isinstance(food_item, str):
                    food_name = food_item
                    food = next((f for f in foods_db if f['name'] == food_name), None)
                    if food:
                        food_entry = food.copy()
                        food_entry['amount'] = food_entry.get('amount', 100)  # Default amount
                        foods_to_log.append(food_entry)
                else:
                    # It's already a full food object from the template
                    food_entry = food_item.copy()
                    food_entry['amount'] = food_entry.get('amount', 100)  # Default amount
                    foods_to_log.append(food_entry)
        
        # Process workouts
        workouts_to_log = []
        if template.get('workouts'):
            for workout_item in template['workouts']:
                # Handle both string names and full workout objects
                if isinstance(workout_item, str):
                    workout_name = workout_item
                    workout = next((w for w in workouts_db if w['name'] == workout_name), None)
                    if workout:
                        workouts_to_log.append(workout.copy())
                else:
                    # It's already a full workout object from the template
                    workouts_to_log.append(workout_item.copy())
        
        # Create entries based on template content
        entries_created = 0
        
        if foods_to_log:
            # Create food entry
            food_entry = {
                "user": session['user'],
                "date": today,
                "foods": foods_to_log,
                "workouts": [],
                "privacy": "Private"
            }
            entries.append(food_entry)
            entries_created += 1
        
        if workouts_to_log:
            # Create workout entry
            workout_entry = {
                "user": session['user'],
                "date": today,
                "foods": [],
                "workouts": workouts_to_log,
                "privacy": "Private"
            }
            entries.append(workout_entry)
            entries_created += 1
        
        if entries_created > 0:
            save_json(ENTRIES_FILE, entries)
            return jsonify({
                'success': True, 
                'message': f'Template "{template_name}" logged successfully! Created {entries_created} entries.'
            })
        else:
            return jsonify({'error': 'No valid foods or workouts found in template'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@templates_bp.route('/api/foods', methods=['GET'])
def get_foods():
    """Get available foods for template creation"""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        foods = load_json(FOODS_FILE)
        # Filter foods that are public or created by the user
        available_foods = []
        for food in foods:
            if food.get('public', True) and not food.get('pending_approval', False):
                available_foods.append(food)
            elif food.get('creator') == session['user']:
                available_foods.append(food)
        
        return jsonify(available_foods)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@templates_bp.route('/api/workouts', methods=['GET'])
def get_workouts():
    """Get available workouts for template creation"""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        workouts = load_json(WORKOUTS_FILE)
        # Filter workouts that are public or created by the user
        available_workouts = []
        for workout in workouts:
            if workout.get('public', True) and not workout.get('pending_approval', False):
                available_workouts.append(workout)
            elif workout.get('creator') == session['user']:
                available_workouts.append(workout)
        
        return jsonify(available_workouts)
    except Exception as e:
        return jsonify({'error': str(e)}), 500