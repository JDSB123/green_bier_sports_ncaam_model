"""
Prometheus metrics for ML Service
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
import time

# Prediction metrics
predictions_total = Counter(
    'ncaaf_ml_predictions_total',
    'Total number of predictions made',
    ['model_type']
)

prediction_duration = Histogram(
    'ncaaf_ml_prediction_duration_seconds',
    'Time spent generating predictions',
    ['model_type'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

prediction_confidence = Histogram(
    'ncaaf_ml_prediction_confidence',
    'Confidence score of predictions',
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

predictions_with_edge = Counter(
    'ncaaf_ml_predictions_with_edge_total',
    'Number of predictions with betting edge',
    ['bet_type']
)

recommended_bets = Counter(
    'ncaaf_ml_recommended_bets_total',
    'Number of recommended bets',
    ['bet_type']
)

# Feature extraction metrics
feature_extraction_duration = Histogram(
    'ncaaf_ml_feature_extraction_duration_seconds',
    'Time spent extracting features',
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0]
)

features_extracted = Counter(
    'ncaaf_ml_features_extracted_total',
    'Total number of feature sets extracted'
)

# Database metrics
db_queries_total = Counter(
    'ncaaf_ml_db_queries_total',
    'Total number of database queries',
    ['operation']
)

db_query_duration = Histogram(
    'ncaaf_ml_db_query_duration_seconds',
    'Database query duration',
    ['operation'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
)

# Cache metrics
cache_hits = Counter(
    'ncaaf_ml_cache_hits_total',
    'Number of cache hits'
)

cache_misses = Counter(
    'ncaaf_ml_cache_misses_total',
    'Number of cache misses'
)

# Model metrics
models_loaded = Gauge(
    'ncaaf_ml_models_loaded',
    'Number of ML models currently loaded'
)

model_load_duration = Histogram(
    'ncaaf_ml_model_load_duration_seconds',
    'Time to load ML models',
    ['model_name']
)

# API metrics
api_requests_total = Counter(
    'ncaaf_ml_api_requests_total',
    'Total API requests',
    ['endpoint', 'method', 'status']
)

api_request_duration = Histogram(
    'ncaaf_ml_api_request_duration_seconds',
    'API request duration',
    ['endpoint', 'method'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Error metrics
errors_total = Counter(
    'ncaaf_ml_errors_total',
    'Total errors',
    ['error_type', 'component']
)

# System metrics
system_uptime = Gauge(
    'ncaaf_ml_system_uptime_seconds',
    'System uptime in seconds'
)


# Helper functions
def record_prediction(model_type: str, duration: float, confidence: float):
    """Record a prediction metric"""
    predictions_total.labels(model_type=model_type).inc()
    prediction_duration.labels(model_type=model_type).observe(duration)
    prediction_confidence.observe(confidence)


def record_edge_detected(bet_type: str):
    """Record when edge is detected"""
    predictions_with_edge.labels(bet_type=bet_type).inc()


def record_recommended_bet(bet_type: str):
    """Record a recommended bet"""
    recommended_bets.labels(bet_type=bet_type).inc()


def record_feature_extraction(duration: float):
    """Record feature extraction metrics"""
    features_extracted.inc()
    feature_extraction_duration.observe(duration)


def record_db_query(operation: str, duration: float):
    """Record database query metrics"""
    db_queries_total.labels(operation=operation).inc()
    db_query_duration.labels(operation=operation).observe(duration)


def record_cache_hit():
    """Record cache hit"""
    cache_hits.inc()


def record_cache_miss():
    """Record cache miss"""
    cache_misses.inc()


def record_model_loaded(model_name: str, duration: float):
    """Record model loading"""
    models_loaded.inc()
    model_load_duration.labels(model_name=model_name).observe(duration)


def record_api_request(endpoint: str, method: str, status: int, duration: float):
    """Record API request metrics"""
    api_requests_total.labels(endpoint=endpoint, method=method, status=str(status)).inc()
    api_request_duration.labels(endpoint=endpoint, method=method).observe(duration)


def record_error(error_type: str, component: str):
    """Record an error"""
    errors_total.labels(error_type=error_type, component=component).inc()


def update_system_uptime(uptime_seconds: float):
    """Update system uptime"""
    system_uptime.set(uptime_seconds)


# Metrics endpoint handler
def metrics_handler() -> Response:
    """Return Prometheus metrics"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
