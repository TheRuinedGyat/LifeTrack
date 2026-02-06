from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import date
import json
from utils import (
    load_json, save_json, get_user, is_admin, find_duplicate, 
    safe_float, validate_name, validate_numeric_input, check_rate_limit,
    sanitize_categories, FOODS_FILE, ENTRIES_FILE
)
from utils import get_tbilisi_date

food_bp = Blueprint('food', __name__)

@food_bp.route('/log_food', methods=['GET', 'POST'])
def log_food():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        # Rate limiting
        rate_ok, rate_msg = check_rate_limit(session['user'], 'log_food', max_actions=10, time_window=3600)
        if not rate_ok:
            flash(rate_msg, 'error')
            return redirect(url_for('food.log_food'))
        
        try:
            entries = load_json(ENTRIES_FILE)
            foods_db = load_json(FOODS_FILE)
            
            selected_foods = request.form.getlist('foods')
            if not selected_foods:
                flash('Please select at least one food item.', 'error')
                return redirect(url_for('food.log_food'))
            
            logged_foods = []
            
            # CREATE SEPARATE ENTRY FOR EACH FOOD
            for food_name in selected_foods:
                food = next((f for f in foods_db if f['name'] == food_name), None)
                if food:
                    amount_key = f'amount_{food_name}'
                    amount = request.form.get(amount_key)
                    
                    if not amount or float(amount) <= 0:
                        flash(f'Please enter a valid amount for {food_name}.', 'error')
                        return redirect(url_for('food.log_food'))
                    
                    food_entry = food.copy()
                    food_entry['amount'] = float(amount)
                    
                    # Create individual entry for this food
                    entry = {
                        "user": session['user'],
                        "date": get_tbilisi_date().isoformat(),
                        "foods": [food_entry],  # Single food in array
                        "workouts": [],  # Empty workouts for food entry
                        "privacy": "Private"
                    }
                    
                    entries.append(entry)
                    logged_foods.append(food_name)
            
            if logged_foods:
                save_json(ENTRIES_FILE, entries)
                flash(f'✅ Successfully logged {len(logged_foods)} food(s): {", ".join(logged_foods)}!', 'success')
            
            return redirect(url_for('home'))
            
        except Exception as e:
            flash('❌ Error logging foods. Please try again.', 'error')
            return redirect(url_for('food.log_food'))
    
    # Show only approved public foods OR private foods created by current user
    all_foods = load_json(FOODS_FILE)
    foods = []
    
    for f in all_foods:
        if f.get('public', True):
            if not f.get('pending_approval', False):
                foods.append(f)
        else:
            if f.get('creator') == session.get('user'):
                foods.append(f)
    
    user = get_user(session.get('user'))
    
    return render_template('log_food.html', 
                         foods=foods, 
                         user=user, 
                         is_admin=is_admin())

@food_bp.route('/add_food', methods=['GET', 'POST'])
def add_food():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        # Rate limiting
        rate_ok, rate_msg = check_rate_limit(session['user'], 'add_food', max_actions=5, time_window=3600)
        if not rate_ok:
            flash(rate_msg, 'error')
            return render_template('add_food.html')
        
        name = request.form.get('name', '').strip()
        
        # Comprehensive validation
        valid, error_msg = validate_name(name, "Food")
        if not valid:
            flash(error_msg, 'error')
            return render_template('add_food.html')
        
        foods = load_json(FOODS_FILE)
        
        # Get visibility setting
        public = request.form.get('public') == 'true'
        
        # Only check for duplicates if it's a PUBLIC food
        if public and find_duplicate(foods, name):
            flash('A public food with this name already exists or is pending approval.', 'error')
            return render_template('add_food.html')
        
        # Validate nutritional information
        protein_valid, protein = validate_numeric_input(request.form.get('protein'), 'Protein', 0, 1000)
        carbs_valid, carbs = validate_numeric_input(request.form.get('carbs'), 'Carbs', 0, 1000)
        fat_valid, fat = validate_numeric_input(request.form.get('fat'), 'Fat', 0, 1000)
        calories_valid, calories = validate_numeric_input(request.form.get('calories'), 'Calories', 0, 10000)
        
        if not all([protein_valid, carbs_valid, fat_valid, calories_valid]):
            flash('Please enter valid nutritional values.', 'error')
            return render_template('add_food.html')
        
        # Get creator and visibility settings
        creator = session.get('user', 'system')
        
        # Validate categories
        categories_raw = request.form.get('categories', '[]')
        categories = sanitize_categories(categories_raw)
        
        new_food = {
            "name": name,
            "calories": calories,
            "protein": protein,
            "carbs": carbs,
            "fat": fat,
            "creator": creator,
            "categories": categories,
            "public": public,
            "pending_approval": public
        }
        
        try:
            foods.append(new_food)
            save_json(FOODS_FILE, foods)
            
            if public:
                flash('Public food submitted for approval!', 'info')
            else:
                flash('Private food added successfully!', 'success')
        except Exception:
            flash('Error saving food. Please try again.', 'error')
        
        return redirect(url_for('food.log_food'))
    
    return render_template('add_food.html')

@food_bp.route('/delete_food/<name>', methods=['POST'])
def delete_food(name):
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    # Rate limiting for delete operations
    rate_ok, rate_msg = check_rate_limit(session['user'], 'delete_food', max_actions=10, time_window=3600)
    if not rate_ok:
        flash(rate_msg, 'error')
        return redirect(url_for('food.log_food'))
    
    user = get_user(session.get('user'))
    foods = load_json(FOODS_FILE)
    admin = is_admin()
    
    # Find the food to check permissions
    food_to_delete = next((f for f in foods if f['name'].lower() == name.lower()), None)
    
    if not food_to_delete:
        flash("Food not found", "error")
        return redirect(url_for('food.log_food'))
    
    # Permission check:
    # - Creator can always delete their own food
    # - Admin can delete any APPROVED PUBLIC food (for removing false information)
    # - Admin can also delete their own foods (as a creator)
    is_creator = user and food_to_delete.get('creator') == user['username']
    is_approved_public = food_to_delete.get('public', True) and not food_to_delete.get('pending_approval', False)
    
    can_delete = is_creator or (admin and is_approved_public)
    
    if can_delete:
        original_count = len(foods)
        foods = [f for f in foods if f['name'].lower() != name.lower()]
        
        if len(foods) < original_count:
            try:
                save_json(FOODS_FILE, foods)
                flash(f"{name} deleted", "success")
            except Exception:
                flash("Error deleting food", "error")
        else:
            flash("Error deleting food", "error")
    else:
        flash("You don't have permission to delete this food", "error")
    
    return redirect(url_for('food.log_food'))

@food_bp.route('/api/foods', methods=['GET'])
def api_foods():
    """API endpoint to get all foods as JSON"""
    try:
        foods = load_json(FOODS_FILE)
        return jsonify(foods)
    except Exception as e:
        return jsonify([]), 500

@food_bp.route('/api/foods/<food_name>', methods=['GET'])
def api_food_details(food_name):
    """API endpoint to get specific food details"""
    try:
        foods = load_json(FOODS_FILE)
        food = next((f for f in foods if f['name'] == food_name), None)
        if food:
            return jsonify(food)
        return jsonify({'error': 'Food not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500