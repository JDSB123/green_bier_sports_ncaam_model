#!/usr/bin/env python3
"""
Temporary script to run NCAA analysis with relaxed team matching requirements
"""
import os
import sys
from datetime import date

# Add the app directory to the path
sys.path.insert(0, 'services/prediction-service-python/app')

# Import the main analysis function with modified settings
os.environ['MIN_TEAM_RESOLUTION_RATE'] = '0.70'  # Lower threshold from 0.99 to 0.70

# Now run the analysis
exec(open('services/prediction-service-python/run_today.py').read())