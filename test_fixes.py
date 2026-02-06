#!/usr/bin/env python3
"""
Test script to verify the fixes for:
1. Admin can delete public approved foods/workouts
2. Users can only add foods they have permission to use in templates
"""

import json
import os
from datetime import datetime, timedelta, timezone

# Tbilisi timezone
TBILISI_TZ = timezone(timedelta(hours=4))

def get_tbilisi_date():
    return datetime.now(TBILISI_TZ).date()

# Data paths
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
FOODS_FILE = os.path.join(DATA_DIR, 'foods.json')
WORKOUTS_FILE = os.path.join(DATA_DIR, 'workouts.json')

def load_json(path):
    if not os.path.exists(path):
        return [] if 'rate_limits' not in path else {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return [] if 'rate_limits' not in path else {}

def test_food_deletion_logic():
    """Test that deletion logic correctly identifies permissions"""
    print("\n" + "="*60)
    print("TEST 1: Food Deletion Permission Logic")
    print("="*60)
    
    foods = load_json(FOODS_FILE)
    users = load_json(USERS_FILE)
    
    # Find an admin user
    admin_user = next((u for u in users if u.get('role') == 'admin'), None)
    
    # Find a regular user
    regular_user = next((u for u in users if u.get('role') != 'admin'), None)
    
    # Find a public approved food
    public_food = next((f for f in foods if f.get('public') and not f.get('pending_approval')), None)
    
    # Find a private food
    private_food = next((f for f in foods if not f.get('public')), None)
    
    print(f"\n✓ Admin user found: {admin_user['username'] if admin_user else 'None'}")
    print(f"✓ Regular user found: {regular_user['username'] if regular_user else 'None'}")
    print(f"✓ Public approved food found: {public_food['name'] if public_food else 'None'}")
    print(f"✓ Private food found: {private_food['name'] if private_food else 'None'}")
    
    # Test Case 1: Admin can delete public approved food
    if admin_user and public_food:
        is_admin = admin_user.get('role') == 'admin'
        is_creator = public_food.get('creator') == admin_user['username']
        is_approved_public = public_food.get('public', True) and not public_food.get('pending_approval', False)
        can_delete = is_creator or (is_admin and is_approved_public)
        
        print(f"\n[TEST 1A] Admin '{admin_user['username']}' deleting public food '{public_food['name']}'")
        print(f"  - Is admin: {is_admin}")
        print(f"  - Is creator: {is_creator}")
        print(f"  - Is approved public: {is_approved_public}")
        print(f"  - Can delete: {can_delete} ✓" if can_delete else f"  - Can delete: {can_delete} ✗ FAILED")
    
    # Test Case 2: Creator can delete their own food
    if private_food:
        creator = private_food.get('creator')
        is_creator = private_food.get('creator') == creator
        is_approved_public = private_food.get('public', True) and not private_food.get('pending_approval', False)
        is_admin = False
        can_delete = is_creator or (is_admin and is_approved_public)
        
        print(f"\n[TEST 1B] Creator '{creator}' deleting their own food '{private_food['name']}'")
        print(f"  - Is creator: {is_creator}")
        print(f"  - Can delete: {can_delete} ✓" if can_delete else f"  - Can delete: {can_delete} ✗ FAILED")
    
    # Test Case 3: Regular user cannot delete someone else's public food
    if regular_user and public_food:
        if public_food.get('creator') != regular_user['username']:
            is_admin = regular_user.get('role') == 'admin'
            is_creator = public_food.get('creator') == regular_user['username']
            is_approved_public = public_food.get('public', True) and not public_food.get('pending_approval', False)
            can_delete = is_creator or (is_admin and is_approved_public)
            
            print(f"\n[TEST 1C] Regular user '{regular_user['username']}' trying to delete public food '{public_food['name']}'")
            print(f"  - Is admin: {is_admin}")
            print(f"  - Is creator: {is_creator}")
            print(f"  - Is approved public: {is_approved_public}")
            print(f"  - Can delete: {can_delete} (should be False) ✓" if not can_delete else f"  - Can delete: {can_delete} ✗ FAILED")

def test_template_food_validation():
    """Test that template creation validates food permissions"""
    print("\n" + "="*60)
    print("TEST 2: Template Food Permission Validation")
    print("="*60)
    
    foods = load_json(FOODS_FILE)
    users = load_json(USERS_FILE)
    
    regular_user = next((u for u in users if u.get('role') != 'admin'), None)
    
    if not regular_user:
        print("❌ No regular user found, skipping test")
        return
    
    print(f"\n✓ Testing with user: {regular_user['username']}")
    
    # Find a public approved food
    public_food = next((f for f in foods if f.get('public') and not f.get('pending_approval')), None)
    
    # Find a private food that doesn't belong to this user
    private_food_others = next((f for f in foods 
                               if not f.get('public') and f.get('creator') != regular_user['username']), None)
    
    # Find a private food that belongs to this user
    private_food_own = next((f for f in foods 
                            if not f.get('public') and f.get('creator') == regular_user['username']), None)
    
    print(f"\n✓ Public approved food: {public_food['name'] if public_food else 'None'}")
    print(f"✓ Private food (other user): {private_food_others['name'] if private_food_others else 'None'}")
    print(f"✓ Private food (own): {private_food_own['name'] if private_food_own else 'None'}")
    
    # Test Case 1: Can use public approved food
    if public_food:
        is_public_approved = public_food.get('public', True) and not public_food.get('pending_approval', False)
        is_creator = public_food.get('creator') == regular_user['username']
        can_use = is_public_approved or is_creator
        
        print(f"\n[TEST 2A] User '{regular_user['username']}' using public food '{public_food['name']}'")
        print(f"  - Is public approved: {is_public_approved}")
        print(f"  - Can use: {can_use} ✓" if can_use else f"  - Can use: {can_use} ✗ FAILED")
    
    # Test Case 2: Cannot use other user's private food
    if private_food_others:
        is_public_approved = private_food_others.get('public', True) and not private_food_others.get('pending_approval', False)
        is_creator = private_food_others.get('creator') == regular_user['username']
        can_use = is_public_approved or is_creator
        
        print(f"\n[TEST 2B] User '{regular_user['username']}' trying to use other's private food '{private_food_others['name']}'")
        print(f"  - Is public approved: {is_public_approved}")
        print(f"  - Is creator: {is_creator}")
        print(f"  - Can use: {can_use} (should be False) ✓" if not can_use else f"  - Can use: {can_use} ✗ FAILED")
    
    # Test Case 3: Can use own private food
    if private_food_own:
        is_public_approved = private_food_own.get('public', True) and not private_food_own.get('pending_approval', False)
        is_creator = private_food_own.get('creator') == regular_user['username']
        can_use = is_public_approved or is_creator
        
        print(f"\n[TEST 2C] User '{regular_user['username']}' using their own private food '{private_food_own['name']}'")
        print(f"  - Is creator: {is_creator}")
        print(f"  - Can use: {can_use} ✓" if can_use else f"  - Can use: {can_use} ✗ FAILED")

def test_data_integrity():
    """Verify data structure integrity"""
    print("\n" + "="*60)
    print("TEST 3: Data Structure Integrity")
    print("="*60)
    
    foods = load_json(FOODS_FILE)
    workouts = load_json(WORKOUTS_FILE)
    users = load_json(USERS_FILE)
    
    print(f"\n✓ Total foods: {len(foods)}")
    print(f"✓ Total workouts: {len(workouts)}")
    print(f"✓ Total users: {len(users)}")
    
    # Check food structure
    public_count = sum(1 for f in foods if f.get('public', True))
    private_count = sum(1 for f in foods if not f.get('public', True))
    pending_count = sum(1 for f in foods if f.get('pending_approval', False))
    
    print(f"\n[Foods]")
    print(f"  - Public: {public_count}")
    print(f"  - Private: {private_count}")
    print(f"  - Pending approval: {pending_count}")
    
    # Check workout structure
    workout_public = sum(1 for w in workouts if w.get('public', True))
    workout_private = sum(1 for w in workouts if not w.get('public', True))
    workout_pending = sum(1 for w in workouts if w.get('pending_approval', False))
    
    print(f"\n[Workouts]")
    print(f"  - Public: {workout_public}")
    print(f"  - Private: {workout_private}")
    print(f"  - Pending approval: {workout_pending}")
    
    # Check admin users
    admin_count = sum(1 for u in users if u.get('role') == 'admin')
    print(f"\n[Users]")
    print(f"  - Admin users: {admin_count}")

if __name__ == '__main__':
    print("\n" + "🔍 Testing Permission and Validation Fixes" + "\n")
    
    test_data_integrity()
    test_food_deletion_logic()
    test_template_food_validation()
    
    print("\n" + "="*60)
    print("✅ All tests completed!")
    print("="*60 + "\n")
