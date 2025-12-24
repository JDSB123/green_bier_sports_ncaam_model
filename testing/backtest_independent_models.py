import pandas as pd
import numpy as np
from sklearn.metrics import mean_absolute_error

# Load historical data
historical_df = pd.read_csv('testing/data/historical/games_2019.csv')  # Example, load all seasons

# For each model, predict and compute MAE
# Example for FG Total
predictions = []
actuals = []
for _, row in historical_df.iterrows():
    # Get teams, predict using model
    pred = fg_total_model.predict(row['home_team'], row['away_team'])
    predictions.append(pred)
    actuals.append(row['home_score'] + row['away_score'])

mae = mean_absolute_error(actuals, predictions)
print(f"FG Total MAE: {mae}")

# Similar for other models
# ROI simulation: Assume market lines, calculate edges, win rates