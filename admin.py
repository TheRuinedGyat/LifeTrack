from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort
from datetime import datetime, timedelta
from utils import (
    load_json, save_json, is_admin, 
    FOODS_FILE, WORKOUTS_FILE, ENTRIES_FILE, USERS_FILE
)

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin_dashboard')
def admin_dashboard():
    if not is_admin():
        abort(403)
    
    # Get pending items - ONLY items with pending_approval: true
    foods = [f for f in load_json(FOODS_FILE) if f.get("pending_approval", False) == True]
    workouts = [w for w in load_json(WORKOUTS_FILE) if w.get("pending_approval", False) == True]
    entries = [e for e in load_json(ENTRIES_FILE) if e.get("pending_approval", False) == True]
    users = load_json(USERS_FILE)
    
    return render_template('admin_dashboard.html',
                         foods=foods,
                         workouts=workouts,
                         entries=entries,
                         users=users)

# Food approval routes
@admin_bp.route('/admin/approve_food/<name>', methods=['POST'])
def approve_food(name):
    if not is_admin():
        abort(403)
    
    foods = load_json(FOODS_FILE)
    for food in foods:
        if food['name'] == name:
            food['pending_approval'] = False
            break
    
    save_json(FOODS_FILE, foods)
    flash(f"{name} approved!", "success")
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/reject_food/<name>', methods=['POST'])
def reject_food(name):
    if not is_admin():
        abort(403)
    
    foods = load_json(FOODS_FILE)
    foods = [f for f in foods if f['name'].lower() != name.lower()]
    save_json(FOODS_FILE, foods)
    flash(f"{name} rejected and removed!", "success")
    return redirect(url_for('admin.admin_dashboard'))

# Workout approval routes
@admin_bp.route('/admin/approve_workout/<name>', methods=['POST'])
def approve_workout(name):
    if not is_admin():
        abort(403)
    
    workouts = load_json(WORKOUTS_FILE)
    for workout in workouts:
        if workout['name'].lower() == name.lower():
            workout['pending_approval'] = False
            break
    
    save_json(WORKOUTS_FILE, workouts)
    flash(f"{name} approved!", "success")
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/reject_workout/<name>', methods=['POST'])
def reject_workout(name):
    if not is_admin():
        abort(403)
    
    workouts = load_json(WORKOUTS_FILE)
    workouts = [w for w in workouts if w['name'].lower() != name.lower()]
    save_json(WORKOUTS_FILE, workouts)
    flash(f"{name} rejected and removed!", "success")
    return redirect(url_for('admin.admin_dashboard'))

# Entry approval routes
@admin_bp.route('/admin/approve_entry/<int:entry_id>', methods=['POST'])
def approve_entry(entry_id):
    if not is_admin():
        abort(403)
    
    entries = load_json(ENTRIES_FILE)
    if 0 <= entry_id < len(entries):
        entries[entry_id]['pending_approval'] = False
        save_json(ENTRIES_FILE, entries)
        flash("Entry approved!", "success")
    else:
        flash("Entry not found!", "error")
    
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/reject_entry/<int:entry_id>', methods=['POST'])
def reject_entry(entry_id):
    if not is_admin():
        abort(403)
    
    entries = load_json(ENTRIES_FILE)
    if 0 <= entry_id < len(entries):
        del entries[entry_id]
        save_json(ENTRIES_FILE, entries)
        flash("Entry rejected and removed!", "success")
    else:
        flash("Entry not found!", "error")
    
    return redirect(url_for('admin.admin_dashboard'))

# User management routes
@admin_bp.route('/admin/ban_user/<username>', methods=['POST'])
def ban_user(username):
    if not is_admin():
        abort(403)
    
    users = load_json(USERS_FILE)
    for user in users:
        if user['username'] == username:
            user['suspended_until'] = '9999-12-31'
            break
    
    save_json(USERS_FILE, users)
    flash(f"User {username} has been permanently banned!", "success")
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/timeout_user/<username>', methods=['POST'])
def timeout_user(username):
    if not is_admin():
        abort(403)
    
    users = load_json(USERS_FILE)
    for user in users:
        if user['username'] == username:
            user['suspended_until'] = (datetime.now() + timedelta(days=7)).isoformat()
            break
    
    save_json(USERS_FILE, users)
    flash(f"User {username} has been suspended for 7 days!", "success")
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/unban_user/<username>', methods=['POST'])
def unban_user(username):
    if not is_admin():
        abort(403)
    
    users = load_json(USERS_FILE)
    for user in users:
        if user['username'] == username:
            user['suspended_until'] = None
            break
    
    save_json(USERS_FILE, users)
    flash(f"User {username} has been unbanned!", "success")
    return redirect(url_for('admin.admin_dashboard'))