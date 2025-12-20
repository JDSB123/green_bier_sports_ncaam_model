package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

// Prometheus metrics for the ingestion service

var (
	// API Call metrics
	APICallsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "ncaaf_api_calls_total",
			Help: "Total number of SportsDataIO API calls",
		},
		[]string{"endpoint", "status"},
	)

	APICallDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "ncaaf_api_call_duration_seconds",
			Help:    "Duration of API calls in seconds",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"endpoint"},
	)

	// Database metrics
	DBQueriesTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "ncaaf_db_queries_total",
			Help: "Total number of database queries",
		},
		[]string{"operation", "table", "status"},
	)

	DBQueryDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "ncaaf_db_query_duration_seconds",
			Help:    "Duration of database queries in seconds",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"operation", "table"},
	)

	DBConnectionsActive = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "ncaaf_db_connections_active",
			Help: "Number of active database connections",
		},
	)

	DBConnectionsIdle = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "ncaaf_db_connections_idle",
			Help: "Number of idle database connections",
		},
	)

	// Cache metrics
	CacheHitsTotal = promauto.NewCounter(
		prometheus.CounterOpts{
			Name: "ncaaf_cache_hits_total",
			Help: "Total number of cache hits",
		},
	)

	CacheMissesTotal = promauto.NewCounter(
		prometheus.CounterOpts{
			Name: "ncaaf_cache_misses_total",
			Help: "Total number of cache misses",
		},
	)

	CacheOperationDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "ncaaf_cache_operation_duration_seconds",
			Help:    "Duration of cache operations in seconds",
			Buckets: []float64{.001, .005, .01, .025, .05, .1, .25, .5, 1},
		},
		[]string{"operation"},
	)

	// Sync metrics
	SyncOperationsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "ncaaf_sync_operations_total",
			Help: "Total number of sync operations",
		},
		[]string{"type", "status"},
	)

	SyncDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "ncaaf_sync_duration_seconds",
			Help:    "Duration of sync operations in seconds",
			Buckets: []float64{1, 5, 10, 30, 60, 120, 300, 600},
		},
		[]string{"type"},
	)

	TeamsIngested = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "ncaaf_teams_ingested_total",
			Help: "Total number of teams in database",
		},
	)

	GamesIngested = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "ncaaf_games_ingested_total",
			Help: "Total number of games in database",
		},
	)

	ActiveGames = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "ncaaf_active_games",
			Help: "Number of currently active games",
		},
	)

	OddsRecordsIngested = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "ncaaf_odds_records_total",
			Help: "Total number of odds records in database",
		},
	)

	// Line movement metrics
	LineMovementsDetected = promauto.NewCounter(
		prometheus.CounterOpts{
			Name: "ncaaf_line_movements_detected_total",
			Help: "Total number of line movements detected",
		},
	)

	// Error metrics
	ErrorsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "ncaaf_errors_total",
			Help: "Total number of errors",
		},
		[]string{"component", "error_type"},
	)

	// Worker metrics
	WorkerLoopIterations = promauto.NewCounter(
		prometheus.CounterOpts{
			Name: "ncaaf_worker_loop_iterations_total",
			Help: "Total number of worker loop iterations",
		},
	)

	WorkerLoopDuration = promauto.NewHistogram(
		prometheus.HistogramOpts{
			Name:    "ncaaf_worker_loop_duration_seconds",
			Help:    "Duration of worker loop iterations in seconds",
			Buckets: []float64{1, 5, 10, 30, 60, 120},
		},
	)

	// System metrics
	SystemUptime = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "ncaaf_system_uptime_seconds",
			Help: "System uptime in seconds",
		},
	)

	LastSuccessfulSync = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "ncaaf_last_successful_sync_timestamp",
			Help: "Timestamp of last successful sync operation",
		},
	)
)

// RecordAPICall records an API call metric
func RecordAPICall(endpoint, status string, duration float64) {
	APICallsTotal.WithLabelValues(endpoint, status).Inc()
	APICallDuration.WithLabelValues(endpoint).Observe(duration)
}

// RecordDBQuery records a database query metric
func RecordDBQuery(operation, table, status string, duration float64) {
	DBQueriesTotal.WithLabelValues(operation, table, status).Inc()
	DBQueryDuration.WithLabelValues(operation, table).Observe(duration)
}

// RecordCacheHit records a cache hit
func RecordCacheHit() {
	CacheHitsTotal.Inc()
}

// RecordCacheMiss records a cache miss
func RecordCacheMiss() {
	CacheMissesTotal.Inc()
}

// RecordCacheOperation records a cache operation duration
func RecordCacheOperation(operation string, duration float64) {
	CacheOperationDuration.WithLabelValues(operation).Observe(duration)
}

// RecordSync records a sync operation
func RecordSync(syncType, status string, duration float64) {
	SyncOperationsTotal.WithLabelValues(syncType, status).Inc()
	SyncDuration.WithLabelValues(syncType).Observe(duration)

	if status == "success" {
		LastSuccessfulSync.SetToCurrentTime()
	}
}

// RecordError records an error
func RecordError(component, errorType string) {
	ErrorsTotal.WithLabelValues(component, errorType).Inc()
}

// UpdateDBConnectionStats updates database connection pool statistics
func UpdateDBConnectionStats(active, idle int32) {
	DBConnectionsActive.Set(float64(active))
	DBConnectionsIdle.Set(float64(idle))
}

// UpdateIngestionStats updates ingestion statistics
func UpdateIngestionStats(teams, games, activeGames, odds int64) {
	TeamsIngested.Set(float64(teams))
	GamesIngested.Set(float64(games))
	ActiveGames.Set(float64(activeGames))
	OddsRecordsIngested.Set(float64(odds))
}

// RecordLineMovement records a line movement detection
func RecordLineMovement() {
	LineMovementsDetected.Inc()
}

// RecordWorkerIteration records a worker loop iteration
func RecordWorkerIteration(duration float64) {
	WorkerLoopIterations.Inc()
	WorkerLoopDuration.Observe(duration)
}
