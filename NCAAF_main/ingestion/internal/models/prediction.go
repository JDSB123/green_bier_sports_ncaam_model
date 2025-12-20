package models

import (
	"database/sql"
	"encoding/json"
	"time"
)

// Prediction represents ML model predictions for a game
type Prediction struct {
	ID     int `db:"id"`
	GameID int `db:"game_id"`

	// Model info
	ModelName    string         `db:"model_name"`
	ModelVersion sql.NullString `db:"model_version"`

	// Predictions
	PredictedHomeScore sql.NullFloat64 `db:"predicted_home_score"`
	PredictedAwayScore sql.NullFloat64 `db:"predicted_away_score"`
	PredictedTotal     sql.NullFloat64 `db:"predicted_total"`
	PredictedMargin    sql.NullFloat64 `db:"predicted_margin"`

	// Confidence
	ConfidenceScore sql.NullFloat64 `db:"confidence_score"`

	// Market comparison
	ConsensusSpread sql.NullFloat64 `db:"consensus_spread"`
	ConsensusTotal  sql.NullFloat64 `db:"consensus_total"`
	EdgeSpread      sql.NullFloat64 `db:"edge_spread"`
	EdgeTotal       sql.NullFloat64 `db:"edge_total"`

	// Recommendation
	RecommendBet       bool            `db:"recommend_bet"`
	RecommendedBetType sql.NullString  `db:"recommended_bet_type"`
	RecommendedSide    sql.NullString  `db:"recommended_side"`
	RecommendedUnits   sql.NullFloat64 `db:"recommended_units"`

	// Rationale (JSONB)
	Rationale json.RawMessage `db:"rationale"`

	PredictedAt time.Time `db:"predicted_at"`
	CreatedAt   time.Time `db:"created_at"`
}

// PredictionRationale represents the JSONB structure for prediction reasoning
type PredictionRationale struct {
	KeyFactors []string           `json:"key_factors"`
	Strengths  []string           `json:"strengths"`
	Concerns   []string           `json:"concerns"`
	Stats      map[string]float64 `json:"stats,omitempty"`
}

// PredictionInput is used for creating predictions from ML service
type PredictionInput struct {
	GameID       int    `json:"game_id"`
	ModelName    string `json:"model_name"`
	ModelVersion string `json:"model_version,omitempty"`

	// Predictions
	PredictedHomeScore float64 `json:"predicted_home_score"`
	PredictedAwayScore float64 `json:"predicted_away_score"`
	PredictedTotal     float64 `json:"predicted_total"`
	PredictedMargin    float64 `json:"predicted_margin"`

	// Confidence
	ConfidenceScore float64 `json:"confidence_score"`

	// Market comparison
	ConsensusSpread *float64 `json:"consensus_spread,omitempty"`
	ConsensusTotal  *float64 `json:"consensus_total,omitempty"`
	EdgeSpread      *float64 `json:"edge_spread,omitempty"`
	EdgeTotal       *float64 `json:"edge_total,omitempty"`

	// Recommendation
	RecommendBet       bool    `json:"recommend_bet"`
	RecommendedBetType string  `json:"recommended_bet_type,omitempty"`
	RecommendedSide    string  `json:"recommended_side,omitempty"`
	RecommendedUnits   float64 `json:"recommended_units,omitempty"`

	// Rationale
	Rationale *PredictionRationale `json:"rationale,omitempty"`
}

// ToPrediction converts PredictionInput to Prediction model
func (pi *PredictionInput) ToPrediction(dbGameID int) *Prediction {
	pred := &Prediction{
		GameID:       dbGameID,
		ModelName:    pi.ModelName,
		RecommendBet: pi.RecommendBet,
		PredictedAt:  time.Now(),
	}

	if pi.ModelVersion != "" {
		pred.ModelVersion = sql.NullString{String: pi.ModelVersion, Valid: true}
	}

	// Predictions
	pred.PredictedHomeScore = sql.NullFloat64{Float64: pi.PredictedHomeScore, Valid: true}
	pred.PredictedAwayScore = sql.NullFloat64{Float64: pi.PredictedAwayScore, Valid: true}
	pred.PredictedTotal = sql.NullFloat64{Float64: pi.PredictedTotal, Valid: true}
	pred.PredictedMargin = sql.NullFloat64{Float64: pi.PredictedMargin, Valid: true}

	// Confidence
	pred.ConfidenceScore = sql.NullFloat64{Float64: pi.ConfidenceScore, Valid: true}

	// Market comparison
	if pi.ConsensusSpread != nil {
		pred.ConsensusSpread = sql.NullFloat64{Float64: *pi.ConsensusSpread, Valid: true}
	}
	if pi.ConsensusTotal != nil {
		pred.ConsensusTotal = sql.NullFloat64{Float64: *pi.ConsensusTotal, Valid: true}
	}
	if pi.EdgeSpread != nil {
		pred.EdgeSpread = sql.NullFloat64{Float64: *pi.EdgeSpread, Valid: true}
	}
	if pi.EdgeTotal != nil {
		pred.EdgeTotal = sql.NullFloat64{Float64: *pi.EdgeTotal, Valid: true}
	}

	// Recommendation
	if pi.RecommendedBetType != "" {
		pred.RecommendedBetType = sql.NullString{String: pi.RecommendedBetType, Valid: true}
	}
	if pi.RecommendedSide != "" {
		pred.RecommendedSide = sql.NullString{String: pi.RecommendedSide, Valid: true}
	}
	if pi.RecommendedUnits > 0 {
		pred.RecommendedUnits = sql.NullFloat64{Float64: pi.RecommendedUnits, Valid: true}
	}

	// Rationale
	if pi.Rationale != nil {
		if jsonData, err := json.Marshal(pi.Rationale); err == nil {
			pred.Rationale = jsonData
		}
	}

	return pred
}
