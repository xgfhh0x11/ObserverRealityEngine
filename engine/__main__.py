"""
ObserverRealityEngine - Main entry point
Run examples when executed as module.
"""

if __name__ == "__main__":
    import sys
    import os
    
    # Add parent directory to path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from examples.basic_example import *
    
    print("\n" + "=" * 60)
    print("ObserverRealityEngine - Examples")
    print("=" * 60 + "\n")
    
    example_1_simple_measurement()
    example_2_multiple_questions()
    example_3_isa_program()
    example_4_sequential_measurements()
    
    print("=" * 60)
    print("All examples completed!")
    print("=" * 60)

