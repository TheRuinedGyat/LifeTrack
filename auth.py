from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from utils import (
    load_json, save_json, get_user, update_user, calculate_recommended_macros, 
    validate_name, check_rate_limit, USERS_FILE
)
import re

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/check_username')
def check_username():
    """API endpoint to check if username is available"""
    username = request.args.get('username', '').strip()
    
    # Basic validation
    if not username or len(username) < 3:
        return jsonify({'available': False, 'error': 'Username too short'})
    
    # Check if username exists (case-insensitive)
    users = load_json(USERS_FILE)
    username_taken = any(u['username'].lower() == username.lower() for u in users)
    
    return jsonify({'available': not username_taken})

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        # Rate limiting for signup
        ip_address = request.environ.get('REMOTE_ADDR', 'unknown')
        rate_ok, rate_msg = check_rate_limit(ip_address, 'signup', max_actions=5, time_window=3600)
        if not rate_ok:
            flash(rate_msg, 'error')
            return render_template('signup.html')
        
        username = request.form['username'].strip()
        password = request.form['password']
        repeat_password = request.form['repeat_password']
        
        # Validate username
        valid, error_msg = validate_name(username, "Username")
        if not valid:
            flash(error_msg, 'error')
            return render_template('signup.html')
        
        # Additional username restrictions
        if len(username) < 3:
            flash('Username must be at least 3 characters long.', 'error')
            return render_template('signup.html')
        
        if ',' in username:
            flash('Commas are not allowed in username.', 'error')
            return render_template('signup.html')
        
        # Password validation
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('signup.html')
        
        if not re.search(r'\d', password):
            flash('Password must contain at least one number.', 'error')
            return render_template('signup.html')
        
        if password != repeat_password:
            flash('Passwords do not match.', 'error')
            return render_template('signup.html')
        
        users = load_json(USERS_FILE)
        if any(user['username'].lower() == username.lower() for user in users):
            flash('Username already exists', 'error')
            return render_template('signup.html')
        
        hashed_pw = generate_password_hash(password)
        users.append({
            "username": username,
            "password": hashed_pw,
            "role": "user",
            "suspended_until": None,
            "profile": {}
        })
        
        try:
            save_json(USERS_FILE, users)
            flash('Registered successfully. Please log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception:
            flash('Error creating account. Please try again.', 'error')
            return render_template('signup.html')
    
    return render_template('signup.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Rate limiting for login attempts
        ip_address = request.environ.get('REMOTE_ADDR', 'unknown')
        rate_ok, rate_msg = check_rate_limit(ip_address, 'login', max_actions=10, time_window=3600)
        if not rate_ok:
            flash(rate_msg, 'error')
            return render_template('login.html')
        
        username = request.form['username'].strip()
        password = request.form['password']
        
        if not username or not password:
            flash('Please enter both username and password.', 'error')
            return render_template('login.html')
        
        user = get_user(username)
        
        if user and check_password_hash(user['password'], password):
            # Check suspension
            if user.get('suspended_until'):
                try:
                    until = datetime.fromisoformat(user['suspended_until'])
                    if until > datetime.now():
                        flash(f'Account suspended until {until.strftime("%Y-%m-%d %H:%M")}', 'error')
                        return render_template('login.html')
                except:
                    pass  # Invalid date format, proceed with login
            
            session['user'] = username
            
            # Check if onboarding needed
            if not user.get('profile') or not user['profile'].get('calorie_goal'):
                return redirect(url_for('auth.onboarding'))
            
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials', 'error')
    
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()  # Clear entire session for security
    flash('Logged out successfully.', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/onboarding', methods=['GET', 'POST'])
def onboarding():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    # Default values
    defaults = {
        'weight': 70, 'height': 175, 'age': 25,
        'gender': 'male', 'goal': 'maintain', 'activity_level': 1.5
    }
    
    if request.method == 'POST':
        try:
            # Get form data with validation
            weight = float(request.form.get('weight', defaults['weight']))
            height = float(request.form.get('height', defaults['height']))
            age = int(request.form.get('age', defaults['age']))
            gender = request.form.get('gender', defaults['gender'])
            goal = request.form.get('goal', defaults['goal'])
            activity_level = float(request.form.get('activity_level', defaults['activity_level']))
            
            # Validate ranges
            if not (30 <= weight <= 300):
                flash('Weight must be between 30 and 300 kg.', 'error')
                return render_template('onboarding.html')
            
            if not (100 <= height <= 250):
                flash('Height must be between 100 and 250 cm.', 'error')
                return render_template('onboarding.html')
            
            if not (13 <= age <= 120):
                flash('Age must be between 13 and 120 years.', 'error')
                return render_template('onboarding.html')
            
            if gender not in ['male', 'female']:
                gender = 'male'
            
            if goal not in ['lose', 'maintain', 'gain']:
                goal = 'maintain'
            
            # Calculate recommendations
            recommended = calculate_recommended_macros(
                weight=weight, height=height, age=age, 
                gender=gender, goal=goal, activity_level=activity_level
            )
            
            # Get macro goals (allow user override)
            protein_goal = int(request.form.get('protein_goal', recommended['protein']))
            carb_goal = int(request.form.get('carb_goal', recommended['carbs']))
            fat_goal = int(request.form.get('fat_goal', recommended['fat']))
            calorie_goal = int(request.form.get('calorie_goal', recommended['calories']))
            
            # Validate macro goals
            if not (0 <= protein_goal <= 1000):
                protein_goal = recommended['protein']
            if not (0 <= carb_goal <= 2000):
                carb_goal = recommended['carbs']
            if not (0 <= fat_goal <= 500):
                fat_goal = recommended['fat']
            if not (500 <= calorie_goal <= 10000):
                calorie_goal = recommended['calories']
            
            # Update user profile
            user = get_user(session['user'])
            user['profile'] = {
                "height": height, "weight": weight, "goal": goal,
                "calorie_goal": calorie_goal, "age": age, "gender": gender,
                "activity_level": activity_level, "protein_goal": protein_goal,
                "carb_goal": carb_goal, "fat_goal": fat_goal,
                "tdee": recommended['tdee'], "bmr": recommended['bmr']
            }
            update_user(user)
            flash('Profile setup complete!', 'success')
            return redirect(url_for('home'))
            
        except (ValueError, TypeError):
            flash('Please enter valid values for all fields.', 'error')
    
    # Calculate recommendations for display
    recommended = calculate_recommended_macros(**defaults)
    
    activity_options = [
        (1.2, "Sedentary (little/no exercise)"),
        (1.375, "Light activity (light exercise 1-3 days/week)"),
        (1.5, "Moderate activity (moderate exercise 3-5 days/week)"),
        (1.725, "Very active (hard exercise 6-7 days/week)"),
        (1.9, "Extremely active (very hard exercise, physical job)")
    ]
    
    return render_template('onboarding.html', 
                         recommended_macros=recommended,
                         activity_options=activity_options,
                         selected_activity=defaults['activity_level'])