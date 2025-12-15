#!/usr/bin/env python3
"""
Test script for the new graph methods in osrsItemProperties.
"""

from datetime import datetime, timedelta
from src.osrs.item_properties import osrsItemProperties

def test_graph_methods():
    """Test the price line graph and volume bar graph methods."""
    
    # Test with a known item (e.g., item_id 2 might be a common item)
    # You can change this to any valid OSRS item ID
    item_id = 2  # Cannonball or another common item
    
    print(f"Testing graph methods for item_id: {item_id}")
    
    # Initialize the item properties
    item = osrsItemProperties(item_id)
    print(f"Item name: {item.name}")
    
    # Set date range (last 7 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    print(f"\nFetching data from {start_date} to {end_date}")
    
    try:
        # Test 1: Create price line graph
        print("\n1. Creating price line graph...")
        price_graph_path = f"test_price_graph_{item_id}.png"
        item.create_price_line_graph(
            start_date=start_date,
            end_date=end_date,
            table_type="5min",
            limit=100,
            save_path=price_graph_path
        )
        print(f"   ✓ Price line graph saved to: {price_graph_path}")
        
        # Test 2: Create volume bar graph
        print("\n2. Creating volume bar graph...")
        volume_graph_path = f"test_volume_graph_{item_id}.png"
        item.create_volume_bar_graph(
            start_date=start_date,
            end_date=end_date,
            table_type="5min",
            limit=100,
            save_path=volume_graph_path
        )
        print(f"   ✓ Volume bar graph saved to: {volume_graph_path}")
        
        # Test 3: Get base64 encoded version
        print("\n3. Testing base64 encoding...")
        base64_img = item.create_price_line_graph(
            start_date=start_date,
            end_date=end_date,
            table_type="5min",
            limit=50,
            return_base64=True
        )
        print(f"   ✓ Base64 encoded image generated (length: {len(base64_img)} chars)")
        
        print("\n✅ All tests passed successfully!")
        print(f"\nGenerated files:")
        print(f"  - {price_graph_path}")
        print(f"  - {volume_graph_path}")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_graph_methods()
