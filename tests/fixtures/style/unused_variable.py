"""Example with unused variable."""

def calculate_total(items):
    """Calculate total price of items."""
    total = 0
    count = 0  # F841: Local variable 'count' is assigned but never used
    
    for item in items:
        total += item['price']
        # count should be used here but isn't
    
    return total

def calculate_total_fixed(items):
    """Calculate total price of items - FIXED."""
    total = 0
    # Removed unused 'count' variable
    
    for item in items:
        total += item['price']
    
    return total
