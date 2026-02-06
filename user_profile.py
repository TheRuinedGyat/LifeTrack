from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from utils import load_json, save_json, get_user, check_rate_limit, validate_numeric_input
import os

# Create the Blueprint
user_profile_bp = Blueprint('user_profile', __name__)

# Data file paths
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
USERS_FILE = os.path.join(DATA_DIR, 'users.json')

@user_profile_bp.route('/profile')
def profile():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    user = get_user(session['user'])
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('auth.login'))
    
    return render_template('profile.html', user=user)

@user_profile_bp.route('/profile/edit', methods=['GET', 'POST'])
def edit_profile():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    user = get_user(session['user'])
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        # Rate limiting
        rate_ok, rate_msg = check_rate_limit(session['user'], 'edit_profile', max_actions=5, time_window=3600)
        if not rate_ok:
            flash(rate_msg, 'error')
            return render_template('profile.html', user=user)
        
        try:
            users = load_json(USERS_FILE)
            
            # Find user index
            user_index = -1
            for i, u in enumerate(users):
                if u['username'] == session['user']:
                    user_index = i
                    break
            
            if user_index == -1:
                flash('User not found.', 'error')
                return render_template('profile.html', user=user)
            
            # Update profile data
            profile_data = users[user_index].get('profile', {})
            
            # Validate and update numeric fields
            numeric_fields = ['calorie_goal', 'protein_goal', 'carb_goal', 'fat_goal', 'weight', 'height', 'age']
            for field in numeric_fields:
                value = request.form.get(field)
                if value and value.strip():
                    valid, num_value = validate_numeric_input(value, field, 0, 10000)
                    if valid:
                        profile_data[field] = num_value
                    else:
                        flash(f'Invalid {field}: {num_value}', 'error')
                        return render_template('profile.html', user=user)
            
            # Update text fields (including activity_level)
            text_fields = ['gender', 'activity_level', 'goal']
            for field in text_fields:
                value = request.form.get(field)
                if value and value.strip():
                    profile_data[field] = value.strip()
            
            # Save updated profile
            users[user_index]['profile'] = profile_data
            save_json(USERS_FILE, users)
            
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('user_profile.profile'))
            
        except Exception as e:
            flash('Error updating profile.', 'error')
            return render_template('profile.html', user=user)
    
    return render_template('profile.html', user=user)

@user_profile_bp.route('/onboarding', methods=['GET', 'POST'])
def onboarding():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    user = get_user(session['user'])
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('auth.login'))
    
    # Check if user has already completed onboarding
    if user.get('profile', {}).get('onboarding_complete'):
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        try:
            users = load_json(USERS_FILE)
            
            # Find user index
            user_index = -1
            for i, u in enumerate(users):
                if u['username'] == session['user']:
                    user_index = i
                    break
            
            if user_index == -1:
                flash('User not found.', 'error')
                return redirect(url_for('auth.login'))
            
            # Create/update profile
            profile_data = users[user_index].get('profile', {})
            
            # Required fields for onboarding
            required_fields = {
                'age': 'Age',
                'gender': 'Gender',
                'height': 'Height',
                'weight': 'Weight',
                'activity_level': 'Activity Level',
                'goal': 'Goal',
                'calorie_goal': 'Calorie Goal'
            }
            
            # Validate all required fields
            for field, display_name in required_fields.items():
                value = request.form.get(field)
                if not value or not value.strip():
                    flash(f'{display_name} is required.', 'error')
                    return render_template('onboarding.html', user=user)
                
                if field in ['age', 'height', 'weight', 'calorie_goal']:
                    valid, num_value = validate_numeric_input(value, field, 1, 1000)
                    if valid:
                        profile_data[field] = num_value
                    else:
                        flash(f'Invalid {display_name}: {num_value}', 'error')
                        return render_template('onboarding.html', user=user)
                else:
                    profile_data[field] = value.strip()
            
            # Optional macro goals
            optional_fields = ['protein_goal', 'carb_goal', 'fat_goal']
            for field in optional_fields:
                value = request.form.get(field)
                if value and value.strip():
                    valid, num_value = validate_numeric_input(value, field, 0, 1000)
                    if valid:
                        profile_data[field] = num_value
            
            # Mark onboarding as complete
            profile_data['onboarding_complete'] = True
            users[user_index]['profile'] = profile_data
            
            save_json(USERS_FILE, users)
            
            flash('Welcome to LifeTrack! Your profile has been set up.', 'success')
            return redirect(url_for('home'))
            
        except Exception as e:
            flash('Error saving profile.', 'error')
            return render_template('onboarding.html', user=user)
    
    return render_template('onboarding.html', user=user)